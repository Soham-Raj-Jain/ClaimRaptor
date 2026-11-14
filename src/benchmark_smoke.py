import os
import json
import time
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

# Each unique claim is run several times so latency is less
# dependent on one lucky/unlucky network request.
REPEATS = 5


# ============================================================
# GROUND-TRUTH BENCHMARK CASES
# ============================================================

CASES = [
    {
        "claim_id": "CLM-001",
        "expected_action": "approve",
        "data": {
            "damage_type": "collision",
            "repair_cost": 4700,
            "claim_number": "CLM-001",
            "incident_date": "October 10, 2026",
            "policy_number": "CR-2026-001",
            "photos_submitted": True,
            "policy_start_date": "January 1, 2026",
            "collision_deductible": 1000,
            "policy_expiration_date": "December 31, 2026",
            "conflicting_information": False,
            "police_report_submitted": True,
        },
    },

    {
        "claim_id": "CLM-002",
        "expected_action": "deny",
        "data": {
            "damage_type": "collision damage to the rear bumper",
            "repair_cost": 3000,
            "claim_number": "CLM-002",
            "incident_date": "October 10, 2026",
            "policy_number": "CR-2026-002",
            "photos_submitted": True,
            "policy_start_date": "January 1, 2026",
            "collision_deductible": 1000,
            "policy_expiration_date": "June 30, 2026",
            "conflicting_information": False,
            "police_report_submitted": True,
        },
    },

    {
        "claim_id": "CLM-003",
        "expected_action": "manual_review",
        "data": {
            "damage_type": "damage to the front bumper",
            "repair_cost": 4200,
            "claim_number": "CLM-003",
            "incident_date": "September 20, 2026",
            "policy_number": "CR-2026-003",
            "photos_submitted": False,
            "policy_start_date": "January 1, 2026",
            "collision_deductible": 1000,
            "policy_expiration_date": "December 31, 2026",
            "conflicting_information": True,
            "police_report_submitted": False,
        },
    },
]


# ============================================================
# NORMALIZE LLM OUTPUT
# ============================================================

def normalize_action(text):

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
# DREX
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
        model="drex-latest",
    )

    wall_latency_ms = (
        time.perf_counter() - start
    ) * 1000

    action = result.answers["action"]

    return {
        "decision": action.choice,
        "latency_ms": wall_latency_ms,
        "model_latency_ms": result.evaluation_time_ms,
        "input_tokens": result.usage.input_tokens,
        "output_tokens": result.usage.output_tokens,
    }


# ============================================================
# DEEPINFRA
# ============================================================

def run_deepinfra(client, claim_data):

    prompt = f"""
You are an insurance claim decision engine.

Choose exactly ONE action:

approve
manual_review
deny

Rules:

approve:
The claim is covered and there is enough evidence.

manual_review:
Important information is missing, uncertain,
ambiguous, contradictory, or requires human review.

deny:
There is enough evidence and the claim is clearly
not covered by the insurance policy.

Claim facts:

{json.dumps(claim_data, indent=2)}

Return ONLY one of these exact labels:

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

    wall_latency_ms = (
        time.perf_counter() - start
    ) * 1000

    raw_answer = (
        response.choices[0]
        .message.content
        or ""
    )

    decision = normalize_action(
        raw_answer
    )

    return {
        "decision": decision,
        "latency_ms": wall_latency_ms,
        "model_latency_ms": None,
        "input_tokens": (
            response.usage.prompt_tokens
            if response.usage
            else None
        ),
        "output_tokens": (
            response.usage.completion_tokens
            if response.usage
            else None
        ),
    }


# ============================================================
# RUN BENCHMARK
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

    deepinfra_client = OpenAI(
        api_key=DEEPINFRA_API_KEY,
        base_url="https://api.deepinfra.com/v1/openai",
    )

    rows = []

    with NaceClient(
        api_key=NACE_API_KEY
    ) as nace_client:

        total_runs = (
            len(CASES)
            * REPEATS
            * 2
        )

        completed = 0

        for repeat in range(
            1,
            REPEATS + 1
        ):

            print(
                f"\n=== REPEAT "
                f"{repeat}/{REPEATS} ==="
            )

            for case in CASES:

                claim_id = case["claim_id"]

                expected = case[
                    "expected_action"
                ]

                claim_data = case["data"]

                # --------------------------------------------
                # DREX
                # --------------------------------------------

                drex = run_drex(
                    nace_client,
                    claim_data,
                )

                completed += 1

                print(
                    f"{claim_id} | "
                    f"Drex | "
                    f"{drex['decision']} | "
                    f"{drex['latency_ms']:.1f} ms"
                )

                rows.append({
                    "repeat": repeat,
                    "claim_id": claim_id,
                    "expected": expected,
                    "model": "Drex",
                    "decision": drex[
                        "decision"
                    ],
                    "correct": (
                        drex["decision"]
                        == expected
                    ),
                    "latency_ms": drex[
                        "latency_ms"
                    ],
                    "model_latency_ms": drex[
                        "model_latency_ms"
                    ],
                    "input_tokens": drex[
                        "input_tokens"
                    ],
                    "output_tokens": drex[
                        "output_tokens"
                    ],
                })

                # --------------------------------------------
                # DEEPINFRA
                # --------------------------------------------

                llm = run_deepinfra(
                    deepinfra_client,
                    claim_data,
                )

                completed += 1

                print(
                    f"{claim_id} | "
                    f"DeepInfra | "
                    f"{llm['decision']} | "
                    f"{llm['latency_ms']:.1f} ms"
                )

                rows.append({
                    "repeat": repeat,
                    "claim_id": claim_id,
                    "expected": expected,
                    "model": "DeepInfra Qwen",
                    "decision": llm[
                        "decision"
                    ],
                    "correct": (
                        llm["decision"]
                        == expected
                    ),
                    "latency_ms": llm[
                        "latency_ms"
                    ],
                    "model_latency_ms": None,
                    "input_tokens": llm[
                        "input_tokens"
                    ],
                    "output_tokens": llm[
                        "output_tokens"
                    ],
                })

    # ========================================================
    # RESULTS
    # ========================================================

    df = pd.DataFrame(
        rows
    )

    os.makedirs(
        "results",
        exist_ok=True,
    )

    output_file = (
        "results/smoke_benchmark.csv"
    )

    df.to_csv(
        output_file,
        index=False,
    )

    print(
        "\n\n=============================="
    )

    print(
        "SMOKE BENCHMARK RESULTS"
    )

    print(
        "=============================="
    )

    summary = (
        df.groupby("model")
        .agg(
            accuracy=(
                "correct",
                "mean"
            ),
            median_latency_ms=(
                "latency_ms",
                "median"
            ),
            p95_latency_ms=(
                "latency_ms",
                lambda x: x.quantile(
                    0.95
                )
            ),
            average_input_tokens=(
                "input_tokens",
                "mean"
            ),
            average_output_tokens=(
                "output_tokens",
                "mean"
            ),
        )
        .reset_index()
    )

    summary["accuracy"] *= 100

    print(
        summary.to_string(
            index=False
        )
    )

    drex_median = summary.loc[
        summary["model"] == "Drex",
        "median_latency_ms",
    ].iloc[0]

    llm_median = summary.loc[
        summary["model"]
        == "DeepInfra Qwen",
        "median_latency_ms",
    ].iloc[0]

    speedup = (
        llm_median
        / drex_median
    )

    print(
        f"\nDrex median speedup: "
        f"{speedup:.2f}x"
    )

    print(
        f"\nRaw results saved to: "
        f"{output_file}"
    )


if __name__ == "__main__":
    main()