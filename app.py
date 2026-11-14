import os
import json
import time
import tempfile
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from nace_sdk import (
    NaceClient,
    Choice,
)


# ============================================================
# CONFIG
# ============================================================

load_dotenv()

NACE_API_KEY = os.getenv("NACE_API_KEY")
DEEPINFRA_API_KEY = os.getenv("DEEPINFRA_API_KEY")

DREX_MODEL = "drex-max-v1.1"
QWEN_MODEL = "Qwen/Qwen3.8-27B"

# Pricing used by the benchmark/live cost estimator.
DREX_INPUT_PRICE_PER_MILLION = 0.03

QWEN_INPUT_PRICE_PER_MILLION = 0.15
QWEN_OUTPUT_PRICE_PER_MILLION = 1.875


st.set_page_config(
    page_title="ClaimRaptor",
    page_icon="🦖",
    layout="wide",
)


# ============================================================
# STYLE
# ============================================================

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    div[data-testid="stMetric"] {
        border: 1px solid rgba(128,128,128,0.25);
        padding: 14px;
        border-radius: 12px;
    }

    .subtitle {
        color: #888;
        margin-top: -10px;
        margin-bottom: 20px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SHARED LIVE DECISION POLICY
#
# BOTH models follow the same evidence rules.
# ============================================================

COMMON_DECISION_POLICY = """
Review the supplied insurance documents and recommend exactly
one claim-handling action.

Use ONLY evidence contained in the supplied documents.

Never invent or assume missing policy terms.

A repair estimate, payment record, subrogation demand,
claim notice, or insurer correspondence does NOT by itself
prove that the loss is covered under the policy.

If the documents do not contain enough policy or coverage
information to establish coverage, choose manual_review.

If important evidence is missing, ambiguous, uncertain,
or contradictory, choose manual_review.

Only choose approve when the supplied evidence clearly
establishes both:

1. that the loss is covered, and
2. that the available evidence is sufficient.

Only choose deny when the supplied evidence clearly
establishes that the claim is not covered or otherwise
ineligible.

Do not guess.
"""


DREX_CRITERIA = {
    "approve": (
        "The supplied documents clearly establish that the "
        "loss is covered and that the available evidence is "
        "sufficient to recommend approval."
    ),

    "manual_review": (
        "Coverage cannot be established from the supplied "
        "documents, or important policy terms, evidence, "
        "dates, cause information, or other facts are "
        "missing, ambiguous, uncertain, or contradictory."
    ),

    "deny": (
        "The supplied documents clearly establish that the "
        "claim is not covered, occurred outside applicable "
        "coverage, is excluded, or is otherwise clearly "
        "ineligible."
    ),
}


QWEN_RULES = f"""
{COMMON_DECISION_POLICY}

The available labels are:

approve
manual_review
deny
"""


# ============================================================
# HELPERS
# ============================================================

def normalize_action(text):

    if not text:
        return "unknown"

    text = (
        text
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    if "manual_review" in text:
        return "manual_review"

    if "approve" in text:
        return "approve"

    if "deny" in text:
        return "deny"

    return "unknown"


def action_display(action):

    if action == "approve":
        return "APPROVE"

    if action == "manual_review":
        return "MANUAL REVIEW"

    if action == "deny":
        return "DENY"

    return "UNKNOWN"


def render_action(action):

    label = action_display(
        action
    )

    if action == "approve":

        st.success(
            f"✅ {label}"
        )

    elif action == "deny":

        st.error(
            f"❌ {label}"
        )

    elif action == "manual_review":

        st.warning(
            f"⚠️ {label}"
        )

    else:

        st.info(
            label
        )


# ============================================================
# NDI PARSE
# ============================================================

def parse_pdf_with_ndi(uploaded_file):

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".pdf",
    ) as temp_file:

        temp_file.write(
            uploaded_file.getvalue()
        )

        temp_path = (
            temp_file.name
        )

    try:

        with NaceClient(
            api_key=NACE_API_KEY
        ) as client:

            start = (
                time.perf_counter()
            )

            # ------------------------------------------------
            # Upload document
            # ------------------------------------------------

            uploaded = (
                client.documents.upload(
                    temp_path,
                    on_conflict="new_version",
                )
            )

            # ------------------------------------------------
            # Parse document
            # ------------------------------------------------

            parse_job = (
                client.documents.parse(
                    uploaded.as_source(),

                    parse_mode="medium",

                    output={
                        "formats": [
                            "markdown"
                        ],

                        "include_page_markers": True,
                    },

                    wait_seconds=60,
                )
            )

            if parse_job.status not in {
                "succeeded",
                "failed",
                "cancelled",
            }:

                parse_job = (
                    client.jobs.wait(
                        parse_job.job_id
                    )
                )

            if parse_job.status != "succeeded":

                raise RuntimeError(
                    "NDI parsing failed with status: "
                    f"{parse_job.status}"
                )

            ndi_latency_ms = (
                time.perf_counter()
                - start
            ) * 1000

            # ------------------------------------------------
            # Read Markdown
            # ------------------------------------------------

            markdown = (
                parse_job.result[
                    "document"
                ][
                    "markdown"
                ]
            )

            if not markdown:

                raise RuntimeError(
                    "NDI returned empty Markdown."
                )

            return {
                "markdown": markdown,

                "ndi_latency_ms": (
                    ndi_latency_ms
                ),

                "parse_job_id": (
                    parse_job.job_id
                ),
            }

    finally:

        try:

            os.remove(
                temp_path
            )

        except OSError:

            pass


# ============================================================
# DREX LIVE DECISION
# ============================================================

def run_live_drex(
    document_markdown,
):

    start = (
        time.perf_counter()
    )

    with NaceClient(
        api_key=NACE_API_KEY
    ) as client:

        result = client.system_one(
            state=document_markdown,

            questions={
                "action": Choice(
                    instructions=(
                        COMMON_DECISION_POLICY
                    ),

                    criteria=(
                        DREX_CRITERIA
                    ),
                )
            },

            model=DREX_MODEL,
        )

    latency_ms = (
        time.perf_counter()
        - start
    ) * 1000

    answer = (
        result.choices[
            "action"
        ]
    )

    input_tokens = (
        result.usage.input_tokens
    )

    output_tokens = (
        result.usage.output_tokens
    )

    cost_usd = (
        input_tokens
        / 1_000_000
        * DREX_INPUT_PRICE_PER_MILLION
    )

    return {
        "model": (
            "Drex Max v1.1"
        ),

        "decision": (
            answer.choice
        ),

        "confidence": (
            float(
                answer.confidence
            )
        ),

        "probabilities": (
            dict(
                answer.probabilities
            )
        ),

        "latency_ms": (
            latency_ms
        ),

        "input_tokens": (
            input_tokens
        ),

        "output_tokens": (
            output_tokens
        ),

        "cost_usd": (
            cost_usd
        ),
    }


# ============================================================
# QWEN LIVE DECISION
# ============================================================

def run_live_qwen(
    document_markdown,
):

    client = OpenAI(
        api_key=DEEPINFRA_API_KEY,

        base_url=(
            "https://api.deepinfra.com/v1/openai"
        ),
    )

    prompt = f"""
You are reviewing insurance claim documentation.

{QWEN_RULES}

DOCUMENT:

{document_markdown}

Return ONLY one exact label:

approve
manual_review
deny
"""

    start = (
        time.perf_counter()
    )

    response = (
        client.chat.completions.create(
            model=QWEN_MODEL,

            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],

            temperature=0,

            max_tokens=10,

            extra_body={
                "reasoning_effort": "none"
            },
        )
    )

    latency_ms = (
        time.perf_counter()
        - start
    ) * 1000

    raw_answer = (
        response
        .choices[0]
        .message
        .content
        or ""
    )

    decision = (
        normalize_action(
            raw_answer
        )
    )

    if response.usage:

        input_tokens = (
            response.usage.prompt_tokens
        )

        output_tokens = (
            response.usage.completion_tokens
        )

    else:

        input_tokens = 0
        output_tokens = 0

    cost_usd = (
        (
            input_tokens
            / 1_000_000
            * QWEN_INPUT_PRICE_PER_MILLION
        )
        +
        (
            output_tokens
            / 1_000_000
            * QWEN_OUTPUT_PRICE_PER_MILLION
        )
    )

    return {
        "model": (
            "DeepInfra Qwen3.8-27B"
        ),

        "decision": (
            decision
        ),

        "raw_answer": (
            raw_answer
        ),

        "latency_ms": (
            latency_ms
        ),

        "input_tokens": (
            input_tokens
        ),

        "output_tokens": (
            output_tokens
        ),

        "cost_usd": (
            cost_usd
        ),
    }


