#!/usr/bin/env python3
"""
Deterministic synthetic-data generator for an academic-integrity case-management system.

All records are synthetic. Similarity scores are screening signals, not proof of misconduct.
Benchmark ground truth is written separately from operational CSVs.

Outputs:
  data/generated/*.csv
  data/ground_truth/ground_truth.csv
  data/validation/validation_summary.json
  data/validation/source_manifest.json

The summary contains checksums for CSV artifacts. The manifest additionally contains the
final summary checksum. Neither file attempts to contain its own checksum.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

STARTER_PROFILE = {
    "learners": 100, "instructors": 10, "reviewers": 10, "assessments": 10,
    "submissions": 500, "similarity_reports": 500, "similarity_flags": 50, "cases": 15,
}
FULL_PROFILE = {
    "learners": 3000, "instructors": 50, "reviewers": 30, "assessments": 100,
    "submissions": 10000, "similarity_reports": 10000, "similarity_flags": 1000, "cases": 300,
}
REQUIRED_ROLES = {
    "Learner", "Instructor", "Academic Administrator", "Support Staff",
    "Platform Administrator", "Case Reviewer", "Independent Appeal Reviewer",
}
OPERATIONAL_SCHEMAS = {
    "users": ["user_id", "username", "email", "role", "is_active", "created_at"],
    "learners": ["learner_id", "user_id", "full_name", "department", "enrollment_year"],
    "instructors": ["instructor_id", "user_id", "full_name", "department"],
    "reviewers": ["reviewer_id", "user_id", "full_name", "department", "specialization"],
    "assessments": ["assessment_id", "title", "course_code", "created_by_instructor_id", "max_score", "due_date"],
    "submissions": ["submission_id", "learner_id", "assessment_id", "submitted_at", "content_fingerprint", "status"],
    "similarity_reports": ["report_id", "target_submission_id", "matched_submission_id", "similarity_score", "generated_at", "algorithm_version"],
    "similarity_flags": ["flag_id", "report_id", "submission_id", "similarity_score", "severity", "flag_reason", "created_at"],
    "cases": ["case_id", "flag_id", "submission_id", "case_status", "created_at", "updated_at"],
    "reviewer_assignments": ["assignment_id", "case_id", "reviewer_id", "assigned_by_user_id", "assignment_role", "assigned_at", "is_active"],
    "evidence": ["evidence_id", "case_id", "evidence_type", "content_summary", "metadata_checksum", "added_by_user_id", "added_at", "version"],
    "decisions": ["decision_id", "case_id", "decision_maker_id", "finding", "sanction_recommended", "rationale_text", "decided_at"],
    "appeals": ["appeal_id", "case_id", "decision_id", "independent_reviewer_id", "appeal_reason", "appeal_status", "submitted_at", "review_completed_at", "review_outcome"],
    "audit_events": ["event_id", "actor_id", "event_type", "entity_type", "entity_id", "event_payload_json", "timestamp"],
}
GROUND_TRUTH_SCHEMA = [
    "report_id", "synthetic_pair_relationship", "synthetic_case_outcome", "is_synthetic_plagiarism",
]
DATA_DICTIONARY = {
    "content_fingerprint": "Deterministic identifier for synthetic placeholder content; not a hash of a persisted submission file.",
    "similarity_reports": "Pairwise screening reports. Similarity scores are signals for human review, not findings of misconduct.",
    "similarity_flags": "Flags selected only from reports with similarity score >= 15%; HIGH at >= 30%, otherwise MEDIUM.",
    "cases": "Formal case records with UNDER_INVESTIGATION, DECIDED, APPEALED, or CLOSED lifecycle states.",
    "ground_truth": {
        "file": "data/ground_truth/ground_truth.csv",
        "columns": {
            "report_id": "Corresponding operational similarity report ID",
            "synthetic_pair_relationship": "Synthetic benchmark relationship category",
            "synthetic_case_outcome": "Synthetic benchmark outcome category",
            "is_synthetic_plagiarism": "Synthetic benchmark boolean label stored as true/false text",
        },
        "policy": {
            "DIRECT_COPY": ["SERIOUS_VIOLATION", "true"],
            "COLLABORATION": ["SERIOUS_VIOLATION or WARNING", "true"],
            "TEMPLATED_CODE": ["WARNING or NO_VIOLATION", "true or false"],
            "CITATIONS_EXCLUDED": ["NO_VIOLATION", "false"],
            "ORIGINAL": ["NO_VIOLATION", "false"],
        },
        "description": "Benchmark-only labels; never included in operational CSVs and never inferred from similarity scores.",
    },
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def iso(dt: datetime) -> str:
    return dt.isoformat()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate deterministic synthetic academic-integrity datasets.")
    p.add_argument(
        "--profile", choices=["starter", "full", "custom"], default="starter")
    p.add_argument("--seed", type=int, default=20261022)
    for arg, help_text in [
        ("learners", "Number of learners"), ("instructors", "Number of instructors"),
        ("reviewers", "Number of reviewers"), ("assessments", "Number of assessments"),
        ("submissions", "Number of submissions"), ("reports",
                                                   "Number of similarity reports"),
        ("flags", "Number of similarity flags"), ("cases", "Number of cases"),
    ]:
        p.add_argument(f"--{arg}", type=int, default=None, help=help_text)
    return p.parse_args()


def validate_counts(counts: dict[str, int]) -> None:
    required = set(STARTER_PROFILE)
    if set(counts) != required:
        raise ValueError(f"Count keys must be exactly {sorted(required)}.")
    for name, value in counts.items():
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"Count for {name!r} must be a positive integer; got {value!r}.")
    if counts["reviewers"] < 3:
        raise ValueError(
            "At least 3 reviewers are required for independent appeal review.")
    n = counts["submissions"]
    max_pairs = n * (n - 1) // 2
    if counts["similarity_reports"] > max_pairs:
        raise ValueError(
            f"Reports ({counts['similarity_reports']}) exceed {max_pairs} unique pairs.")
    if counts["similarity_flags"] > counts["similarity_reports"]:
        raise ValueError("Flags cannot exceed reports.")
    if counts["cases"] > counts["similarity_flags"]:
        raise ValueError("Cases cannot exceed flags.")


def counts_from_args(args: argparse.Namespace) -> dict[str, int]:
    if args.profile == "starter":
        return STARTER_PROFILE.copy()
    if args.profile == "full":
        return FULL_PROFILE.copy()
    mapping = {
        "learners": args.learners, "instructors": args.instructors, "reviewers": args.reviewers,
        "assessments": args.assessments, "submissions": args.submissions,
        "similarity_reports": args.reports, "similarity_flags": args.flags, "cases": args.cases,
    }
    missing = [k for k, v in mapping.items() if v is None]
    if missing:
        raise ValueError("Custom profile requires: " + ", ".join(missing))
    validate_counts(mapping)
    return mapping


def rank_to_pair(rank: int, n: int) -> tuple[int, int]:
    """Map a rank in [0, n*(n-1)//2) to one unique pair i < j."""
    low, high, i = 0, n - 2, 0
    while low <= high:
        mid = (low + high) // 2
        offset = mid * n - mid * (mid + 1) // 2
        if offset <= rank:
            i, low = mid, mid + 1
        else:
            high = mid - 1
    offset = i * n - i * (i + 1) // 2
    return i, i + 1 + rank - offset


def make_ground_truth(rng: random.Random, report_id: str) -> dict[str, str]:
    """A documented, score-independent policy with valid label combinations."""
    category = rng.choice(["DIRECT_COPY", "COLLABORATION",
                          "TEMPLATED_CODE", "CITATIONS_EXCLUDED", "ORIGINAL"])
    if category == "DIRECT_COPY":
        outcome, plagiarism = "SERIOUS_VIOLATION", "true"
    elif category == "COLLABORATION":
        outcome, plagiarism = rng.choice(
            [("SERIOUS_VIOLATION", "true"), ("WARNING", "true")])
    elif category == "TEMPLATED_CODE":
        outcome, plagiarism = rng.choice(
            [("WARNING", "true"), ("WARNING", "false"), ("NO_VIOLATION", "false")])
    else:
        outcome, plagiarism = "NO_VIOLATION", "false"
    return {
        "report_id": report_id,
        "synthetic_pair_relationship": category,
        "synthetic_case_outcome": outcome,
        "is_synthetic_plagiarism": plagiarism,
    }


def generate_dataset(counts: dict[str, int], seed: int) -> dict[str, list[dict[str, Any]]]:
    validate_counts(counts)
    rng = random.Random(seed)
    base = datetime(2026, 1, 15, 8, tzinfo=timezone.utc)
    departments = ["Computer Science", "Data Science", "Electrical Engineering",
                   "Mechanical Engineering", "Business Analytics", "Health Informatics"]
    users: list[dict[str, Any]] = []
    learners: list[dict[str, Any]] = []
    instructors: list[dict[str, Any]] = []
    reviewers: list[dict[str, Any]] = []
    uid = 1

    def add_user(username: str, role: str, created: datetime) -> str:
        nonlocal uid
        user_id = f"USR-{uid:06d}"
        users.append({"user_id": user_id, "username": username, "email": f"{username}@academic.edu",
                      "role": role, "is_active": "true", "created_at": iso(created)})
        uid += 1
        return user_id

    admin_id = add_user(
        "admin_user_01", "Academic Administrator", base - timedelta(days=120))
    add_user("support_user_01", "Support Staff", base - timedelta(days=120))
    add_user("platform_admin_01", "Platform Administrator",
             base - timedelta(days=120))

    for i in range(1, counts["learners"] + 1):
        user_id = add_user(f"learner_{i:06d}",
                           "Learner", base - timedelta(days=30))
        learners.append({"learner_id": f"LRN-{i:06d}", "user_id": user_id,
                         "full_name": f"Synthetic Learner {i:06d}", "department": departments[i % len(departments)],
                         "enrollment_year": 2023 + i % 4})
    for i in range(1, counts["instructors"] + 1):
        user_id = add_user(
            f"instructor_{i:06d}", "Instructor", base - timedelta(days=60))
        instructors.append({"instructor_id": f"INS-{i:06d}", "user_id": user_id,
                            "full_name": f"Professor {i:06d}", "department": departments[i % len(departments)]})

    n_independent = max(1, counts["reviewers"] // 3)
    n_case = counts["reviewers"] - n_independent
    for i in range(1, n_case + 1):
        user_id = add_user(
            f"reviewer_{i:06d}", "Case Reviewer", base - timedelta(days=60))
        dept = departments[i % len(departments)]
        reviewers.append({"reviewer_id": f"REV-{i:06d}", "user_id": user_id,
                          "full_name": f"Case Reviewer {i:06d}", "department": dept,
                          "specialization": f"{dept} Ethics"})
    for i in range(1, n_independent + 1):
        user_id = add_user(
            f"ind_reviewer_{i:06d}", "Independent Appeal Reviewer", base - timedelta(days=60))
        dept = departments[i % len(departments)]
        reviewers.append({"reviewer_id": f"REV-IND-{i:06d}", "user_id": user_id,
                          "full_name": f"Independent Appeal Reviewer {i:06d}", "department": dept,
                          "specialization": "Appeals Adjudication"})

    assessments = []
    for i in range(1, counts["assessments"] + 1):
        instructor = instructors[(i - 1) % len(instructors)]
        created = base + timedelta(days=i % 10)
        assessments.append({"assessment_id": f"ASM-{i:06d}",
                            "title": f"Assessment {i:06d} - {instructor['department']} Assignment",
                            "course_code": f"{instructor['department'][:3].upper()}-{100 + i % 20}",
                            "created_by_instructor_id": instructor["instructor_id"], "max_score": "100.0",
                            "due_date": iso(created + timedelta(days=14))})

    submissions = []
    for i in range(1, counts["submissions"] + 1):
        sub_id = f"SUB-{i:06d}"
        assessment = assessments[(i - 1) % len(assessments)]
        submitted = datetime.fromisoformat(
            assessment["due_date"]) - timedelta(hours=rng.randint(1, 48))
        submissions.append({"submission_id": sub_id,
                            "learner_id": learners[(i - 1) % len(learners)]["learner_id"],
                            "assessment_id": assessment["assessment_id"], "submitted_at": iso(submitted),
                            "content_fingerprint": sha256_text(f"synthetic_submission_file_content_{sub_id}"),
                            "status": "SUBMITTED"})

    n = len(submissions)
    sampled_ranks = rng.sample(
        range(n * (n - 1) // 2), counts["similarity_reports"])
    reports, ground_truth = [], []
    for idx, rank in enumerate(sampled_ranks, 1):
        p1, p2 = rank_to_pair(rank, n)
        target, matched = submissions[p1], submissions[p2]
        score = round(rng.uniform(0, 99.5), 2)
        report_id = f"REP-{idx:06d}"
        reports.append({"report_id": report_id, "target_submission_id": target["submission_id"],
                        "matched_submission_id": matched["submission_id"], "similarity_score": f"{score:.2f}",
                        "generated_at": iso(datetime.fromisoformat(target["submitted_at"]) + timedelta(minutes=15)),
                        "algorithm_version": "v2.4.0"})
        ground_truth.append(make_ground_truth(rng, report_id))

    eligible = [r for r in reports if float(r["similarity_score"]) >= 15]
    if len(eligible) < counts["similarity_flags"]:
        raise ValueError(f"Only {len(eligible)} reports meet the >=15% flag threshold; "
                         f"{counts['similarity_flags']} requested. Try a different seed or more reports.")
    selected = rng.sample(eligible, counts["similarity_flags"])
    flags = []
    for i, report in enumerate(selected, 1):
        score = float(report["similarity_score"])
        flags.append({"flag_id": f"FLG-{i:06d}", "report_id": report["report_id"],
                      "submission_id": report["target_submission_id"], "similarity_score": report["similarity_score"],
                      "severity": "HIGH" if score >= 30 else "MEDIUM",
                      "flag_reason": f"Screening score {report['similarity_score']}% triggered human review",
                      "created_at": iso(datetime.fromisoformat(report["generated_at"]) + timedelta(hours=1))})

    case_reviewers = [r for r in reviewers if r["reviewer_id"].startswith(
        "REV-") and not r["reviewer_id"].startswith("REV-IND-")]
    independent_reviewers = [
        r for r in reviewers if r["reviewer_id"].startswith("REV-IND-")]
    cases, assignments, evidence, decisions, appeals, audit_events = [], [], [], [], [], []

    for i in range(1, counts["cases"] + 1):
        flag = flags[i - 1]
        case_id = f"CAS-{i:06d}"

        status = rng.choices(
            ["UNDER_INVESTIGATION", "DECIDED", "APPEALED", "CLOSED"],
            weights=[0.3, 0.3, 0.2, 0.2],
            k=1
        )[0]

        created = datetime.fromisoformat(
            flag["created_at"]) + timedelta(hours=2)

        # Prepare lifecycle timestamps.
        decided = created + timedelta(days=3)
        appeal_date = decided + timedelta(days=1)
        completed = appeal_date + \
            timedelta(days=2) if status == "CLOSED" else None

        # Keep the case updated timestamp consistent with its lifecycle.
        if status == "UNDER_INVESTIGATION":
            updated = created + timedelta(hours=3)
        elif status == "DECIDED":
            updated = decided
        elif status == "APPEALED":
            updated = appeal_date
        else:  # CLOSED
            updated = completed

        cases.append({
            "case_id": case_id,
            "flag_id": flag["flag_id"],
            "submission_id": flag["submission_id"],
            "case_status": status,
            "created_at": iso(created),
            "updated_at": iso(updated)
        })

        primary = case_reviewers[(i - 1) % len(case_reviewers)]

        assignments.append({
            "assignment_id": f"ASG-{i:06d}",
            "case_id": case_id,
            "reviewer_id": primary["reviewer_id"],
            "assigned_by_user_id": admin_id,
            "assignment_role": "PRIMARY_INVESTIGATOR",
            "assigned_at": iso(created + timedelta(hours=1)),
            "is_active": "true"
        })

        summary = (
            f"Synthetic evidence record for Case {case_id} "
            "- Similarity screening excerpt."
        )

        evidence.append({
            "evidence_id": f"EVD-{i:06d}",
            "case_id": case_id,
            "evidence_type": "SIMILARITY_MATCH_EXCERPT",
            "content_summary": summary,
            "metadata_checksum": sha256_text(summary),
            "added_by_user_id": primary["user_id"],
            "added_at": iso(created + timedelta(hours=3)),
            "version": 1
        })

        if status in {"DECIDED", "APPEALED", "CLOSED"}:
            decision_id = f"DEC-{i:06d}"

            finding = rng.choice([
                "ACADEMIC_MISCONDUCT_FOUND",
                "NO_MISCONDUCT_FOUND",
                "INSUFFICIENT_EVIDENCE"
            ])

            decisions.append({
                "decision_id": decision_id,
                "case_id": case_id,
                "decision_maker_id": primary["reviewer_id"],
                "finding": finding,
                "sanction_recommended": (
                    "ZERO_ON_ASSIGNMENT"
                    if finding == "ACADEMIC_MISCONDUCT_FOUND"
                    else "NONE"
                ),
                "rationale_text": (
                    "Synthetic example of a documented human-review rationale."
                ),
                "decided_at": iso(decided)
            })

            if status in {"APPEALED", "CLOSED"}:
                independent = independent_reviewers[
                    (i - 1) % len(independent_reviewers)
                ]

                is_closed = status == "CLOSED"

                appeals.append({
                    "appeal_id": f"APL-{i:06d}",
                    "case_id": case_id,
                    "decision_id": decision_id,
                    "independent_reviewer_id": independent["reviewer_id"],
                    "appeal_reason": (
                        "Disputing findings based on shared course-template code."
                    ),
                    "appeal_status": (
                        "CLOSED" if is_closed else "UNDER_INDEPENDENT_REVIEW"
                    ),
                    "submitted_at": iso(appeal_date),
                    "review_completed_at": iso(completed) if completed else "",
                    "review_outcome": (
                        rng.choice(["UPHELD", "OVERTURNED", "REMANDED"])
                        if is_closed else ""
                    )
                })

        audit_events.append({
            "event_id": f"EVT-{i:06d}",
            "actor_id": admin_id,
            "event_type": "CASE_CREATED",
            "entity_type": "CASE",
            "entity_id": case_id,
            "event_payload_json": json.dumps({
                "case_id": case_id,
                "flag_id": flag["flag_id"]
            }, sort_keys=True),
            "timestamp": iso(created)
        })
    return {
        "users": users,
        "learners": learners,
        "instructors": instructors,
        "reviewers": reviewers,
        "assessments": assessments,
        "submissions": submissions,
        "similarity_reports": reports,
        "similarity_flags": flags,
        "cases": cases,
        "reviewer_assignments": assignments,
        "evidence": evidence,
        "decisions": decisions,
        "appeals": appeals,
        "audit_events": audit_events,
        "ground_truth": ground_truth
    }


def validate_ground_truth(rows: list[dict[str, Any]]) -> list[str]:
    errors = []
    valid = {
        ("DIRECT_COPY", "SERIOUS_VIOLATION", "true"),
        ("COLLABORATION", "SERIOUS_VIOLATION", "true"),
        ("COLLABORATION", "WARNING", "true"),
        ("TEMPLATED_CODE", "WARNING", "true"),
        ("TEMPLATED_CODE", "WARNING", "false"),
        ("TEMPLATED_CODE", "NO_VIOLATION", "false"),
        ("CITATIONS_EXCLUDED", "NO_VIOLATION", "false"),
        ("ORIGINAL", "NO_VIOLATION", "false"),
    }
    for row in rows:
        combo = (row["synthetic_pair_relationship"],
                 row["synthetic_case_outcome"], row["is_synthetic_plagiarism"])
        if combo not in valid:
            errors.append(
                f"Invalid ground-truth combination for {row['report_id']}: {combo}")
    return errors


def validate_dataset(data: dict[str, list[dict[str, Any]]], counts: dict[str, int], profile: str) -> list[str]:
    errors: list[str] = []
    expected = counts.copy()
    for key in counts:
        actual_key = {"similarity_reports": "similarity_reports",
                      "similarity_flags": "similarity_flags"}.get(key, key)
        actual = len(data[actual_key])
        if actual != expected[key]:
            errors.append(
                f"Count mismatch for {key}: got {actual}, expected {expected[key]}")
    expected_users = 3 + counts["learners"] + \
        counts["instructors"] + counts["reviewers"]
    if len(data["users"]) != expected_users:
        errors.append(
            f"Users count mismatch: got {len(data['users'])}, expected {expected_users}")
    for entity, rows in data.items():
        pk = {
            "users": "user_id", "learners": "learner_id", "instructors": "instructor_id", "reviewers": "reviewer_id",
            "assessments": "assessment_id", "submissions": "submission_id", "similarity_reports": "report_id",
            "similarity_flags": "flag_id", "cases": "case_id", "reviewer_assignments": "assignment_id",
            "evidence": "evidence_id", "decisions": "decision_id", "appeals": "appeal_id", "audit_events": "event_id",
            "ground_truth": "report_id",
        }[entity]
        vals = [r[pk] for r in rows]
        if len(vals) != len(set(vals)):
            errors.append(f"Duplicate primary key in {entity}.{pk}")
    sets = {k: {r[pk] for r in data[k]} for k, pk in [
        ("users", "user_id"), ("learners", "learner_id"), ("instructors",
                                                           "instructor_id"), ("reviewers", "reviewer_id"),
        ("assessments", "assessment_id"), ("submissions",
                                           "submission_id"), ("similarity_reports", "report_id"),
        ("similarity_flags", "flag_id"), ("cases", "case_id"), ("decisions", "decision_id")]}
    fk_checks = [
        ("learners.user_id", all(r["user_id"]
         in sets["users"] for r in data["learners"])),
        ("instructors.user_id", all(
            r["user_id"] in sets["users"] for r in data["instructors"])),
        ("reviewers.user_id", all(
            r["user_id"] in sets["users"] for r in data["reviewers"])),
        ("assessments.created_by_instructor_id", all(
            r["created_by_instructor_id"] in sets["instructors"] for r in data["assessments"])),
        ("submissions.learner_id", all(
            r["learner_id"] in sets["learners"] for r in data["submissions"])),
        ("submissions.assessment_id", all(
            r["assessment_id"] in sets["assessments"] for r in data["submissions"])),
        ("reports.target_submission_id", all(
            r["target_submission_id"] in sets["submissions"] for r in data["similarity_reports"])),
        ("reports.matched_submission_id", all(
            r["matched_submission_id"] in sets["submissions"] for r in data["similarity_reports"])),
        ("flags.report_id", all(
            r["report_id"] in sets["similarity_reports"] for r in data["similarity_flags"])),
        ("flags.submission_id", all(
            r["submission_id"] in sets["submissions"] for r in data["similarity_flags"])),
        ("cases.flag_id", all(
            r["flag_id"] in sets["similarity_flags"] for r in data["cases"])),
        ("cases.submission_id", all(
            r["submission_id"] in sets["submissions"] for r in data["cases"])),
        ("assignments.case_id", all(
            r["case_id"] in sets["cases"] for r in data["reviewer_assignments"])),
        ("assignments.reviewer_id", all(
            r["reviewer_id"] in sets["reviewers"] for r in data["reviewer_assignments"])),
        ("assignments.assigned_by_user_id", all(
            r["assigned_by_user_id"] in sets["users"] for r in data["reviewer_assignments"])),
        ("evidence.case_id", all(r["case_id"]
         in sets["cases"] for r in data["evidence"])),
        ("evidence.added_by_user_id", all(
            r["added_by_user_id"] in sets["users"] for r in data["evidence"])),
        ("decisions.case_id", all(
            r["case_id"] in sets["cases"] for r in data["decisions"])),
        ("decisions.decision_maker_id", all(
            r["decision_maker_id"] in sets["reviewers"] for r in data["decisions"])),
        ("appeals.case_id", all(r["case_id"] in sets["cases"]
         for r in data["appeals"])),
        ("appeals.decision_id", all(r["decision_id"] in {
         d["decision_id"] for d in data["decisions"]} for r in data["appeals"])),
        ("appeals.independent_reviewer_id", all(
            r["independent_reviewer_id"] in sets["reviewers"] for r in data["appeals"])),
        ("audit_events.actor_id", all(
            r["actor_id"] in sets["users"] for r in data["audit_events"])),
    ]
    errors.extend(
        f"Foreign-key failure: {name}" for name, ok in fk_checks if not ok)
    report_ids = sets["similarity_reports"]
    if {r["report_id"] for r in data["ground_truth"]} != report_ids:
        errors.append(
            "Ground-truth report IDs do not exactly match report IDs.")
    if validate_ground_truth(data["ground_truth"]):
        errors.extend(validate_ground_truth(data["ground_truth"]))
    roles = {u["role"] for u in data["users"]}
    if not REQUIRED_ROLES.issubset(roles):
        errors.append(
            f"Missing required roles: {sorted(REQUIRED_ROLES - roles)}")
    user_role = {u["user_id"]: u["role"] for u in data["users"]}
    reviewer_user = {r["reviewer_id"]: r["user_id"] for r in data["reviewers"]}
    case_assignment: dict[str, list[dict[str, Any]]] = {}
    for a in data["reviewer_assignments"]:
        case_assignment.setdefault(a["case_id"], []).append(a)
        if user_role.get(reviewer_user.get(a["reviewer_id"])) != "Case Reviewer":
            errors.append(
                f"Assignment {a['assignment_id']} is not assigned to a Case Reviewer.")
    reports_by_id = {r["report_id"]: r for r in data["similarity_reports"]}
    for r in data["similarity_reports"]:
        score = float(r["similarity_score"])
        if not 0 <= score <= 100:
            errors.append(
                f"Report {r['report_id']} has score outside [0,100].")
    flags_by_id = {f["flag_id"]: f for f in data["similarity_flags"]}
    for f in data["similarity_flags"]:
        report = reports_by_id.get(f["report_id"])
        if not report:
            continue
        score = float(report["similarity_score"])
        if score < 15 or f["submission_id"] != report["target_submission_id"]:
            errors.append(
                f"Flag {f['flag_id']} violates threshold or target-submission consistency.")
        if float(f["similarity_score"]) != score:
            errors.append(
                f"Flag {f['flag_id']} score differs from its source report.")
        if f["severity"] != ("HIGH" if score >= 30 else "MEDIUM"):
            errors.append(f"Flag {f['flag_id']} has inconsistent severity.")
    pairs = set()
    for r in data["similarity_reports"]:
        a, b = r["target_submission_id"], r["matched_submission_id"]
        if a == b:
            errors.append(
                f"Report {r['report_id']} compares a submission with itself.")
        pair = tuple(sorted((a, b)))
        if pair in pairs:
            errors.append(
                f"Duplicate unordered pair in report {r['report_id']}.")
        pairs.add(pair)
    decisions_by_case: dict[str, list[dict[str, Any]]] = {}
    appeals_by_case: dict[str, list[dict[str, Any]]] = {}
    for d in data["decisions"]:
        decisions_by_case.setdefault(d["case_id"], []).append(d)
        if user_role.get(reviewer_user.get(d["decision_maker_id"])) != "Case Reviewer":
            errors.append(
                f"Decision {d['decision_id']} maker is not a Case Reviewer.")
    for a in data["appeals"]:
        appeals_by_case.setdefault(a["case_id"], []).append(a)
    allowed_statuses = {"UNDER_INVESTIGATION", "DECIDED", "APPEALED", "CLOSED"}
    decisions_by_id = {d["decision_id"]: d for d in data["decisions"]}
    for c in data["cases"]:
        cid, status = c["case_id"], c["case_status"]
        ds, aps = decisions_by_case.get(cid, []), appeals_by_case.get(cid, [])
        if status not in allowed_statuses:
            errors.append(f"Unknown case status {status!r} for {cid}.")
            continue
        expected_dec = 0 if status == "UNDER_INVESTIGATION" else 1
        expected_appeal = 1 if status in {"APPEALED", "CLOSED"} else 0
        if len(ds) != expected_dec or len(aps) != expected_appeal:
            errors.append(
                f"Lifecycle cardinality mismatch for {cid} ({status}): {len(ds)} decisions, {len(aps)} appeals.")
            continue
        flag = flags_by_id.get(c["flag_id"])
        if not flag or c["submission_id"] != flag["submission_id"]:
            errors.append(
                f"Case {cid} submission does not match its referenced flag.")
        assignments = case_assignment.get(cid, [])
        if len(assignments) != 1 or assignments[0]["assignment_role"] != "PRIMARY_INVESTIGATOR":
            errors.append(
                f"Case {cid} must have exactly one primary investigator assignment.")
        if aps:
            appeal = aps[0]
            decision = ds[0]
            referenced_decision = decisions_by_id.get(appeal["decision_id"])
            if not referenced_decision or referenced_decision["case_id"] != cid or appeal["decision_id"] != decision["decision_id"]:
                errors.append(
                    f"Appeal for {cid} does not reference that case's decision.")
            primary_id = assignments[0]["reviewer_id"] if assignments else None
            independent_id = appeal["independent_reviewer_id"]
            if user_role.get(reviewer_user.get(independent_id)) != "Independent Appeal Reviewer":
                errors.append(
                    f"Appeal reviewer for {cid} lacks Independent Appeal Reviewer role.")
            if independent_id in {primary_id, decision["decision_maker_id"]}:
                errors.append(f"Appeal reviewer is not independent for {cid}.")
            if status == "APPEALED":
                if appeal["appeal_status"] != "UNDER_INDEPENDENT_REVIEW" or appeal["review_completed_at"] or appeal["review_outcome"]:
                    errors.append(
                        f"Appealed case {cid} has inconsistent pending appeal fields.")
            if status == "CLOSED":
                if appeal["appeal_status"] != "CLOSED" or not appeal["review_completed_at"] or appeal["review_outcome"] not in {"UPHELD", "OVERTURNED", "REMANDED"}:
                    errors.append(
                        f"Closed case {cid} lacks a valid completed appeal.")
    for entity, rows in data.items():
        if entity == "ground_truth":
            continue
        if any(k.startswith("synthetic_") or k == "is_synthetic_plagiarism" for row in rows for k in row):
            errors.append(
                f"Ground-truth field leaked into operational entity {entity}.")
    # Derived entity cardinalities
    if len(data["reviewer_assignments"]) != counts["cases"]:
        errors.append("Reviewer assignments count must equal case count.")
    if len(data["evidence"]) != counts["cases"]:
        errors.append("Evidence count must equal case count.")
    if len(data["decisions"]) != sum(c["case_status"] != "UNDER_INVESTIGATION" for c in data["cases"]):
        errors.append(
            "Decision count does not match lifecycle-derived expectation.")
    if len(data["appeals"]) != sum(c["case_status"] in {"APPEALED", "CLOSED"} for c in data["cases"]):
        errors.append(
            "Appeal count does not match lifecycle-derived expectation.")
    if len(data["audit_events"]) != counts["cases"]:
        errors.append("Audit event count must equal case count.")
    return errors


def write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def artifact_checksums(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            result[path.relative_to(root).as_posix()] = sha256_bytes(
                path.read_bytes())
    return result


def safe_replace(staged: dict[str, Path], targets: dict[str, Path], data_root: Path) -> None:
    """Move old targets to backup, install staged targets, and restore on any failure."""
    backup = Path(tempfile.mkdtemp(
        prefix=".backup_generate_",
        dir=data_root,
    ))
    existed = {name: path.exists() for name, path in targets.items()}
    backed_up: set[str] = set()
    installed: set[str] = set()
    try:
        # Complete all backups before modifying any final target.
        for name, target in targets.items():
            if existed[name]:
                shutil.move(str(target), str(backup / name))
                backed_up.add(name)
        for name, target in targets.items():
            shutil.move(str(staged[name]), str(target))
            installed.add(name)
    except Exception as original:
        restore_errors = []
        for name, target in targets.items():
            try:
                if name in installed and target.exists():
                    shutil.rmtree(
                        target) if target.is_dir() else target.unlink()
                if name in backed_up:
                    old = backup / name
                    if old.exists():
                        if target.exists():
                            shutil.rmtree(
                                target) if target.is_dir() else target.unlink()
                        shutil.move(str(old), str(target))
                    else:
                        restore_errors.append(f"backup for {name} is missing")
                elif not existed[name] and target.exists():
                    shutil.rmtree(
                        target) if target.is_dir() else target.unlink()
            except Exception as restore_error:
                restore_errors.append(f"{name}: {restore_error}")
        if restore_errors:
            raise RuntimeError(
                f"Replacement failed: {original}; rollback ALSO failed: {'; '.join(restore_errors)}") from original
        # Verify old targets restored and previously absent targets absent.
        for name, target in targets.items():
            if existed[name] and not target.exists():
                restore_errors.append(
                    f"{name} was expected to be restored but is missing")
            if not existed[name] and target.exists():
                restore_errors.append(
                    f"{name} should not exist after rollback")
        if restore_errors:
            raise RuntimeError(
                f"Replacement failed: {original}; rollback verification failed: {'; '.join(restore_errors)}") from original
        raise RuntimeError(
            f"Replacement failed; rollback completed and verified. Original error: {original}") from original
    finally:
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)


def write_outputs(data: dict[str, list[dict[str, Any]]], summary: dict[str, Any], manifest_base: dict[str, Any], project_root: Path) -> None:
    data_root = project_root / "data"
    targets = {
        "generated": data_root / "generated",
        "ground_truth": data_root / "ground_truth",
        "validation": data_root / "validation",
    }
    staging_root = Path(tempfile.mkdtemp(
        prefix=".staging_generate_", dir=data_root))
    try:
        staged = {name: staging_root / name for name in targets}
        for path in staged.values():
            path.mkdir(parents=True, exist_ok=True)
        for entity, columns in OPERATIONAL_SCHEMAS.items():
            write_csv(staged["generated"] /
                      f"{entity}.csv", columns, data[entity])
        write_csv(staged["ground_truth"] / "ground_truth.csv",
                  GROUND_TRUTH_SCHEMA, data["ground_truth"])
        csv_checksums = {
            f"generated/{p.name}": sha256_bytes(p.read_bytes())
            for p in sorted(staged["generated"].glob("*.csv"))
        }
        csv_checksums["ground_truth/ground_truth.csv"] = sha256_bytes(
            (staged["ground_truth"] / "ground_truth.csv").read_bytes())
        summary["file_checksums"] = csv_checksums
        summary_path = staged["validation"] / "validation_summary.json"
        summary_path.write_text(json.dumps(
            summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest = dict(manifest_base)
        manifest["artifact_checksums"] = dict(csv_checksums)
        manifest["artifact_checksums"]["validation/validation_summary.json"] = sha256_bytes(
            summary_path.read_bytes())
        manifest_path = staged["validation"] / "source_manifest.json"
        manifest_path.write_text(json.dumps(
            manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        safe_replace(staged, targets, data_root)
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)


def main() -> int:
    args = parse_args()
    try:
        counts = counts_from_args(args)
        data = generate_dataset(counts, args.seed)
        errors = validate_dataset(data, counts, args.profile)
        if errors:
            print("DATASET VALIDATION FAILED:", file=sys.stderr)
            for error in errors:
                print(f" - {error}", file=sys.stderr)
            return 1
        project_root = Path(__file__).resolve().parent.parent
        counts_out = {name: len(rows) for name, rows in data.items()}
        summary = {
            "profile": args.profile, "seed": args.seed, "status": "SUCCESS",
            "passed_all_checks": True, "counts": counts_out,
            "data_dictionary": DATA_DICTIONARY,
            "checks": ["exact counts", "primary keys", "foreign keys", "unique unordered pairs",
                       "flag thresholds/severity", "role coverage", "lifecycle/cardinality",
                       "reviewer independence", "ground-truth consistency/isolation"],
            "errors": [],
        }
        manifest = {
            "profile": args.profile, "seed": args.seed,
            "source_paths": {"generated_dir": "data/generated", "ground_truth_dir": "data/ground_truth",
                             "validation_dir": "data/validation"},
            "row_counts": counts_out,
            "operational_tables": sorted(OPERATIONAL_SCHEMAS),
            "ground_truth_table": "ground_truth",
        }
        (project_root / "data").mkdir(parents=True, exist_ok=True)
        write_outputs(data, summary, manifest, project_root)
        print("[+] Dataset generation and validation successful.")
        print(f"    Profile: {args.profile}; seed: {args.seed}")
        print(f"    Learners: {counts_out['learners']}; submissions: {counts_out['submissions']}; "
              f"reports: {counts_out['similarity_reports']}; flags: {counts_out['similarity_flags']}; "
              f"cases: {counts_out['cases']}")
        print(f"    Operational data: {project_root / 'data' / 'generated'}")
        print(
            f"    Ground truth: {project_root / 'data' / 'ground_truth' / 'ground_truth.csv'}")
        print(
            f"    Validation summary: {project_root / 'data' / 'validation' / 'validation_summary.json'}")
        print(
            f"    Source manifest: {project_root / 'data' / 'validation' / 'source_manifest.json'}")
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
