import os
import json
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("DEEPINFRA_API_KEY")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepinfra.com/v1/openai",
)

claim_data = {
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
}

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
ambiguous, or conflicting.

deny:
There is enough evidence and the claim is
clearly not covered.

Claim:

{json.dumps(claim_data, indent=2)}

Return ONLY:

approve

or

manual_review

or

deny
"""

start = time.perf_counter()

response = client.chat.completions.create(
    model="Qwen/Qwen3.8-27B",
    messages=[
        {
            "role": "user",
            "content": prompt,
        }
    ],
    temperature=0,
    max_tokens=10,

    # DeepInfra-specific parameter:
    extra_body={
        "reasoning_effort": "none"
    },
)

latency_ms = (
    time.perf_counter() - start
) * 1000

answer = (
    response.choices[0]
    .message.content
    .strip()
    .lower()
)

print("\n=== DEEPINFRA TEST ===")
print("Decision:", answer)
print(f"Latency: {latency_ms:.1f} ms")

if response.usage:
    print(
        "Input tokens:",
        response.usage.prompt_tokens
    )

    print(
        "Output tokens:",
        response.usage.completion_tokens
    )