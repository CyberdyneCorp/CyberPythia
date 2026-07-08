# add-intelligence-indexed-scope-org-bulk

Intelligence (REST + MCP) only considers indexed repos: per-repo endpoints reject disabled repos
(portfolio/scorecard already exclude them). Plus organization-scoped bulk selection
(POST /api/v1/repos/selection with `organization`) and per-org Index-all / Un-index-all controls in
the Organizations panel. No data model change.
