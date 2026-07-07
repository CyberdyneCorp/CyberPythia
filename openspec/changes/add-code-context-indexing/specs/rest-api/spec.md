# rest-api — code endpoints

## ADDED Requirements

### Requirement: Code-content REST endpoints
The REST API SHALL add:

```text
GET    /api/v1/repos/{repo_id}/files/{file_id}/content   (captured source content)
POST   /api/v1/repos/{repo_id}/code-search                (semantic code search)
GET    /api/v1/repos/{repo_id}/symbols                    (symbol lookup; ?name= filter)
GET    /api/v1/repos/{repo_id}/files/{file_id}/related    (related files)
```

All SHALL enforce bearer validation and the `mnemosyne` entitlement; they SHALL respect the repository's indexing mode and return the consistent error model. `code-search` and `symbols` on a repository not indexed for code SHALL return 409 with a code identifying that source is not indexed. File-content retrieval SHALL be audit-logged.

#### Scenario: Code search endpoint
- **WHEN** an entitled caller POSTs a query to `/code-search` for a `code_context` repository
- **THEN** the response SHALL list ranked source-chunk matches with path, symbol, line span, excerpt, and score

#### Scenario: Code search on non-code repository
- **WHEN** an entitled caller calls `/code-search` for a repository indexed below `code_context`
- **THEN** the API SHALL respond 409 with a code indicating source code is not indexed

#### Scenario: File content endpoint documented and secured
- **WHEN** the OpenAPI document is fetched
- **THEN** the four code endpoints SHALL be present with bearer security requirements
