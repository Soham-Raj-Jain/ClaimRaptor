import os

from dotenv import load_dotenv
from nace_sdk import NaceClient, Noul, Choice, Score

load_dotenv()

api_key = os.getenv("NACE_API_KEY")

with NaceClient(api_key=api_key) as client:

    # -------------------------
    # STEP 1: Upload the PDF
    # -------------------------

    print("1. Uploading claim document...")

    uploaded_file = client.documents.upload(
        "data/test_claim.pdf"
    )

    # -------------------------
    # STEP 2: NDI reads the PDF
    # -------------------------

    print("2. NDI is reading the document...")

    parse_job = client.documents.parse(
        uploaded_file.as_source(),
        output={"formats": ["markdown"]},
        wait_seconds=60,
    )

    if parse_job.status != "succeeded":
        parse_job = client.jobs.wait(parse_job.job_id)

    claim_text = parse_job.result["document"]["markdown"]

    print("3. NDI finished.")

    # -------------------------
    # STEP 3: Give NDI output
    #         directly to Drex
    # -------------------------

    print("4. Drex is evaluating the claim...")

    result = client.system_one(
        state=claim_text,
        questions={

            "covered": Noul(
                instructions=(
                    "Based only on the insurance policy and claim "
                    "information provided, is this claim covered?"
                )
            ),

            "evidence_sufficient": Noul(
                instructions=(
                    "Is there enough evidence in the provided documents "
                    "to make a claim decision?"
                )
            ),

            "action": Choice(
                instructions=(
                    "Based only on the provided policy and claim evidence, "
                    "what should happen to this claim?"
                ),
                criteria={
                    "approve": (
                        "The claim is covered and there is sufficient "
                        "evidence to approve it."
                    ),
                    "manual_review": (
                        "Important information is missing, uncertain, "
                        "ambiguous, or conflicting."
                    ),
                    "deny": (
                        "The claim is clearly not covered by the policy."
                    ),
                },
            ),

            "fraud_risk": Score(
                instructions=(
                    "Based only on the provided evidence, rate the apparent "
                    "fraud or inconsistency risk."
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

    # -------------------------
    # STEP 4: Clean results
    # -------------------------

    covered = result.answers["covered"]
    evidence = result.answers["evidence_sufficient"]
    action = result.answers["action"]
    fraud = result.answers["fraud_risk"]

    fraud_index = max(
        fraud.probabilities,
        key=fraud.probabilities.get
    )

    print("\n==============================")
    print("🦖 CLAIMRAPTOR DECISION")
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