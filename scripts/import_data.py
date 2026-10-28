import csv
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys

from sqlalchemy import (
    Boolean, DateTime, Float, Integer, JSON, Numeric, inspect, select, func
)
from sqlalchemy.sql.sqltypes import NullType

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.database import engine, Base
import backend.app.models  # Register all ORM models


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "generated"

# Import parent tables before tables that reference them.
IMPORT_ORDER = [
    "users",
    "instructors",
    "learners",
    "reviewers",
    "assessments",
    "submissions",
    "similarity_reports",
    "similarity_flags",
    "cases",
    "decisions",
    "evidence",
    "reviewer_assignments",
    "appeals",
    "audit_events",
]


def parse_value(value, column_type):
    if value is None or value.strip() == "":
        return None

    value = value.strip()

    if isinstance(column_type, Boolean):
        normalized = value.lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
        raise ValueError(f"Invalid boolean value: {value!r}")

    if isinstance(column_type, DateTime):
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        # MySQL DATETIME does not retain timezone information.
        if result.tzinfo is not None:
            result = result.astimezone(timezone.utc).replace(tzinfo=None)
        return result

    if isinstance(column_type, JSON):
        return json.loads(value)

    if isinstance(column_type, Integer):
        return int(value)

    if isinstance(column_type, (Numeric, Float)):
        return Decimal(value) if isinstance(column_type, Numeric) else float(value)

    return value


def load_csv(table_name):
    path = DATA_DIR / f"{table_name}.csv"

    if not path.is_file():
        raise FileNotFoundError(f"Required CSV not found: {path}")

    table = Base.metadata.tables[table_name]

    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        if reader.fieldnames is None:
            raise ValueError(f"{path.name} has no header row")

        expected = set(table.columns.keys())
        actual = set(reader.fieldnames)

        if expected != actual:
            raise ValueError(
                f"Column mismatch in {path.name}. "
                f"Missing: {sorted(expected - actual)}; "
                f"unexpected: {sorted(actual - expected)}"
            )

        records = []
        for line_number, row in enumerate(reader, start=2):
            try:
                records.append({
                    column.name: parse_value(
                        row[column.name], column.type
                    )
                    for column in table.columns
                })
            except Exception as exc:
                raise ValueError(
                    f"Error in {path.name}, line {line_number}: {exc}"
                ) from exc

    return records


def main():
    # Validate every CSV before making any database changes.
    data = {
        table_name: load_csv(table_name)
        for table_name in IMPORT_ORDER
    }

    print("CSV validation passed.")
    for name, records in data.items():
        print(f"  {name}: {len(records)} records")

    # Never silently append duplicates or overwrite an existing dataset.
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    missing_tables = set(IMPORT_ORDER) - existing_tables

    if missing_tables:
        raise RuntimeError(
            f"Database tables are missing: {sorted(missing_tables)}. "
            "Apply the Alembic migration first."
        )

    with engine.connect() as connection:
        nonempty = []
        for name in IMPORT_ORDER:
            table = Base.metadata.tables[name]
            count = connection.execute(
                select(func.count()).select_from(table)
            ).scalar_one()

            if count:
                nonempty.append(f"{name}={count}")

    if nonempty:
        raise RuntimeError(
            "Import stopped because these tables already contain records: "
            + ", ".join(nonempty)
            + ". No data was imported. Inspect the database before proceeding."
        )

    # One transaction for the complete import.
    with engine.begin() as connection:
        for name in IMPORT_ORDER:
            records = data[name]
            if records:
                table = Base.metadata.tables[name]
                connection.execute(table.insert(), records)
            print(f"Imported {len(records)} rows into {name}.")

    print("\nIMPORT COMPLETED SUCCESSFULLY")
    print("The ground_truth dataset was not imported.")


if __name__ == "__main__":
    main()
