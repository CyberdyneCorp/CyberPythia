# Tasks

- [x] 1. `has_releases(token, full_name)` on GitHub port + client + fake
- [x] 2. Metrics step fetches release presence; recompute stores `has_releases`, preserving it when not supplied
- [x] 3. Readiness: `has_releases` input + `releases` DONE check in the pure rule
- [x] 4. Readiness service reads `has_releases` from the metrics summary
- [x] 5. Tests: classify (releases blocks DONE), recompute preserve, service, client
