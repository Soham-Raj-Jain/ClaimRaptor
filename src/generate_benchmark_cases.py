import json
import os


cases = []

POLICY_RULES = {
    "collision_covered": True,
    "coverage_requires_active_policy": True,
    "mechanical_failure_excluded": True,
    "wear_and_tear_excluded": True,
    "intentional_damage_excluded": True,
}


def add_case(
    claim_id,
    expected_action,
    reason,
    policy_start,
    policy_end,
    incident_date,
    damage_type,
    repair_cost,
    deductible,
    police_report,
    photos,
    conflicting_information,
):
    cases.append({
        "claim_id": claim_id,
        "expected_action": expected_action,
        "reason": reason,
        "data": {
            "policy_rules": POLICY_RULES,
            "claim_number": claim_id,
            "policy_number": f"POL-{claim_id}",
            "policy_start_date": policy_start,
            "policy_expiration_date": policy_end,
            "incident_date": incident_date,
            "damage_type": damage_type,
            "repair_cost": repair_cost,
            "collision_deductible": deductible,
            "police_report_submitted": police_report,
            "photos_submitted": photos,
            "conflicting_information": conflicting_information,
        },
    })


# ============================================================
# APPROVE CASES
# ============================================================

add_case(
    "BENCH-001",
    "approve",
    "Active policy, covered collision, complete evidence.",
    "January 1, 2026",
    "December 31, 2026",
    "March 15, 2026",
    "collision",
    4200,
    1000,
    True,
    True,
    False,
)

add_case(
    "BENCH-002",
    "approve",
    "Active policy and well-documented rear-end collision.",
    "January 1, 2026",
    "December 31, 2026",
    "July 8, 2026",
    "rear-end collision",
    6500,
    1000,
    True,
    True,
    False,
)

add_case(
    "BENCH-003",
    "approve",
    "Incident occurred one day after policy started with complete evidence.",
    "April 1, 2026",
    "December 31, 2026",
    "April 2, 2026",
    "collision",
    2800,
    500,
    True,
    True,
    False,
)

add_case(
    "BENCH-004",
    "approve",
    "Incident occurred on final active policy day.",
    "January 1, 2026",
    "September 30, 2026",
    "September 30, 2026",
    "collision",
    5100,
    1000,
    True,
    True,
    False,
)

add_case(
    "BENCH-005",
    "approve",
    "Low-cost covered collision with supporting evidence.",
    "January 1, 2026",
    "December 31, 2026",
    "February 12, 2026",
    "minor parking collision",
    1800,
    500,
    True,
    True,
    False,
)

add_case(
    "BENCH-006",
    "approve",
    "High repair cost but otherwise clearly covered.",
    "January 1, 2026",
    "December 31, 2026",
    "August 21, 2026",
    "multi-vehicle collision",
    18000,
    1500,
    True,
    True,
    False,
)

add_case(
    "BENCH-007",
    "approve",
    "Covered side-impact collision with complete documentation.",
    "March 1, 2026",
    "December 31, 2026",
    "June 4, 2026",
    "side-impact collision",
    7300,
    1000,
    True,
    True,
    False,
)

add_case(
    "BENCH-008",
    "approve",
    "Covered collision with photos and police documentation.",
    "January 1, 2026",
    "November 30, 2026",
    "November 10, 2026",
    "front bumper collision",
    3600,
    750,
    True,
    True,
    False,
)

add_case(
    "BENCH-009",
    "approve",
    "Active policy and clear accidental collision.",
    "February 1, 2026",
    "December 31, 2026",
    "May 14, 2026",
    "accidental collision",
    9200,
    1000,
    True,
    True,
    False,
)

add_case(
    "BENCH-010",
    "approve",
    "Complete evidence and no inconsistencies.",
    "January 1, 2026",
    "December 31, 2026",
    "October 20, 2026",
    "collision",
    5400,
    1000,
    True,
    True,
    False,
)


# ============================================================
# DENY CASES
# ============================================================

add_case(
    "BENCH-011",
    "deny",
    "Incident occurred after policy expiration.",
    "January 1, 2026",
    "June 30, 2026",
    "October 10, 2026",
    "collision",
    4000,
    1000,
    True,
    True,
    False,
)

add_case(
    "BENCH-012",
    "deny",
    "Incident occurred before policy began.",
    "June 1, 2026",
    "December 31, 2026",
    "May 20, 2026",
    "collision",
    3000,
    1000,
    True,
    True,
    False,
)

add_case(
    "BENCH-013",
    "deny",
    "Mechanical failure is excluded from collision coverage.",
    "January 1, 2026",
    "December 31, 2026",
    "August 5, 2026",
    "normal mechanical failure",
    6200,
    1000,
    True,
    True,
    False,
)

add_case(
    "BENCH-014",
    "deny",
    "Normal wear and tear is excluded.",
    "January 1, 2026",
    "December 31, 2026",
    "April 11, 2026",
    "normal wear and tear",
    2200,
    500,
    True,
    True,
    False,
)

