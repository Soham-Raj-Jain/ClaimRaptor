import os
import json
import tempfile

import streamlit as st
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

st.set_page_config(
    page_title="ClaimRaptor",
    page_icon="🦖",
    layout="wide",
)

st.title("🦖 ClaimRaptor")
st.subheader("Evidence-grounded insurance decisions with NDI + Drex")

st.write(
    "Upload an insurance claim packet. "
    "NDI extracts the evidence and Drex makes the decision."
)

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

uploaded_file = st.file_uploader(
    "Upload claim PDF",
    type=["pdf"]
)

if uploaded_file is not None:

    st.success(f"Loaded: {uploaded_file.name}")

    if st.button("Analyze Claim", type="primary"):

        with st.spinner("ClaimRaptor is analyzing the claim..."):

            # Save uploaded PDF temporarily
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".pdf"
            ) as temp_file:

                temp_file.write(uploaded_file.getvalue())
                temp_path = temp_file.name

            with NaceClient(api_key=api_key) as client:

                # Upload to NDI
                ndi_file = client.documents.upload(
                    temp_path
                )

                # Parse
                parse_job = client.documents.parse(
                    ndi_file.as_source(),
                    output={"formats": ["markdown"]},
                    wait_seconds=60,
                )

                if parse_job.status != "succeeded":
                    parse_job = client.jobs.wait(
                        parse_job.job_id
                    )

                # Extract structured facts
                extract_job = client.documents.extract(
                    ParseResultSource(
                        job_id=parse_job.job_id
                    ),
                    schema=schema,
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

                state = json.dumps(
                    claim_data,
                    indent=2
                )

                # Drex decision
                result = client.system_one(
                    state=state,
                    questions={

                        "covered": Noul(
                            instructions=(
                                "Based only on these structured "
                                "insurance claim facts, is this "
                                "claim covered?"
                            )
                        ),

                        "evidence_sufficient": Noul(
                            instructions=(
                                "Is there enough reliable evidence "
                                "to automatically make a claim decision?"
                            )
                        ),

                        "action": Choice(
                            instructions=(
                                "What should happen to this "
                                "insurance claim?"
                            ),
                            criteria={
                                "approve": (
                                    "The claim is covered and "
                                    "evidence is sufficient."
                                ),

                                "manual_review": (
                                    "Important information is missing, "
                                    "ambiguous, uncertain, or conflicting."
                                ),

                                "deny": (
                                    "The claim is clearly not covered."
                                ),
                            },
                        ),

                        "fraud_risk": Score(
                            instructions=(
                                "Rate fraud risk only when there are "
                                "actual contradictions, suspicious "
                                "evidence, deception indicators, or "
                                "material inconsistencies. Missing "
                                "documents alone should not imply fraud."
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

        action_name = action.choice.upper()
        action_confidence = (
            action.probabilities[action.choice]
            * 100
        )

        st.divider()

        st.header("Decision")

        if action.choice == "approve":
            st.success(
                f"✅ APPROVE — {action_confidence:.2f}%"
            )

        elif action.choice == "deny":
            st.error(
                f"❌ DENY — {action_confidence:.2f}%"
            )

        else:
            st.warning(
                f"⚠️ MANUAL REVIEW — "
                f"{action_confidence:.2f}%"
            )

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Coverage",
            f"{covered.noul * 100:.2f}% YES"
        )

        col2.metric(
            "Evidence sufficient",
            f"{evidence.noul * 100:.2f}% YES"
        )

        col3.metric(
            "Fraud risk",
            fraud.legend[fraud_index]
        )

        col4.metric(
            "Drex latency",
            f"{result.evaluation_time_ms:.1f} ms"
        )

        st.divider()

        st.subheader("NDI Extracted Evidence")

        st.json(claim_data)

        st.caption(
            f"Drex input tokens: "
            f"{result.usage.input_tokens}"
        )