# Tasks: add-bulk-repository-selection

> Bulk selection over the current filter. Typed; unit coverage > 90%; ruff + mypy --strict clean.

## 1. Backend
- [x] 1.1 `RepositoryUseCases.bulk_update_selection(ids, *, enabled, mode=None) -> int` (load-by-id, mutate, save_many). Unit test.
- [x] 1.2 `POST /api/v1/repos/selection` (AdminCaller) + `RepositorySelectionBulkRequest` schema; one audit event. Interface test incl. non-admin 403 + unknown-id ignored.

## 2. Web
- [x] 2.1 `RepositoriesApi.bulkSelection(ids, enabled, mode?)`; `RepositoryListViewModel.bulkSetSelection(enabled, mode?)` over filtered ids + in-place update. VM test.
- [x] 2.2 Enable-all / Disable-all buttons + mode select in the dashboard filters row (act on filtered set; show the count).

## 3. Gate
- [x] 3.1 ruff, mypy --strict, unit >= 90%, integration, openspec --strict, web build + tests. Deploy after merge.
