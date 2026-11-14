import os
import json
import tempfile
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv
from nace_sdk import (
    NaceClient,
    ParseResultSource,
    Noul,
    Choice,
    Score,
)

# ============================================================
# CONFIG
# ============================================================

load_dotenv()

NACE_API_KEY = os.getenv("NACE_API_KEY")

st.set_page_config(
    page_title="ClaimRaptor",
    page_icon="🦖",
    layout="wide",
)

# ============================================================
# PAGE HEADER
# ============================================================

st.title("🦖 ClaimRaptor")

st.subheader(
    "Evidence-grounded insurance decisions with NDI + Drex"
)

st.write(
    "Upload multiple insurance claims. "
    "NDI extracts evidence from each document and Drex "
    "independently decides whether to approve, deny, "
    "or send the claim to human review."
)

# ============================================================
# NDI EXTRACTION SCHEMA
# ============================================================

CLAIM_SCHEMA = {
    "type": "object",
    "properties": {
        "policy_number": {
            "type": "string"
        },
        "policy_start_date": {
            "type": "string"
        },
        "policy_expiration_date": {
            "type": "string"
        },
        "claim_number": {
            "type": "string"
        },
        "incident_date": {
            "type": "string"
        },
        "damage_type": {
            "type": "string"
        },
        "collision_deductible": {
            "type": "number"
        },
        "repair_cost": {
            "type": "number"
        },
        "police_report_submitted": {
            "type": "boolean"
        },
        "photos_submitted": {
            "type": "boolean"
        },
        "conflicting_information": {
            "type": "boolean"
        },
    },
    "required": [
        "policy_number",
        "policy_start_date",
        "policy_expiration_date",
        "claim_number",
        "incident_date",
        "damage_type",
        "collision_deductible",
        "repair_cost",
        "police_report_submitted",
        "photos_submitted",
        "conflicting_information",
    ],
}


# ============================================================
# HELPER: CHECK POLICY DATES
# ============================================================

def get_policy_status(claim_data):

    try:
        policy_start = datetime.strptime(
            claim_data["policy_start_date"],
            "%B %d, %Y",
        )

        policy_end = datetime.strptime(
            claim_data["policy_expiration_date"],
            "%B %d, %Y",
        )

        incident_date = datetime.strptime(
            claim_data["incident_date"],
            "%B %d, %Y",
        )

        return policy_start <= incident_date <= policy_end

    except (ValueError, TypeError, KeyError):
        return None


# ============================================================
# HELPER: ANALYZE ONE CLAIM
# ============================================================

def analyze_claim(client, uploaded_file):

    temp_path = None

    try:

        # ----------------------------------------------------
        # SAVE PDF LOCALLY
        # ----------------------------------------------------

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".pdf",
        ) as temp_file:

            temp_file.write(
                uploaded_file.getvalue()
            )

            temp_path = temp_file.name

        # ----------------------------------------------------
        # UPLOAD TO NDI
        # ----------------------------------------------------

        ndi_file = client.documents.upload(
            temp_path
        )

        # ----------------------------------------------------
        # NDI PARSE
        # ----------------------------------------------------

        parse_job = client.documents.parse(
            ndi_file.as_source(),
            output={
                "formats": ["markdown"]
            },
            wait_seconds=60,
        )

        if parse_job.status != "succeeded":
            parse_job = client.jobs.wait(
                parse_job.job_id
            )

        # ----------------------------------------------------
        # NDI EXTRACT
        # ----------------------------------------------------

        extract_job = client.documents.extract(
            ParseResultSource(
                job_id=parse_job.job_id
            ),
            schema=CLAIM_SCHEMA,
            citations={
                "enabled": True,
                "include_source_text": True,
            },
            wait_seconds=60,
        )

        if extract_job.status != "succeeded":
            extract_job = client.jobs.wait(
                extract_job.job_id
            )

        claim_data = extract_job.result["data"]

        # ----------------------------------------------------
        # STRUCTURED STATE FOR DREX
        # ----------------------------------------------------

        state = json.dumps(
            claim_data,
            indent=2,
        )

        # ----------------------------------------------------
        # DREX DECISION
        # ----------------------------------------------------

        result = client.system_one(
            state=state,
            questions={

                "covered": Noul(
                    instructions=(
                        "Based only on these structured insurance "
                        "claim facts, determine whether this claim "
                        "is covered by the policy."
                    )
                ),

                "evidence_sufficient": Noul(
                    instructions=(
                        "Determine whether there is enough reliable "
                        "evidence to automatically make a final "
                        "claim decision."
                    )
                ),

                "action": Choice(
                    instructions=(
                        "Determine the appropriate action for this "
                        "insurance claim."
                    ),
                    criteria={
                        "approve": (
                            "The claim is covered and the available "
                            "evidence is sufficient for automatic "
                            "approval."
                        ),

                        "manual_review": (
                            "Important information is missing, "
                            "ambiguous, uncertain, contradictory, "
                            "or requires human review."
                        ),

                        "deny": (
                            "The evidence is sufficient and the "
                            "claim is clearly not covered by "
                            "the insurance policy."
                        ),
                    },
                ),

                "fraud_risk": Score(
                    instructions=(
                        "Rate apparent fraud or inconsistency risk. "
                        "Only increase fraud risk when there are "
                        "actual contradictions, suspicious evidence, "
                        "deception indicators, or material "
                        "inconsistencies. Missing documents alone "
                        "should not imply fraud."
                    ),
                    criteria=[
                        "Very low",
                        "Low",
                        "Moderate",
                        "High",
                        "Very high",
                    ],
                ),
            },
            model="drex-latest",
        )

        return {
            "filename": uploaded_file.name,
            "claim_data": claim_data,
            "drex_result": result,
        }

    finally:

        if (
            temp_path is not None
            and os.path.exists(temp_path)
        ):
            os.remove(temp_path)