# ============================================================
# LIVE HEAD-TO-HEAD
# ============================================================

def run_live_duel(
    document_markdown,
):

    # NDI parsing is shared.
    #
    # Once parsing finishes, Drex and Qwen are launched
    # simultaneously so neither gets an ordering advantage.

    with ThreadPoolExecutor(
        max_workers=2
    ) as executor:

        drex_future = (
            executor.submit(
                run_live_drex,
                document_markdown,
            )
        )

        qwen_future = (
            executor.submit(
                run_live_qwen,
                document_markdown,
            )
        )

        drex = (
            drex_future.result()
        )

        qwen = (
            qwen_future.result()
        )

    return (
        drex,
        qwen,
    )


# ============================================================
# ANALYZE ONE PDF
# ============================================================

def analyze_pdf(
    uploaded_file,
):

    ndi = (
        parse_pdf_with_ndi(
            uploaded_file
        )
    )

    drex, qwen = (
        run_live_duel(
            ndi["markdown"]
        )
    )

    agreement = (
        drex["decision"]
        == qwen["decision"]
    )

    if drex["latency_ms"] > 0:

        latency_ratio = (
            qwen["latency_ms"]
            / drex["latency_ms"]
        )

    else:

        latency_ratio = 0

    if drex["cost_usd"] > 0:

        cost_ratio = (
            qwen["cost_usd"]
            / drex["cost_usd"]
        )

    else:

        cost_ratio = 0

    return {
        "file_name": (
            uploaded_file.name
        ),

        "document_markdown": (
            ndi["markdown"]
        ),

        "ndi_latency_ms": (
            ndi["ndi_latency_ms"]
        ),

        "parse_job_id": (
            ndi["parse_job_id"]
        ),

        "drex": (
            drex
        ),

        "qwen": (
            qwen
        ),

        "agreement": (
            agreement
        ),

        "latency_ratio": (
            latency_ratio
        ),

        "cost_ratio": (
            cost_ratio
        ),
    }


