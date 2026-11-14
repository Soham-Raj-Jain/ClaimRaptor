import os

from dotenv import load_dotenv
from nace_sdk import NaceClient

load_dotenv()

api_key = os.getenv("NACE_API_KEY")

with NaceClient(api_key=api_key) as client:

    print("Uploading PDF...")

    uploaded_file = client.documents.upload(
        "data/test_claim.pdf"
    )

    print("Uploaded successfully.")
    print("Parsing with NDI...")

    job = client.documents.parse(
        uploaded_file.as_source(),
        output={"formats": ["markdown"]},
        wait_seconds=60,
    )

    if job.status != "succeeded":
        job = client.jobs.wait(job.job_id)

    print("\n=== NDI OUTPUT ===\n")
    print(job.result["document"]["markdown"])