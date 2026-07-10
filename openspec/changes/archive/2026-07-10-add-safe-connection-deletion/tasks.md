# Tasks

- [x] 1. Add `ConnectionStatus.DELETING`
- [x] 2. Connection list/view carries `repository_count`
- [x] 3. Use case: `begin_delete` (count + mark deleting + enqueue) and `perform_delete` (worker cascade)
- [x] 4. REST: `DELETE /github/connections/{id}` → 202 + `{repository_count}`; response gains `repository_count`
- [x] 5. Worker: `delete_connection` job registered
- [x] 6. Web: typed-confirmation delete (owner match + impact count) + error surfacing
- [x] 7. Tests: use case (begin/perform), endpoint (202), worker fn, VM (confirm gating + error)