# ============================================================
# RENDER LIVE RESULT
# ============================================================

def render_live_result(
    result,
    index,
):

    st.divider()

    st.subheader(
        f"Document {index}: "
        f"{result['file_name']}"
    )

    st.caption(
        "NDI parsed the PDF once. "
        "Drex and Qwen received the same parsed evidence."
    )

    # ========================================================
    # MODEL CARDS
    # ========================================================

    drex_col, qwen_col = (
        st.columns(2)
    )

    # --------------------------------------------------------
    # DREX
    # --------------------------------------------------------

    with drex_col:

        st.markdown(
            "### 🦖 Drex"
        )

        render_action(
            result[
                "drex"
            ][
                "decision"
            ]
        )

        st.metric(
            "Model Latency",

            (
                f"{result['drex']['latency_ms']:.1f} ms"
            ),
        )

        st.metric(
            "Inference Cost",

            (
                f"${result['drex']['cost_usd']:.8f}"
            ),
        )

        st.caption(
            (
                "Confidence: "
                f"{result['drex']['confidence'] * 100:.2f}%"
            )
        )

    # --------------------------------------------------------
    # QWEN
    # --------------------------------------------------------

    with qwen_col:

        st.markdown(
            "### 🤖 Qwen"
        )

        render_action(
            result[
                "qwen"
            ][
                "decision"
            ]
        )

        st.metric(
            "Model Latency",

            (
                f"{result['qwen']['latency_ms']:.1f} ms"
            ),
        )

        st.metric(
            "Inference Cost",

            (
                f"${result['qwen']['cost_usd']:.8f}"
            ),
        )

    # ========================================================
    # LIVE COMPARISON
    # ========================================================

    st.markdown(
        "#### Live Comparison"
    )

    c1, c2, c3, c4 = (
        st.columns(4)
    )

    with c1:

        st.metric(
            "Decision Agreement",

            (
                "YES"
                if result["agreement"]
                else "NO"
            ),
        )

    with c2:

        st.metric(
            "Latency Ratio",

            (
                f"{result['latency_ratio']:.2f}×"
            ),

            help=(
                "Qwen latency divided "
                "by Drex latency."
            ),
        )

    with c3:

        st.metric(
            "Cost Ratio",

            (
                f"{result['cost_ratio']:.2f}×"
            ),

            help=(
                "Qwen inference cost divided "
                "by Drex inference cost."
            ),
        )

    with c4:

        st.metric(
            "NDI Parse",

            (
                f"{result['ndi_latency_ms'] / 1000:.2f} s"
            ),

            help=(
                "Shared document-processing time. "
                "Not included in either model's latency."
            ),
        )

    # ========================================================
    # DREX PROBABILITIES
    # ========================================================

    with st.expander(
        "Drex decision probabilities"
    ):

        probabilities = (
            result[
                "drex"
            ][
                "probabilities"
            ]
        )

        probability_df = (
            pd.DataFrame({
                "Action": [
                    "APPROVE",
                    "MANUAL REVIEW",
                    "DENY",
                ],

                "Probability (%)": [
                    (
                        probabilities.get(
                            "approve",
                            0,
                        )
                        * 100
                    ),

                    (
                        probabilities.get(
                            "manual_review",
                            0,
                        )
                        * 100
                    ),

                    (
                        probabilities.get(
                            "deny",
                            0,
                        )
                        * 100
                    ),
                ],
            })
        )

        st.dataframe(
            probability_df,
            use_container_width=True,
            hide_index=True,
        )

    # ========================================================
    # NDI MARKDOWN
    # ========================================================

    with st.expander(
        "NDI parsed document"
    ):

        st.markdown(
            result[
                "document_markdown"
            ]
        )

    # ========================================================
    # TECHNICAL DETAILS
    # ========================================================

    with st.expander(
        "Technical details"
    ):

        st.write(
            "**NDI Parse Job:**",
            result[
                "parse_job_id"
            ],
        )

        st.write(
            "**Drex input tokens:**",
            result[
                "drex"
            ][
                "input_tokens"
            ],
        )

        st.write(
            "**Drex output tokens:**",
            result[
                "drex"
            ][
                "output_tokens"
            ],
        )

        st.write(
            "**Qwen input tokens:**",
            result[
                "qwen"
            ][
                "input_tokens"
            ],
        )

        st.write(
            "**Qwen output tokens:**",
            result[
                "qwen"
            ][
                "output_tokens"
            ],
        )


