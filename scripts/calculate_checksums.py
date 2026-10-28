import argparse
import hashlib
import json
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(
        description="Verify recorded SHA-256 checksums for a generated dataset."
    )
    parser.add_argument("--data-dir", default="data_full")
    args = parser.parse_args()

    root = Path(args.data_dir)
    metadata_files = [
        (root / "validation" / "validation_summary.json", "file_checksums"),
        (root / "validation" / "source_manifest.json", "artifact_checksums"),
    ]

    errors = []
    checked = 0

    for metadata_path, key in metadata_files:
        if not metadata_path.is_file():
            errors.append(f"Missing metadata file: {metadata_path}")
            continue

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        checksums = metadata.get(key, {})
        print(f"\n{metadata_path}: {len(checksums)} recorded checksums")

        for relative_path, expected_hash in checksums.items():
            file_path = root / relative_path

            if not file_path.is_file():
                errors.append(f"Missing file: {relative_path}")
                continue

            actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
            checked += 1
            if actual_hash.lower() != str(expected_hash).lower():
                errors.append(f"Checksum mismatch: {relative_path}")

    print(f"\nChecked entries: {checked}")
    if errors:
        print("FAIL")
        for error in errors:
            print("-", error)
        return 1

    print("PASS - all recorded checksums match.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
