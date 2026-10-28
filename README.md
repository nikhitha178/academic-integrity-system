# Academic Integrity Case Management System

A full-stack case management application for handling similarity flags, evidence, reviewer assignment, case timelines, documented decisions, independent appeals, audit history, and analytics.

## Core Principle

A similarity flag is not proof of academic misconduct. Every case should receive appropriate human review, documented decisions, conflict-of-interest safeguards, and a fair opportunity to appeal.

## Features

- Role-based access control for learners, instructors, administrators, support staff, case reviewers, and independent appeal reviewers.
- Similarity flag and evidence management.
- Case assignment and timeline tracking.
- Documented case decisions and audit history.
- Independent appeal review workflow.
- Backend API built with FastAPI.
- Frontend application built with React and Vite.
- Relational database migrations managed with Alembic.
- Synthetic benchmark data with validation and checksum records.

## Technology Stack

- Backend: Python, FastAPI
- Frontend: React, TypeScript/JavaScript, Vite
- Database: MySQL
- Database migrations: Alembic
- Testing: pytest
- Package management: pip and npm

## Project Structure

```text
academic-integrity-system/
├── backend/              # API and application logic
├── frontend/             # Web application
├── alembic/              # Database migrations
├── scripts/              # Data generation and utility scripts
├── tests/                # Automated backend tests
├── data/                 # Starter synthetic dataset
├── data_full/            # Full synthetic benchmark dataset
├── docs/                 # Project documentation
├── .env.example          # Environment configuration template
├── alembic.ini
├── requirements.txt
├── requirements-lock.txt
└── README.md
```

## Prerequisites

- Python 3.13 or a compatible Python version
- Node.js and npm
- MySQL 8 or a compatible MySQL release

## Backend Setup

Open PowerShell in the project root.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create your local `.env` file using `.env.example` as a reference. Set the database connection and application settings required by the project. Never commit real credentials.

Ensure MySQL is running and the configured database and application user exist. Apply migrations using the project's configured environment:

```powershell
python -m alembic upgrade head
```

Start the API:

```powershell
python -m uvicorn backend.app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`. If enabled, interactive API documentation is at `http://127.0.0.1:8000/docs`.

## Frontend Setup

Open a second terminal:

```powershell
Set-Location .\frontend
npm install
npm run dev
```

Open the local URL printed by Vite, usually `http://localhost:5173`.

Create a production build:

```powershell
npm run build
```

## Tests

Run backend tests from the project root:

```powershell
python -m pytest -q
```

Build the frontend:

```powershell
Set-Location .\frontend
npm run build
```

## Synthetic Dataset

The project keeps two datasets separate:

- `data/`: existing starter dataset.
- `data_full/`: full benchmark dataset generated for the challenge.

The full benchmark target includes:

| Entity | Expected count |
|---|---:|
| Learners | 3,000 |
| Instructors | 50 |
| Reviewers | 30 |
| Assessments | 100 |
| Submissions | 10,000 |
| Similarity reports | 10,300 |
| Similarity flags | 1,000 |
| Cases | 300 |
| Ground-truth records | 10,300 |

The 10,300 reports comprise 10,000 original reports (`v2.4.0`) and 300 re-scans (`v2.4.1`). The generated dataset uses seed `20261022`.

Generate the full dataset into `data_full/` using the dedicated generator:

```powershell
python .\scripts\generate_full_data.py `
  --profile custom `
  --seed 20261022 `
  --learners 3000 `
  --instructors 50 `
  --reviewers 30 `
  --assessments 100 `
  --submissions 10000 `
  --reports 10300 `
  --flags 1000 `
  --cases 300
```

**Important:** Data generation replaces the output directories managed by that generator. Keep backups of any data you need before regenerating. Do not use the full benchmark CSVs as a database import unless the import process has been explicitly designed and tested for that dataset.

## Data Validation

Use the standalone validation utility to check expected row counts and re-scan relationships:

```powershell
python .\scripts\validate_data.py --data-dir .\data_full
```

Verify recorded checksums:

```powershell
python .\scripts\calculate_checksums.py --data-dir .\data_full
```

Keep validation summaries, manifests, and generated CSVs together so the results remain reproducible.

## Security and Fairness

- Keep `.env` and all real credentials private.
- Use synthetic data for development and benchmark validation.
- Enforce role permissions on the server, not only in the frontend.
- Maintain audit history for important case actions.
- Ensure reviewers are independent where required.
- Treat similarity results as evidence for review, not automatic proof of misconduct.

## Current Verification

The development checks completed during preparation included:

- Backend tests: 73 passed, with one deprecation warning.
- Frontend production build: successful.
- Full dataset generation: successful.
- Independent count and re-scan checks: passed.
- Recorded checksum verification: 31 entries matched.

These results describe the checks performed during development; rerun the commands above after making changes.
