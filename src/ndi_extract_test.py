import os
import json

from dotenv import load_dotenv
from nace_sdk import NaceClient, ParseResultSource

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
        "conflicting_information": {"type": "boolean"}
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
        "conflicting_information"
    ]
}

with NaceClient(api_key=api_key) as client:

    print("1. Uploading PDF...")

    uploaded_file = client.documents.upload(
        "data/test_claim.pdf"
    )

    print("2. Parsing document...")

    parse_job = client.documents.parse(
        uploaded_file.as_source(),
        output={"formats": ["markdown"]},
        wait_seconds=60,
    )

    if parse_job.status != "succeeded":
        parse_job = client.jobs.wait(parse_job.job_id)

    print("3. Extracting structured facts...")

    extract_job = client.documents.extract(
        ParseResultSource(job_id=parse_job.job_id),
        schema=schema,
        citations={
            "enabled": True,
            "include_source_text": True
        },
        wait_seconds=60,
    )

    if extract_job.status != "succeeded":
        extract_job = client.jobs.wait(extract_job.job_id)

    print("\n=== STRUCTURED CLAIM DATA ===\n")

    print(
        json.dumps(
            extract_job.result["data"],
            indent=2
        )
    )