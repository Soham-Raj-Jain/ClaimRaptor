import os
import json
import time
import random

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from nace_sdk import NaceClient, Choice


# ============================================================
# CONFIG
# ============================================================

load_dotenv()

NACE_API_KEY = os.getenv("NACE_API_KEY")
DEEPINFRA_API_KEY = os.getenv("DEEPINFRA_API_KEY")

DEEPINFRA_MODEL = "Qwen/Qwen3.8-27B"

# Three trials gives us better latency + consistency data.
TRIALS = 3

# Fixed seed = reproducible randomized call order.
RANDOM_SEED = 42

# Current pricing used for estimated API cost.
DREX_INPUT_PRICE_PER_MILLION = 0.03

QWEN_INPUT_PRICE_PER_MILLION = 0.15
QWEN_OUTPUT_PRICE_PER_MILLION = 1.875


# ============================================================
# LOAD DATASET
# ============================================================

with open(
    "data/benchmark_cases.json",
    "r",
    encoding="utf-8",
) as file:
    CASES = json.load(file)


# ============================================================
# NORMALIZE LLM OUTPUT
# ============================================================

def normalize_action(text):

    if not text:
        return "unknown"

    text = text.strip().lower()

    text = text.replace("-", "_")
    text = text.replace(" ", "_")

    if "manual_review" in text:
        return "manual_review"

    if "approve" in text:
        return "approve"

    if "deny" in text:
        return "deny"

    return "unknown"


# ============================================================
# DREX DECISION
# ============================================================

def run_drex(client, claim_data):

    state = json.dumps(
        claim_data,
        indent=2,
    )

    start = time.perf_counter()

    result = client.system_one(
        state=state,
        questions={
            "action": Choice(
                instructions=(
                    "Determine the appropriate action "
                    "for this insurance claim."
                ),
                criteria={
                    "approve": (
                        "The claim is covered and the "
                        "available evidence is sufficient "
                        "for automatic approval."
                    ),

                    "manual_review": (
                        "Important information is missing, "
                        "ambiguous, uncertain, contradictory, "
                        "or requires human review."
                    ),

                    "deny": (
                        "The evidence is sufficient and "
                        "the claim is clearly not covered "
                        "by the insurance policy."
                    ),
                },
            )
        },
        model="drex-max-v1.1",
    )

    latency_ms = (
        time.perf_counter() - start
    ) * 1000

    action = result.answers["action"]

    input_tokens = result.usage.input_tokens

    cost_usd = (
        input_tokens
        / 1_000_000
        * DREX_INPUT_PRICE_PER_MILLION
    )

    return {
        "decision": action.choice,
        "latency_ms": latency_ms,
        "internal_latency_ms": result.evaluation_time_ms,
        "input_tokens": input_tokens,
        "output_tokens": result.usage.output_tokens,
        "cost_usd": cost_usd,
    }


# ============================================================
# DEEPINFRA QWEN DECISION
# ============================================================

def run_qwen(client, claim_data):

    prompt = f"""
You are an insurance claim decision engine.

Choose exactly ONE action:

approve
manual_review
deny

Decision rules:

approve:
The claim is covered and there is enough reliable evidence
for automatic approval.

manual_review:
Important information is missing, uncertain, ambiguous,
contradictory, or requires human review.

deny:
There is enough evidence and the claim is clearly not
covered by the insurance policy.

Claim facts:

{json.dumps(claim_data, indent=2)}

Return ONLY one exact label:

approve
manual_review
deny
"""

    start = time.perf_counter()

    response = client.chat.completions.create(
        model=DEEPINFRA_MODEL,
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

    latency_ms = (
        time.perf_counter() - start
    ) * 1000

    raw_answer = (
        response.choices[0].message.content
        or ""
    )

    decision = normalize_action(
        raw_answer
    )

    input_tokens = (
        response.usage.prompt_tokens
        if response.usage
        else 0
    )

    output_tokens = (
        response.usage.completion_tokens
        if response.usage
        else 0
    )

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
        "decision": decision,
        "latency_ms": latency_ms,
        "internal_latency_ms": None,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
    }


# ============================================================
# RUN ONE MODEL
# ============================================================

def run_model(
    model_name,
    nace_client,
    qwen_client,
    claim_data,
):

    if model_name == "Drex":

        return run_drex(
            nace_client,
            claim_data,
        )

    return run_qwen(
        qwen_client,
        claim_data,
    )


# ============================================================
# MAIN BENCHMARK
# ============================================================

