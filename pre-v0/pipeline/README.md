# Company workflow modules

Start with [TEAM_WORKFLOW.md](TEAM_WORKFLOW.md) for the current integrated route,
[the notebook](../notebooks/team_company_workflow.ipynb) for sequential execution,
or [the results](../reports/team_company_workflow/README.md) for findings and charts.

`TeamPipeline` orchestrates collection, profiles, candidate retrieval, business
review, financial factors, growth evidence, EBITDA and valuation. `PipelineConfig`
selects methods; `ExperimentRunner` compares configurations. Stage registries let
teammates add methods without replacing the orchestration.

Implementation is shared across `website_scrape/`, `matching/`, `growth_signals/`
and `valuation/`. The underlying `CompanyWorkflow`, `run_workflow` and `run_target`
interfaces are retained for the earlier 19-company development experiment.
That legacy route permits unreviewed controls; use `TeamPipeline` for mandatory
business review. Earlier notebooks remain historical reports.
