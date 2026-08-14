# Codex Handoff

Read the canonical project documents in this order:

1. `docs/00_project_overview.md`
2. `docs/01_data_and_schema.md`
3. `docs/02_agent_architecture.md`
4. `docs/03_model_and_api.md`
5. `docs/04_evaluation_and_demo.md`
6. `README.md`

Start with **Phase 1 — Data Foundation only**.

Do not implement later phases until the Phase 1 data generator, validation checks, metadata YAML files, and DuckDB build are working and tested.

The exact LLM provider/model is intentionally TBD and must not be hard-coded into the architecture.
