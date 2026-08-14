# Codex Handoff

Historical handoff note from the early build process.

The current source of truth is now:

1. `../../README.md`
2. `../../DETAILED_INSTRUCTIONS.md`
3. `../../ENGINEERING_ARCHITECTURE.md`

The original phase documents are archived here:

1. `00_project_overview.md`
2. `01_data_and_schema.md`
3. `02_agent_architecture.md`
4. `03_model_and_api.md`
5. `04_evaluation_and_demo.md`

Start with **Phase 1 — Data Foundation only**.

Do not implement later phases until the Phase 1 data generator, validation checks, metadata YAML files, and DuckDB build are working and tested.

The exact LLM provider/model is intentionally TBD and must not be hard-coded into the architecture.
