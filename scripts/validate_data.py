import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

EXPECTED = {
    "learners": 3000,
    "instructors": 50,
    "reviewers": 30,
    "assessments": 100,
    "submissions": 10000,
    "similarity_reports": 10300,
    "similarity_flags": 1000,
    "cases": 300,
}

def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def pair(row):
    return tuple(sorted((
        row["target_submission_id"],
        row["matched_submission_id"],
    )))

def main():
    parser = argparse.ArgumentParser(description="Validate a generated dataset.")
    parser.add_argument("--data-dir", default="data_full")
    args = parser.parse_args()

    root = Path(args.data_dir)
    generated = root / "generated"
    errors = []

    summary_path = root / "validation" / "validation_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        print("Generator status:", summary.get("status", "not specified"))
    else:
        print("WARNING: generator validation summary is missing.")

    print("\nRow counts:")
    for name, expected in EXPECTED.items():
        path = generated / f"{name}.csv"
        if not path.is_file():
            errors.append(f"Missing file: {path}")
            print(f"{name}: MISSING")
            continue

        rows = read_csv(path)
        print(f"{name}: {len(rows)} (expected {expected})")
        if len(rows) != expected:
            errors.append(f"{name}: expected {expected}, got {len(rows)}")

    gt_path = root / "ground_truth" / "ground_truth.csv"
    if not gt_path.is_file():
        errors.append(f"Missing file: {gt_path}")
    else:
        gt_count = len(read_csv(gt_path))
        print(f"ground_truth: {gt_count} (expected 10300)")
        if gt_count != 10300:
            errors.append(f"ground_truth: expected 10300, got {gt_count}")

    report_path = generated / "similarity_reports.csv"
    if report_path.is_file():
        reports = read_csv(report_path)
        versions = Counter(r.get("algorithm_version", "") for r in reports)
        print("\nAlgorithm versions:")
        for version, count in sorted(versions.items()):
            print(f"{version}: {count}")

        originals = [r for r in reports if r.get("algorithm_version") == "v2.4.0"]
        rescans = [r for r in reports if r.get("algorithm_version") == "v2.4.1"]
        original_pairs = {pair(r) for r in originals}
        rescan_pairs = [pair(r) for r in rescans]

        if len(originals) != 10000:
            errors.append(f"Expected 10000 original reports, got {len(originals)}")
        if len(rescans) != 300:
            errors.append(f"Expected 300 re-scans, got {len(rescans)}")
        if any(p not in original_pairs for p in rescan_pairs):
            errors.append("At least one re-scan has no matching original pair")
        if any(r["target_submission_id"] == r["matched_submission_id"] for r in reports):
            errors.append("A report compares a submission with itself")

        print("Re-scans matching original pairs:",
              sum(p in original_pairs for p in rescan_pairs), "/", len(rescans))

    print("\nRESULT:", "FAIL" if errors else "PASS")
    for error in errors:
        print("-", error)
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
