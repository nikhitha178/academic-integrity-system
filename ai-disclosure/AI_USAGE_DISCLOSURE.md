\# AI Usage Disclosure



\## Project



\*\*Academic Integrity Case Management System\*\*



\## AI Tools Used



The AI tools used during the development process were:



\- \*\*ChatGPT:\*\* Used for understanding project requirements, planning implementation steps, explaining technical concepts, troubleshooting development issues, reviewing project structure, preparing documentation, and preparing for project explanations and interviews.

\- \*\*Google Gemini:\*\* Used for assistance with project implementation, development guidance, and reviewing progress against the recruitment challenge requirements.

\- \*\*Claude:\*\* Used for assistance with code development, reviewing implementation progress, and checking project functionality and requirements.



\## Areas of Assistance



AI tools supported different stages of the development process, including:



1\. \*\*Requirement analysis and planning:\*\* Understanding the academic integrity case management problem, identifying the main user roles, defining the core workflow, and organizing the project requirements.



2\. \*\*Backend development:\*\* Assistance with Python, FastAPI, API implementation, database integration, access-control rules, case management, evidence handling, reviewer assignments, decisions, and appeals.



3\. \*\*Frontend development:\*\* Assistance with React, Vite, JavaScript, CSS, dashboard organization, reviewer workspaces, evidence panels, and independent appeal review interfaces.



4\. \*\*Database and data management:\*\* Guidance related to MySQL, SQLAlchemy, Alembic migrations, data models, synthetic dataset generation, validation, and data consistency checks.



5\. \*\*Testing and debugging:\*\* Assistance with interpreting errors, troubleshooting implementation issues, understanding test failures, and checking whether the application met the expected requirements.



6\. \*\*Documentation and GitHub:\*\* Assistance with README preparation, setup instructions, project explanations, Git commands, repository management, and preparing the AI usage disclosure and prompt history.



AI assistance was used as a development aid. The implementation was checked through available tests and build commands rather than relying solely on AI-generated claims.



\## Personal Review and Validation



I ran the backend automated test suite locally using Python and pytest. The latest recorded run completed with \*\*73 tests passed and one deprecation warning\*\* related to the use of `httpx` with Starlette's test client.



I also ran the frontend production build using `npm run build`. The build completed successfully with Vite.



Additional validation performed during development included:



\- Checking database migration status and confirming that the expected migration was at the current head.

\- Validating the synthetic dataset, including record counts, dataset versions, rescans, comparison consistency, and checksums.

\- Checking Git repository status and confirming that the latest committed changes were pushed to the configured GitHub repository.

\- Reviewing the available project code, test results, build output, and documentation.



These checks demonstrate that the backend test suite passes and the frontend can be built. They do not, by themselves, establish that every feature or complete user workflow has been tested end to end.



\## Limitations and Known Considerations



\- The backend test suite and frontend production build were verified locally; a successful build does not guarantee that every frontend interaction works correctly.

\- Complete end-to-end verification of every role and workflow has not been established by the recorded test results.

\- Database configuration, environment variables, and dependency installation may be required to run the application in another environment.

\- The system manages academic integrity reports, flags, evidence, cases, review decisions, and appeals. Similarity reports should be treated as signals requiring human review, not as conclusive proof of misconduct.

\- Any incomplete features, untested workflows, or environment-specific issues should be considered when evaluating the project and should be documented as they are identified.



\## Prompt History



The project used multiple AI tools during development. The prompt history is maintained separately in `PROMPT\_HISTORY.md`.



The history should contain the actual prompts submitted to each AI tool, organized by tool and development task where possible. AI responses are not required by the recruitment guidelines.



Where a complete prompt transcript is unavailable, that limitation must be disclosed. This document does not claim to reproduce every original prompt verbatim.



\## Responsibility and Ownership



I am responsible for the submitted project, the accuracy of its documentation, and my ability to explain its implementation and design decisions.



I understand that AI-generated suggestions may contain errors or incomplete assumptions and therefore require review and validation. I will explain the technologies used, the main application workflows, the testing performed, the limitations identified, and the areas where AI assistance contributed to development.



The project is submitted with the intention of providing a transparent account of the development process, the available validation evidence, and the limitations of the current implementation.