# ============================================================
# MULTI-FILE UPLOAD
# ============================================================

uploaded_files = st.file_uploader(
    "Upload claim PDFs",
    type=["pdf"],
    accept_multiple_files=True,
)

if uploaded_files:

    st.success(
        f"{len(uploaded_files)} claim(s) loaded"
    )

    for uploaded_file in uploaded_files:
        st.write(f"📄 {uploaded_file.name}")

    st.write("")

    analyze_button = st.button(
        "🦖 Analyze All Claims",
        type="primary",
        use_container_width=True,
    )

    # ========================================================
    # ANALYZE ALL CLAIMS
    # ========================================================

    if analyze_button:

        if not NACE_API_KEY:

            st.error(
                "NACE_API_KEY was not found. "
                "Check your .env file."
            )

            st.stop()

        all_results = []

        progress_bar = st.progress(0)

        progress_text = st.empty()

        try:

            with NaceClient(
                api_key=NACE_API_KEY
            ) as client:

                total_files = len(
                    uploaded_files
                )

                for index, uploaded_file in enumerate(
                    uploaded_files
                ):

                    progress_text.write(
                        f"Analyzing "
                        f"{uploaded_file.name}..."
                    )

                    claim_result = analyze_claim(
                        client,
                        uploaded_file,
                    )

                    all_results.append(
                        claim_result
                    )

                    progress_bar.progress(
                        (index + 1) / total_files
                    )

            progress_text.empty()

            progress_bar.empty()

        except Exception as error:

            st.error(
                "ClaimRaptor encountered an error "
                "while processing the claims."
            )

            st.exception(error)

            st.stop()

        # ====================================================
        # PORTFOLIO SUMMARY
        # ====================================================

        st.divider()

        st.header("Claim Decisions")

        summary_columns = st.columns(4)

        approve_count = 0
        review_count = 0
        deny_count = 0

        total_drex_latency = 0

        for claim_result in all_results:

            result = claim_result[
                "drex_result"
            ]

            action = result.answers[
                "action"
            ]

            if action.choice == "approve":
                approve_count += 1

            elif action.choice == "deny":
                deny_count += 1

            else:
                review_count += 1

            total_drex_latency += (
                result.evaluation_time_ms
            )

        average_latency = (
            total_drex_latency
            / len(all_results)
        )

        summary_columns[0].metric(
            "Claims analyzed",
            len(all_results),
        )

        summary_columns[1].metric(
            "Approved",
            approve_count,
        )

        summary_columns[2].metric(
            "Manual review",
            review_count,
        )

        summary_columns[3].metric(
            "Denied",
            deny_count,
        )

        st.caption(
            f"Average Drex decision latency: "
            f"{average_latency:.1f} ms"
        )

        # ====================================================
        # INDIVIDUAL CLAIM RESULTS
        # ====================================================

        for number, claim_result in enumerate(
            all_results,
            start=1,
        ):

            filename = claim_result[
                "filename"
            ]

            claim_data = claim_result[
                "claim_data"
            ]

            result = claim_result[
                "drex_result"
            ]

            covered = result.answers[
                "covered"
            ]

            evidence = result.answers[
                "evidence_sufficient"
            ]

            action = result.answers[
                "action"
            ]

            fraud = result.answers[
                "fraud_risk"
            ]

            fraud_index = max(
                fraud.probabilities,
                key=fraud.probabilities.get,
            )

            fraud_label = fraud.legend[
                fraud_index
            ]

            fraud_confidence = (
                fraud.probabilities[
                    fraud_index
                ]
                * 100
            )

            action_confidence = (
                action.probabilities[
                    action.choice
                ]
                * 100
            )

            policy_active = get_policy_status(
                claim_data
            )

            # -----------------------------------------------
            # CLAIM CARD
            # -----------------------------------------------

            st.divider()

            st.subheader(
                f"Claim {number}: "
                f"{claim_data['claim_number']}"
            )

            st.caption(
                filename
            )

            # -----------------------------------------------
            # FINAL ACTION
            # -----------------------------------------------

            if action.choice == "approve":

                st.success(
                    f"✅ APPROVE — "
                    f"{action_confidence:.2f}%"
                )

            elif action.choice == "deny":

                st.error(
                    f"❌ DENY — "
                    f"{action_confidence:.2f}%"
                )

            else:

                st.warning(
                    f"⚠️ MANUAL REVIEW — "
                    f"{action_confidence:.2f}%"
                )

            # -----------------------------------------------
            # CORE METRICS
            # -----------------------------------------------

            m1, m2, m3, m4 = st.columns(4)

            m1.metric(
                "Coverage",
                f"{covered.noul * 100:.2f}% YES",
            )

            m2.metric(
                "Evidence sufficient",
                (
                    f"{evidence.noul * 100:.2f}% YES"
                ),
            )

            m3.metric(
                "Fraud risk",
                fraud_label,
            )

            m4.metric(
                "Drex latency",
                (
                    f"{result.evaluation_time_ms:.1f} ms"
                ),
            )

            st.caption(
                f"Fraud category confidence: "
                f"{fraud_confidence:.1f}%"
            )

            # -----------------------------------------------
            # EVIDENCE SUMMARY
            # -----------------------------------------------

            st.markdown(
                "### Evidence Summary"
            )

            e1, e2, e3 = st.columns(3)

            with e1:

                st.write(
                    f"**Policy:** "
                    f"{claim_data['policy_number']}"
                )

                st.write(
                    f"**Claim:** "
                    f"{claim_data['claim_number']}"
                )

                st.write(
                    f"**Incident:** "
                    f"{claim_data['incident_date']}"
                )

            with e2:

                st.write(
                    f"**Damage:** "
                    f"{claim_data['damage_type']}"
                )

                st.write(
                    f"**Repair Cost:** "
                    f"${claim_data['repair_cost']:,.0f}"
                )

                st.write(
                    f"**Deductible:** "
                    f"${claim_data['collision_deductible']:,.0f}"
                )

            with e3:

                police_status = (
                    "Yes"
                    if claim_data[
                        "police_report_submitted"
                    ]
                    else "No"
                )

                photo_status = (
                    "Yes"
                    if claim_data[
                        "photos_submitted"
                    ]
                    else "No"
                )

                conflict_status = (
                    "Yes"
                    if claim_data[
                        "conflicting_information"
                    ]
                    else "No"
                )

                st.write(
                    f"**Police Report:** "
                    f"{police_status}"
                )

                st.write(
                    f"**Photos:** "
                    f"{photo_status}"
                )

                st.write(
                    f"**Conflicting Info:** "
                    f"{conflict_status}"
                )

            # -----------------------------------------------
            # DECISION SIGNALS
            # -----------------------------------------------

            st.markdown(
                "### Decision Signals"
            )

            if policy_active is True:

                st.write(
                    "✅ Incident occurred during "
                    "the active policy period"
                )

            elif policy_active is False:

                st.write(
                    "❌ Incident occurred outside "
                    "the active policy period"
                )

            else:

                st.write(
                    "⚠️ Policy dates could not "
                    "be automatically verified"
                )

            if claim_data[
                "police_report_submitted"
            ]:

                st.write(
                    "✅ Police report submitted"
                )

            else:

                st.write(
                    "⚠️ Police report missing"
                )

            if claim_data[
                "photos_submitted"
            ]:

                st.write(
                    "✅ Damage photographs submitted"
                )

            else:

                st.write(
                    "⚠️ Damage photographs missing"
                )

            if claim_data[
                "conflicting_information"
            ]:

                st.write(
                    "⚠️ Conflicting or uncertain "
                    "information detected"
                )

            else:

                st.write(
                    "✅ No conflicting information detected"
                )

            # -----------------------------------------------
            # DREX PROBABILITIES
            # -----------------------------------------------

            st.markdown(
                "### Drex Decision Probabilities"
            )

            p1, p2, p3 = st.columns(3)

            p1.metric(
                "Approve",
                (
                    f"{action.probabilities['approve'] * 100:.2f}%"
                ),
            )

            p2.metric(
                "Manual Review",
                (
                    f"{action.probabilities['manual_review'] * 100:.2f}%"
                ),
            )

            p3.metric(
                "Deny",
                (
                    f"{action.probabilities['deny'] * 100:.2f}%"
                ),
            )

            # -----------------------------------------------
            # DEBUG / TECHNICAL DETAILS
            # -----------------------------------------------

            with st.expander(
                "View raw NDI extraction"
            ):

                st.json(
                    claim_data
                )

            with st.expander(
                "View Drex technical details"
            ):

                st.write(
                    f"**Model:** "
                    f"{result.model}"
                )

                st.write(
                    f"**Input tokens:** "
                    f"{result.usage.input_tokens}"
                )

                st.write(
                    f"**Evaluation time:** "
                    f"{result.evaluation_time_ms:.1f} ms"
                )

                st.write(
                    "**Action probabilities:**"
                )

                st.json(
                    action.probabilities
                )

else:

    st.info(
        "Upload one or more claim PDFs to begin."
    )