def main():

    if not NACE_API_KEY:
        raise RuntimeError(
            "NACE_API_KEY is missing."
        )

    if not DEEPINFRA_API_KEY:
        raise RuntimeError(
            "DEEPINFRA_API_KEY is missing."
        )

    random.seed(
        RANDOM_SEED
    )

    qwen_client = OpenAI(
        api_key=DEEPINFRA_API_KEY,
        base_url="https://api.deepinfra.com/v1/openai",
    )

    rows = []

    print(
        f"\nLoaded {len(CASES)} unique claims."
    )

    print(
        f"Running {TRIALS} trials per claim per model."
    )

    print(
        f"Total measured requests: "
        f"{len(CASES) * TRIALS * 2}"
    )

    with NaceClient(
        api_key=NACE_API_KEY
    ) as nace_client:

        # ====================================================
        # WARM-UP
        # ====================================================

        print(
            "\nWarming up both APIs..."
        )

        warmup_data = CASES[0]["data"]

        run_drex(
            nace_client,
            warmup_data,
        )

        run_qwen(
            qwen_client,
            warmup_data,
        )

        print(
            "Warm-up complete."
        )

        # ====================================================
        # MEASURED RUNS
        # ====================================================

        for trial in range(
            1,
            TRIALS + 1,
        ):

            print(
                f"\n=============================="
            )

            print(
                f"TRIAL {trial}/{TRIALS}"
            )

            print(
                f"=============================="
            )

            # Randomize claim order each trial.
            trial_cases = CASES.copy()

            random.shuffle(
                trial_cases
            )

            for case in trial_cases:

                claim_id = case["claim_id"]

                expected = case[
                    "expected_action"
                ]

                reason = case["reason"]

                claim_data = case["data"]

                # Randomize which model is called first.
                model_order = [
                    "Drex",
                    "DeepInfra Qwen",
                ]

                random.shuffle(
                    model_order
                )

                for model_name in model_order:

                    result = run_model(
                        model_name,
                        nace_client,
                        qwen_client,
                        claim_data,
                    )

                    correct = (
                        result["decision"]
                        == expected
                    )

                    symbol = (
                        "OK"
                        if correct
                        else "WRONG"
                    )

                    print(
                        f"{claim_id} | "
                        f"{model_name:<14} | "
                        f"{result['decision']:<13} | "
                        f"{result['latency_ms']:>7.1f} ms | "
                        f"{symbol}"
                    )

                    rows.append({
                        "trial": trial,
                        "claim_id": claim_id,
                        "expected": expected,
                        "reason": reason,
                        "model": model_name,
                        "decision": result[
                            "decision"
                        ],
                        "correct": correct,
                        "latency_ms": result[
                            "latency_ms"
                        ],
                        "internal_latency_ms": result[
                            "internal_latency_ms"
                        ],
                        "input_tokens": result[
                            "input_tokens"
                        ],
                        "output_tokens": result[
                            "output_tokens"
                        ],
                        "cost_usd": result[
                            "cost_usd"
                        ],
                    })

    # ========================================================
    # DATAFRAME
    # ========================================================

    df = pd.DataFrame(
        rows
    )

    os.makedirs(
        "results",
        exist_ok=True,
    )

    raw_path = (
        "results/full_benchmark_raw.csv"
    )

    df.to_csv(
        raw_path,
        index=False,
    )

    # ========================================================
    # PRIMARY ACCURACY
    #
    # Trial 1 only:
    # 30 unique claims = 30 accuracy observations/model.
    # ========================================================

    primary = df[
        df["trial"] == 1
    ].copy()

    primary_accuracy = (
        primary.groupby("model")
        ["correct"]
        .mean()
        * 100
    )

    # ========================================================
    # ALL-TRIAL ACCURACY
    # ========================================================

    repeated_accuracy = (
        df.groupby("model")
        ["correct"]
        .mean()
        * 100
    )

    # ========================================================
    # LATENCY
    # ========================================================

    latency_summary = (
        df.groupby("model")
        ["latency_ms"]
        .agg(
            median="median",
            mean="mean",
            minimum="min",
            maximum="max",
        )
    )

    latency_summary[
        "p95"
    ] = (
        df.groupby("model")
        ["latency_ms"]
        .quantile(0.95)
    )

    # ========================================================
    # COST
    # ========================================================

    cost_summary = (
        df.groupby("model")
        ["cost_usd"]
        .agg(
            average_cost="mean",
            total_cost="sum",
        )
    )

    cost_summary[
        "cost_per_1000"
    ] = (
        cost_summary[
            "average_cost"
        ]
        * 1000
    )

    # ========================================================
    # PER-CLASS ACCURACY
    # ========================================================

    class_accuracy = (
        primary.groupby(
            [
                "model",
                "expected",
            ]
        )
        ["correct"]
        .mean()
        .mul(100)
        .unstack()
    )

    # ========================================================
    # CONSISTENCY
    #
    # How often did a model give the same decision
    # on all three trials for a claim?
    # ========================================================

    consistency_rows = []

    for model_name in df[
        "model"
    ].unique():

        model_df = df[
            df["model"]
            == model_name
        ]

        consistent_count = 0

        for claim_id in model_df[
            "claim_id"
        ].unique():

            decisions = (
                model_df[
                    model_df["claim_id"]
                    == claim_id
                ]
                ["decision"]
                .unique()
            )

            if len(decisions) == 1:
                consistent_count += 1

        consistency_rate = (
            consistent_count
            / len(CASES)
            * 100
        )

        consistency_rows.append({
            "model": model_name,
            "consistent_claims": (
                consistent_count
            ),
            "total_claims": len(CASES),
            "consistency_percent": (
                consistency_rate
            ),
        })

    consistency_df = pd.DataFrame(
        consistency_rows
    ).set_index("model")

    # ========================================================
    # ERROR CASES
    # ========================================================

    errors = primary[
        primary["correct"] == False
    ][
        [
            "claim_id",
            "model",
            "expected",
            "decision",
            "reason",
        ]
    ]

    # ========================================================
    # SPEEDUP
    # ========================================================

    drex_median = latency_summary.loc[
        "Drex",
        "median",
    ]

    qwen_median = latency_summary.loc[
        "DeepInfra Qwen",
        "median",
    ]

    median_speedup = (
        qwen_median
        / drex_median
    )

    drex_p95 = latency_summary.loc[
        "Drex",
        "p95",
    ]

    qwen_p95 = latency_summary.loc[
        "DeepInfra Qwen",
        "p95",
    ]

    p95_speedup = (
        qwen_p95
        / drex_p95
    )

    # ========================================================
    # COST RATIO
    # ========================================================

    drex_cost = cost_summary.loc[
        "Drex",
        "average_cost",
    ]

    qwen_cost = cost_summary.loc[
        "DeepInfra Qwen",
        "average_cost",
    ]

    cost_ratio = (
        qwen_cost
        / drex_cost
    )

    # ========================================================
    # PRINT RESULTS
    # ========================================================

    print(
        "\n\n======================================"
    )

    print(
        "CLAIMRAPTOR FULL BENCHMARK"
    )

    print(
        "======================================"
    )

    print(
        "\nPRIMARY ACCURACY"
    )

    print(
        "(30 unique claims, first measured trial)"
    )

    print(
        primary_accuracy.to_string()
    )

    print(
        "\nALL-TRIAL ACCURACY"
    )

    print(
        repeated_accuracy.to_string()
    )

    print(
        "\nPER-CLASS ACCURACY"
    )

    print(
        class_accuracy.to_string()
    )

    print(
        "\nLATENCY (ms)"
    )

    print(
        latency_summary.round(
            2
        ).to_string()
    )

    print(
        "\nCONSISTENCY"
    )

    print(
        consistency_df.round(
            2
        ).to_string()
    )

    print(
        "\nCOST"
    )

    print(
        cost_summary.to_string(
            float_format=lambda x: f"{x:.8f}"
        )
    )

    print(
        "\nCOMPARATIVE METRICS"
    )

    print(
        f"Median latency ratio "
        f"(Qwen / Drex): "
        f"{median_speedup:.2f}x"
    )

    print(
        f"P95 latency ratio "
        f"(Qwen / Drex): "
        f"{p95_speedup:.2f}x"
    )

    print(
        f"Cost ratio "
        f"(Qwen / Drex): "
        f"{cost_ratio:.2f}x"
    )

    print(
        "\nPRIMARY-TRIAL ERRORS"
    )

    if errors.empty:

        print(
            "No errors."
        )

    else:

        print(
            errors.to_string(
                index=False
            )
        )

    # ========================================================
    # SAVE SUMMARY FILES
    # ========================================================

    primary_accuracy.to_csv(
        "results/accuracy.csv"
    )

    class_accuracy.to_csv(
        "results/class_accuracy.csv"
    )

    latency_summary.to_csv(
        "results/latency.csv"
    )

    cost_summary.to_csv(
        "results/cost.csv"
    )

    consistency_df.to_csv(
        "results/consistency.csv"
    )

    errors.to_csv(
        "results/errors.csv",
        index=False,
    )

    # ========================================================
    # MACHINE-READABLE SUMMARY FOR STREAMLIT
    # ========================================================

    summary_json = {
        "unique_claims": len(CASES),
        "trials": TRIALS,

        "drex_accuracy": (
            float(
                primary_accuracy[
                    "Drex"
                ]
            )
        ),

        "qwen_accuracy": (
            float(
                primary_accuracy[
                    "DeepInfra Qwen"
                ]
            )
        ),

        "drex_median_latency_ms": (
            float(drex_median)
        ),

        "qwen_median_latency_ms": (
            float(qwen_median)
        ),

        "drex_p95_latency_ms": (
            float(drex_p95)
        ),

        "qwen_p95_latency_ms": (
            float(qwen_p95)
        ),

        "median_latency_ratio": (
            float(median_speedup)
        ),

        "p95_latency_ratio": (
            float(p95_speedup)
        ),

        "drex_cost_per_decision": (
            float(drex_cost)
        ),

        "qwen_cost_per_decision": (
            float(qwen_cost)
        ),

        "qwen_to_drex_cost_ratio": (
            float(cost_ratio)
        ),

        "drex_consistency": float(
            consistency_df.loc[
                "Drex",
                "consistency_percent",
            ]
        ),

        "qwen_consistency": float(
            consistency_df.loc[
                "DeepInfra Qwen",
                "consistency_percent",
            ]
        ),
    }

    with open(
        "results/benchmark_summary.json",
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            summary_json,
            file,
            indent=2,
        )

    print(
        "\nResults saved under results/"
    )


if __name__ == "__main__":
    main()