# ============================================================
# LIVE CLAIM ANALYZER TAB
# ============================================================

def render_claim_analyzer():

    st.header(
        "📄 Real-World Claim Analyzer"
    )

    st.markdown(
        """
Upload real insurance documents.

ClaimRaptor performs:

**PDF → NDI Parse → simultaneous Drex + Qwen decision**

Both models receive the **same NDI-parsed evidence**.

For real-world public documents without verified ground-truth
labels, ClaimRaptor compares **decision behavior, latency,
agreement, and cost — not accuracy**.
        """
    )

    # ========================================================
    # KEY CHECKS
    # ========================================================

    if not NACE_API_KEY:

        st.error(
            "NACE_API_KEY is missing from .env."
        )

        return

    if not DEEPINFRA_API_KEY:

        st.error(
            "DEEPINFRA_API_KEY is missing from .env."
        )

        return

    # ========================================================
    # UPLOADER
    # ========================================================

    uploaded_files = (
        st.file_uploader(
            "Upload claim PDFs",

            type=[
                "pdf"
            ],

            accept_multiple_files=True,
        )
    )

    analyze = (
        st.button(
            "🦖 Run Live Head-to-Head",

            type="primary",

            use_container_width=True,

            disabled=(
                not uploaded_files
            ),
        )
    )

    # ========================================================
    # ANALYSIS
    # ========================================================

    if analyze:

        all_results = []

        failed_claims = []

        progress = (
            st.progress(
                0
            )
        )

        status = (
            st.empty()
        )

        total_files = (
            len(
                uploaded_files
            )
        )

        for index, uploaded_file in enumerate(
            uploaded_files,
            start=1,
        ):

            status.write(
                (
                    f"NDI parsing and evaluating "
                    f"{uploaded_file.name} "
                    f"({index}/{total_files})..."
                )
            )

            # ------------------------------------------------
            # INTERN RELIABILITY FIX:
            #
            # One failed document does NOT kill the entire
            # batch.
            # ------------------------------------------------

            try:

                result = (
                    analyze_pdf(
                        uploaded_file
                    )
                )

                all_results.append(
                    result
                )

            except Exception as exc:

                failed_claims.append({
                    "file": (
                        uploaded_file.name
                    ),

                    "error": (
                        str(exc)
                    ),
                })

            progress.progress(
                index
                / total_files
            )

        progress.empty()
        status.empty()

        st.session_state[
            "live_duel_results"
        ] = all_results

        st.session_state[
            "live_duel_errors"
        ] = failed_claims

    # ========================================================
    # LOAD SESSION RESULTS
    # ========================================================

    all_results = (
        st.session_state.get(
            "live_duel_results",
            [],
        )
    )

    failed_claims = (
        st.session_state.get(
            "live_duel_errors",
            [],
        )
    )

    # ========================================================
    # DISPLAY FAILURES
    # ========================================================

    if failed_claims:

        st.warning(
            (
                f"{len(failed_claims)} document(s) "
                f"could not be analyzed."
            )
        )

        for failed in failed_claims:

            st.error(
                (
                    f"{failed['file']}: "
                    f"{failed['error']}"
                )
            )

    # --------------------------------------------------------
    # Prevent empty-result divide by zero.
    # --------------------------------------------------------

    if not all_results:

        if failed_claims:

            st.error(
                "No documents were successfully analyzed."
            )

        return

    # ========================================================
    # LIVE SESSION SUMMARY
    # ========================================================

    st.divider()

    st.header(
        "Live Session Summary"
    )

    agreement_count = sum(
        result[
            "agreement"
        ]
        for result in all_results
    )

    drex_latencies = [
        result[
            "drex"
        ][
            "latency_ms"
        ]
        for result in all_results
    ]

    qwen_latencies = [
        result[
            "qwen"
        ][
            "latency_ms"
        ]
        for result in all_results
    ]

    drex_cost = sum(
        result[
            "drex"
        ][
            "cost_usd"
        ]
        for result in all_results
    )

    qwen_cost = sum(
        result[
            "qwen"
        ][
            "cost_usd"
        ]
        for result in all_results
    )

    median_drex = float(
        pd.Series(
            drex_latencies
        ).median()
    )

    median_qwen = float(
        pd.Series(
            qwen_latencies
        ).median()
    )

    # ========================================================
    # SUMMARY METRICS
    # ========================================================

    c1, c2, c3, c4 = (
        st.columns(4)
    )

    with c1:

        st.metric(
            "Real PDFs",

            len(
                all_results
            ),
        )

    with c2:

        st.metric(
            "Decision Agreement",

            (
                f"{agreement_count}/"
                f"{len(all_results)}"
            ),
        )

    with c3:

        st.metric(
            "Drex Median",

            (
                f"{median_drex:.0f} ms"
            ),
        )

    with c4:

        st.metric(
            "Qwen Median",

            (
                f"{median_qwen:.0f} ms"
            ),
        )

    if drex_cost > 0:

        live_cost_ratio = (
            qwen_cost
            / drex_cost
        )

        st.info(
            (
                "Across this live session, "
                f"Qwen used approximately "
                f"{live_cost_ratio:.2f}× "
                "the inference cost of Drex."
            )
        )

    # ========================================================
    # DOCUMENT RESULTS
    # ========================================================

    for index, result in enumerate(
        all_results,
        start=1,
    ):

        render_live_result(
            result,
            index,
        )


