import os
import json

from dotenv import load_dotenv
from nace_sdk import (
    NaceClient,
    ParseResultSource,
    Noul,
    Choice,
    Score,
)

load_dotenv()

api_key = os.getenv("NACE_API_KEY")

schema = {
    "type": "object",
    "properties": {
        "policy_number": {"type": "string"},
        "policy_start_date": {"type": "string"},
        "policy_expiration_date": {"type": "string"},
        "claim_number": {"type": "string"},
        "incident_date": {"type": "string"},
        "damage_type": {"type": "string"},
        "collision_deductible": {"type": "number"},
        "repair_cost": {"type": "number"},
        "police_report_submitted": {"type": "boolean"},
        "photos_submitted": {"type": "boolean"},
        "conflicting_information": {"type": "boolean"},
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


with NaceClient(api_key=api_key) as client:

    print("1. Uploading claim...")

    uploaded_file = client.documents.upload(
        "data/test_claim.pdf"
    )

    print("2. NDI parsing...")

    parse_job = client.documents.parse(
        uploaded_file.as_source(),
        output={"formats": ["markdown"]},
        wait_seconds=60,
    )

    if parse_job.status != "succeeded":
        parse_job = client.jobs.wait(parse_job.job_id)

    print("3. NDI extracting structured facts...")

    extract_job = client.documents.extract(
        ParseResultSource(job_id=parse_job.job_id),
        schema=schema,
        citations={
            "enabled": True,
            "include_source_text": True,
        },
        wait_seconds=60,
    )

    if extract_job.status != "succeeded":
        extract_job = client.jobs.wait(extract_job.job_id)

    claim_data = extract_job.result["data"]

    print("\n=== NDI STRUCTURED DATA ===")
    print(json.dumps(claim_data, indent=2))

    # Turn the structured data into the state Drex receives.
    state = json.dumps(claim_data, indent=2)

    print("\n4. Drex evaluating structured claim...")

    result = client.system_one(
        state=state,
        questions={
            "covered": Noul(
                instructions=(
                    "Based only on these structured insurance claim facts, "
                    "is this claim covered?"
                )
            ),

            "evidence_sufficient": Noul(
                instructions=(
                    "Based only on these structured facts, is there enough "
                    "evidence to make a claim decision?"
                )
            ),

            "action": Choice(
                instructions=(
                    "What should happen to this insurance claim?"
                ),
                criteria={
                    "approve": (
                        "The claim is covered and the available "
                        "evidence is sufficient."
                    ),
                    "manual_review": (
                        "Important information is missing, ambiguous, "
                        "uncertain, or conflicting."
                    ),
                    "deny": (
                        "The claim is clearly not covered."
                    ),
                },
            ),

            "fraud_risk": Score(
                instructions=(
                    "Rate the apparent fraud or inconsistency risk "
                    "based only on the provided claim facts."
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

    covered = result.answers["covered"]
    evidence = result.answers["evidence_sufficient"]
    action = result.answers["action"]
    fraud = result.answers["fraud_risk"]

    fraud_index = max(
        fraud.probabilities,
        key=fraud.probabilities.get,
    )

    print("\n==============================")
    print("CLAIMRAPTOR STRUCTURED DECISION")
    print("==============================")

    print(f"Covered: {covered.noul * 100:.2f}% YES")

    print(
        f"Evidence sufficient: "
        f"{evidence.noul * 100:.2f}% YES"
    )

    print(
        f"Action: {action.choice.upper()} "
        f"({action.probabilities[action.choice] * 100:.2f}%)"
    )

    print(
        f"Fraud risk: {fraud.legend[fraud_index]} "
        f"({fraud.probabilities[fraud_index] * 100:.2f}%)"
    )

    print(
        f"Drex decision time: "
        f"{result.evaluation_time_ms:.1f} ms"
    )

    print(
        f"Drex input tokens: "
        f"{result.usage.input_tokens}"
    )