add_case(
    "BENCH-015",
    "deny",
    "Intentional damage is excluded.",
    "January 1, 2026",
    "December 31, 2026",
    "September 7, 2026",
    "intentional damage caused by policyholder",
    7500,
    1000,
    True,
    True,
    False,
)

add_case(
    "BENCH-016",
    "deny",
    "Claim occurred months after policy expiration.",
    "January 1, 2025",
    "December 31, 2025",
    "July 5, 2026",
    "collision",
    5700,
    1000,
    True,
    True,
    False,
)

add_case(
    "BENCH-017",
    "deny",
    "Claim clearly identifies uncovered engine breakdown.",
    "January 1, 2026",
    "December 31, 2026",
    "June 19, 2026",
    "engine breakdown from mechanical failure",
    8400,
    1000,
    True,
    True,
    False,
)

add_case(
    "BENCH-018",
    "deny",
    "Policy expired the day before the incident.",
    "January 1, 2026",
    "September 14, 2026",
    "September 15, 2026",
    "collision",
    4900,
    1000,
    True,
    True,
    False,
)

add_case(
    "BENCH-019",
    "deny",
    "Damage described as routine deterioration rather than collision.",
    "January 1, 2026",
    "December 31, 2026",
    "March 9, 2026",
    "routine deterioration",
    2600,
    500,
    True,
    True,
    False,
)

add_case(
    "BENCH-020",
    "deny",
    "Intentional vehicle damage is explicitly excluded.",
    "January 1, 2026",
    "December 31, 2026",
    "November 2, 2026",
    "intentional self-inflicted vehicle damage",
    11000,
    1000,
    True,
    True,
    False,
)


# ============================================================
# MANUAL REVIEW CASES
# ============================================================

add_case(
    "BENCH-021",
    "manual_review",
    "Cause of damage is unknown and supporting evidence is missing.",
    "January 1, 2026",
    "December 31, 2026",
    "June 10, 2026",
    "unknown bumper damage",
    4100,
    1000,
    False,
    False,
    True,
)

add_case(
    "BENCH-022",
    "manual_review",
    "Photos are missing and claim contains conflicting information.",
    "January 1, 2026",
    "December 31, 2026",
    "July 22, 2026",
    "possible collision",
    5300,
    1000,
    True,
    False,
    True,
)

add_case(
    "BENCH-023",
    "manual_review",
    "Claim has incomplete documentation and uncertain cause.",
    "January 1, 2026",
    "December 31, 2026",
    "August 2, 2026",
    "uncertain vehicle damage",
    6900,
    1000,
    False,
    True,
    True,
)

add_case(
    "BENCH-024",
    "manual_review",
    "Conflicting information requires human verification.",
    "January 1, 2026",
    "December 31, 2026",
    "September 4, 2026",
    "collision",
    8300,
    1000,
    True,
    True,
    True,
)

add_case(
    "BENCH-025",
    "manual_review",
    "No police report or photos are available.",
    "January 1, 2026",
    "December 31, 2026",
    "October 3, 2026",
    "reported collision",
    3700,
    500,
    False,
    False,
    False,
)

add_case(
    "BENCH-026",
    "manual_review",
    "Evidence conflicts even though the policy is active.",
    "January 1, 2026",
    "December 31, 2026",
    "May 18, 2026",
    "collision",
    12000,
    1500,
    True,
    True,
    True,
)

add_case(
    "BENCH-027",
    "manual_review",
    "Damage cause cannot be established from submitted evidence.",
    "January 1, 2026",
    "December 31, 2026",
    "March 27, 2026",
    "undetermined damage",
    2400,
    500,
    False,
    True,
    False,
)

add_case(
    "BENCH-028",
    "manual_review",
    "Only a repair estimate exists and incident evidence is incomplete.",
    "January 1, 2026",
    "December 31, 2026",
    "February 8, 2026",
    "possible parking collision",
    4600,
    1000,
    False,
    False,
    False,
)

add_case(
    "BENCH-029",
    "manual_review",
    "Reported collision details materially conflict.",
    "January 1, 2026",
    "December 31, 2026",
    "November 11, 2026",
    "collision with conflicting accounts",
    9800,
    1000,
    True,
    True,
    True,
)

add_case(
    "BENCH-030",
    "manual_review",
    "Claim is potentially covered but evidence is insufficient.",
    "January 1, 2026",
    "December 31, 2026",
    "April 30, 2026",
    "possible collision",
    5800,
    1000,
    False,
    False,
    True,
)


# ============================================================
# SAVE
# ============================================================

os.makedirs(
    "data",
    exist_ok=True,
)

output_path = "data/benchmark_cases.json"

with open(
    output_path,
    "w",
    encoding="utf-8",
) as file:
    json.dump(
        cases,
        file,
        indent=2,
    )


print(
    f"Created {len(cases)} benchmark cases."
)

print(
    f"Saved to {output_path}"
)

print(
    "\nDistribution:"
)

for action in [
    "approve",
    "deny",
    "manual_review",
]:
    count = sum(
        1
        for case in cases
        if case["expected_action"] == action
    )

    print(
        f"{action}: {count}"
    )