# Proposed read-only discovery API — not implemented

`GET /loans?query=<borrower name or external reference>&limit=50&cursor=<opaque>`
would remove the browser-history limitation. It should return loan ID/reference, borrower
ID/name, product name, snapshot terms, status and a stable next cursor. Use a stable
`(created_at,id)` order, validated limit 1–100 and an opaque cursor. Prefix/name search
must be parameterized and indexed; do not expose arbitrary database filters.

Require the same authenticated read permission as existing loan detail. Current demo readers
can read all demo loans; a production implementation would also apply tenant/branch/ownership
scope consistently to both discovery and exact lookup. Search results must not reveal records
that detail authorization would deny. No mutation or job execution on reads.

If financial summaries are included, derive them from posted ledger entries in one read query
or a read-only view; no mutable authoritative balance column. Contractual future interest
must remain separate. Prefer returning metadata in listing and loading `/balance` on selection
if aggregate joins prove expensive. Return an explicit as-of timestamp for any read snapshot.

Add tests for pagination boundaries, equal timestamps, denied readers, consistent record
scope and ledger reconciliation. No frontend mock endpoint, migration or backend change has
been made to simulate this proposal.