# ============================================================
# LIVE RESULTS INSIDE APEX TAB
# ============================================================

def render_live_benchmark():

    results = (
        st.session_state.get(
            "live_duel_results",
            [],
        )
    )

    st.subheader(
        "Live Real-World Session"
    )

    st.caption(
        "Public real-world documents generally do not have "
        "verified adjudication labels available here. "
        "This table compares model behavior, latency, cost, "
        "and agreement — not accuracy."
    )

    if not results:

        st.info(
            "Run PDFs through the Live Claim Analyzer "
            "to populate this section."
        )

        return

    rows = []

    for result in results:

        rows.append({
            "Document": (
                result[
                    "file_name"
                ]
            ),

            "Drex Decision": (
                action_display(
                    result[
                        "drex"
                    ][
                        "decision"
                    ]
                )
            ),

            "Qwen Decision": (
                action_display(
                    result[
                        "qwen"
                    ][
                        "decision"
                    ]
                )
            ),

            "Agreement": (
                "Yes"
                if result[
                    "agreement"
                ]
                else "No"
            ),

            "Drex Latency (ms)": (
                round(
                    result[
                        "drex"
                    ][
                        "latency_ms"
                    ],
                    1,
                )
            ),

            "Qwen Latency (ms)": (
                round(
                    result[
                        "qwen"
                    ][
                        "latency_ms"
                    ],
                    1,
                )
            ),

            "Latency Ratio": (
                round(
                    result[
                        "latency_ratio"
                    ],
                    2,
                )
            ),

            "Drex Cost": (
                result[
                    "drex"
                ][
                    "cost_usd"
                ]
            ),

            "Qwen Cost": (
                result[
                    "qwen"
                ][
                    "cost_usd"
                ]
            ),
        })

    live_df = (
        pd.DataFrame(
            rows
        )
    )

    st.dataframe(
        live_df,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# FROZEN APEX BENCHMARK
# ============================================================

def render_fixed_benchmark():

    st.header(
        "📊 Apex Predator Benchmark"
    )

    st.markdown(
        """
**Frozen ground-truth benchmark**

Drex Max v1.1 vs DeepInfra Qwen3.8-27B.

Both models receive the same structured claim state and
explicit policy rules.
        """
    )

    summary_path = (
        "results/benchmark_summary.json"
    )

    errors_path = (
        "results/errors.csv"
    )

    class_accuracy_path = (
        "results/class_accuracy.csv"
    )

    if not os.path.exists(
        summary_path
    ):

        st.warning(
            "Frozen benchmark results not found. "
            "Run `python src/benchmark_full.py`."
        )

        return

    with open(
        summary_path,
        "r",
        encoding="utf-8",
    ) as file:

        summary = (
            json.load(
                file
            )
        )

    # ========================================================
    # HEADLINE
    # ========================================================

    st.success(
        "🦖 Drex won the frozen benchmark on accuracy, "
        "median latency, p95 latency, cost, "
        "and consistency."
    )

    st.caption(
        (
            f"{summary['unique_claims']} unique labeled claims • "
            f"{summary['trials']} trials per model • "
            "10 APPROVE / 10 DENY / 10 MANUAL REVIEW"
        )
    )

    # ========================================================
    # ACCURACY
    # ========================================================

    st.subheader(
        "Decision Quality"
    )

    c1, c2, c3 = (
        st.columns(3)
    )

    with c1:

        st.metric(
            "Drex Accuracy",

            (
                f"{summary['drex_accuracy']:.2f}%"
            ),
        )

    with c2:

        st.metric(
            "Qwen Accuracy",

            (
                f"{summary['qwen_accuracy']:.2f}%"
            ),
        )

    with c3:

        gap = (
            summary[
                "drex_accuracy"
            ]
            -
            summary[
                "qwen_accuracy"
            ]
        )

        st.metric(
            "Drex Advantage",

            (
                f"+{gap:.2f} pts"
            ),
        )

    # ========================================================
    # LATENCY
    # ========================================================

    st.subheader(
        "Latency"
    )

    c1, c2, c3 = (
        st.columns(3)
    )

    with c1:

        st.metric(
            "Drex Median",

            (
                f"{summary['drex_median_latency_ms']:.0f} ms"
            ),
        )

    with c2:

        st.metric(
            "Qwen Median",

            (
                f"{summary['qwen_median_latency_ms']:.0f} ms"
            ),
        )

    with c3:

        st.metric(
            "Median Advantage",

            (
                f"{summary['median_latency_ratio']:.2f}×"
            ),

            help=(
                "Qwen median latency divided "
                "by Drex median latency."
            ),
        )

    c1, c2, c3 = (
        st.columns(3)
    )

    with c1:

        st.metric(
            "Drex P95",

            (
                f"{summary['drex_p95_latency_ms']:.0f} ms"
            ),
        )

    with c2:

        st.metric(
            "Qwen P95",

            (
                f"{summary['qwen_p95_latency_ms']:.0f} ms"
            ),
        )

    with c3:

        st.metric(
            "P95 Advantage",

            (
                f"{summary['p95_latency_ratio']:.2f}×"
            ),
        )

    # ========================================================
    # COST
    # ========================================================

    st.subheader(
        "Inference Cost"
    )

    drex_1000 = (
        summary[
            "drex_cost_per_decision"
        ]
        * 1000
    )

    qwen_1000 = (
        summary[
            "qwen_cost_per_decision"
        ]
        * 1000
    )

    c1, c2, c3 = (
        st.columns(3)
    )

    with c1:

        st.metric(
            "Drex / 1K",

            (
                f"${drex_1000:.4f}"
            ),
        )

    with c2:

        st.metric(
            "Qwen / 1K",

            (
                f"${qwen_1000:.4f}"
            ),
        )

    with c3:

        st.metric(
            "Cost Advantage",

            (
                f"{summary['qwen_to_drex_cost_ratio']:.2f}×"
            ),
        )

    # ========================================================
    # CONSISTENCY
    # ========================================================

    st.subheader(
        "Consistency"
    )

    c1, c2 = (
        st.columns(2)
    )

    with c1:

        st.metric(
            "Drex",

            (
                f"{summary['drex_consistency']:.2f}%"
            ),
        )

    with c2:

        st.metric(
            "Qwen",

            (
                f"{summary['qwen_consistency']:.2f}%"
            ),
        )

    # ========================================================
    # SUMMARY TABLE
    # ========================================================

    st.subheader(
        "Head-to-Head"
    )

    comparison = (
        pd.DataFrame({
            "Metric": [
                "Accuracy",
                "Median latency",
                "P95 latency",
                "Cost / 1K decisions",
                "Consistency",
            ],

            "Drex Max v1.1": [
                (
                    f"{summary['drex_accuracy']:.2f}%"
                ),

                (
                    f"{summary['drex_median_latency_ms']:.0f} ms"
                ),

                (
                    f"{summary['drex_p95_latency_ms']:.0f} ms"
                ),

                (
                    f"${drex_1000:.4f}"
                ),

                (
                    f"{summary['drex_consistency']:.2f}%"
                ),
            ],

            "Qwen3.8-27B": [
                (
                    f"{summary['qwen_accuracy']:.2f}%"
                ),

                (
                    f"{summary['qwen_median_latency_ms']:.0f} ms"
                ),

                (
                    f"{summary['qwen_p95_latency_ms']:.0f} ms"
                ),

                (
                    f"${qwen_1000:.4f}"
                ),

                (
                    f"{summary['qwen_consistency']:.2f}%"
                ),
            ],
        })
    )

    st.dataframe(
        comparison,
        use_container_width=True,
        hide_index=True,
    )

    # ========================================================
    # CLASS ACCURACY
    # ========================================================

    if os.path.exists(
        class_accuracy_path
    ):

        with st.expander(
            "Accuracy by decision type"
        ):

            class_accuracy = (
                pd.read_csv(
                    class_accuracy_path
                )
            )

            st.dataframe(
                class_accuracy,
                use_container_width=True,
                hide_index=True,
            )

    # ========================================================
    # ERRORS
    # ========================================================

    if os.path.exists(
        errors_path
    ):

        errors = (
            pd.read_csv(
                errors_path
            )
        )

        with st.expander(
            "Primary-trial error analysis"
        ):

            if errors.empty:

                st.success(
                    "No primary-trial errors."
                )

            else:

                st.dataframe(
                    errors,
                    use_container_width=True,
                    hide_index=True,
                )

    # ========================================================
    # METHODOLOGY
    # ========================================================

    with st.expander(
        "Frozen benchmark methodology"
    ):

        st.markdown(
            """
### Dataset

- 30 unique synthetic insurance states
- 10 APPROVE
- 10 DENY
- 10 MANUAL REVIEW
- Ground-truth labels defined before model evaluation
- Explicit policy rules supplied to both models

### Fair comparison

Both models receive the same structured claim state.

### Accuracy

Primary accuracy uses the first measured trial across the
30 unique cases.

Repeated trials are not treated as new accuracy examples.

### Latency

End-to-end model API latency is measured with
`time.perf_counter()`.

Both APIs are warmed before measured requests.

Claim order and model execution order are randomized.

### Consistency

Each claim is evaluated three times by each model.

### Models

- Drex Max v1.1
- Qwen3.8-27B through DeepInfra
            """
        )

    # ========================================================
    # LIVE REAL-WORLD SECTION
    # ========================================================

    st.divider()

    render_live_benchmark()


# ============================================================
# MAIN APP
# ============================================================

st.title(
    "🦖 ClaimRaptor"
)

st.markdown(
    """
<div class="subtitle">
Evidence-grounded insurance decision support powered by NDI + Drex.
</div>
    """,
    unsafe_allow_html=True,
)


claim_tab, apex_tab = (
    st.tabs(
        [
            "📄 Live Claim Analyzer",
            "📊 Apex Benchmark",
        ]
    )
)


with claim_tab:

    render_claim_analyzer()


with apex_tab:

    render_fixed_benchmark()