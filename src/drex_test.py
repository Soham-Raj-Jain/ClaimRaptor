import os

from dotenv import load_dotenv
from nace_sdk import NaceClient, Noul, Choice, Score

load_dotenv()

api_key = os.getenv("NACE_API_KEY")

state = """
Insurance policy:
Collision damage is covered only while the policy is active.
The collision deductible is $1,000.

Claim:
The customer's vehicle was damaged in a collision.
The policy was active on the accident date.
The repair estimate is $4,800.
A repair estimate and accident report were submitted.
There is no conflicting information in the claim.
"""

with NaceClient(api_key=api_key) as client:
    result = client.system_one(
        state=state,
        questions={
            "covered": Noul(
                instructions="Is this claim covered by the insurance policy?"
            ),

            "evidence_sufficient": Noul(
                instructions="Is there enough evidence to make a claim decision?"
            ),

            "action": Choice(
                instructions="What should happen to this claim?",
                criteria={
                    "approve": "The claim is covered and evidence is sufficient.",
                    "manual_review": "Important evidence is missing or ambiguous.",
                    "deny": "The claim is clearly not covered."
                }
            ),

            "fraud_risk": Score(
                instructions="Rate the fraud risk of this claim.",
                criteria=[
                    "Very low",
                    "Low",
                    "Moderate",
                    "High",
                    "Very high"
                ]
            )
        },
        model="drex-latest",
    )

covered = result.answers["covered"]
evidence = result.answers["evidence_sufficient"]
action = result.answers["action"]
fraud = result.answers["fraud_risk"]

print("\n=== CLAIMRAPTOR DECISION ===")

print(f"Covered: {covered.noul * 100:.2f}% YES")

print(
    f"Evidence sufficient: "
    f"{evidence.noul * 100:.2f}% YES"
)

print(
    f"Action: {action.choice.upper()} "
    f"({action.probabilities[action.choice] * 100:.2f}%)"
)

fraud_index = max(
    fraud.probabilities,
    key=fraud.probabilities.get
)

print(
    f"Fraud risk: {fraud.legend[fraud_index]} "
    f"({fraud.probabilities[fraud_index] * 100:.2f}%)"
)

print(f"Decision time: {result.evaluation_time_ms:.1f} ms")