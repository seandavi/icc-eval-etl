# API Quirks

Hard-won lessons — do not change without verifying against live APIs.

## NIH Reporter

- **Projects search**: Use `project_nums` (not `core_project_nums`) in criteria. The `core_project_nums` field is silently ignored and returns ALL projects.
- **Publications search**: Uses `core_project_nums` correctly (opposite of projects).

## Europe PMC

- Use the direct article endpoint `/article/MED/{pmid}` rather than the search endpoint.
- The search endpoint requires `src:MED` qualifier or returns 0 hits.
- PMID lookups via search require `EXT_ID:{pmid} src:MED`.

## iCite

- GET `/api/pubs?pmids=...` — batch size limited to 200 PMIDs per request to avoid HTTP 414 URI Too Long errors.
- The `cited_by` field can be `null` (not just empty list).
- Batch endpoint supports up to 1000 comma-separated PMIDs, but we use 200 for safety.

## OpenAlex

- Filter `ids.pmid` supports up to 100 pipe-separated values.
- Uses cursor pagination (`cursor=*` then follow `meta.next_cursor`).
- Requires API key (`OPENALEX_API_KEY` in `.env`) — without it, limited to 100 requests/day.
- Per-page max is 200.

## GitHub

- Search API is rate-limited to 30 req/min (authenticated) or 10 req/min (unauthenticated).
- Set `GITHUB_TOKEN` in `.env` for higher limits.
- Topics are always lowercase — core project IDs must be lowercased before searching.
- `tenacity` retry: `retry_if_result` with `retry_error_callback` needed — without the callback, exhausted retries raise opaque `RetryError` instead of the HTTP status error.

## General

- All models use `extra="allow"` to capture full API responses without breaking on new fields.
