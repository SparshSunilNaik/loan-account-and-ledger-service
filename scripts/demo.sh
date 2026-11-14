#!/bin/sh
# Creates invented financial records. Run from the repository root on a disposable demo DB.
set -eu
base_url=${BASE_URL:-http://127.0.0.1:8000}
run_id=$(uv run python -c 'from uuid import uuid4; print(uuid4().hex)')
json_id() { uv run python -c 'import json,sys; print(json.load(sys.stdin)[sys.argv[1]])' "$1"; }
officer=${DEMO_OFFICER:-demo-officer}
manager=${DEMO_MANAGER:-demo-manager}
auditor=${DEMO_AUDITOR:-demo-auditor}

curl -fsS "$base_url/health"
borrower=$(curl -fsS -X POST "$base_url/borrowers" -H "X-Demo-User: $officer" -H 'Content-Type: application/json' \
  -d "{\"external_reference\":\"DEMO-B-$run_id\",\"full_name\":\"Invented Submission Borrower\"}")
borrower_id=$(printf '%s' "$borrower" | json_id id)
loan=$(curl -fsS -X POST "$base_url/loans" -H "X-Demo-User: $officer" -H 'Content-Type: application/json' \
  -d "{\"external_reference\":\"DEMO-L-$run_id\",\"borrower_id\":\"$borrower_id\",\"product_id\":\"00000000-0000-0000-0000-000000000002\",\"principal_paise\":10000,\"tenure_periods\":2,\"first_due_date\":\"2026-01-31\"}")
loan_id=$(printf '%s' "$loan" | json_id id)
printf '\nCreated borrower %s and loan %s\n' "$borrower_id" "$loan_id"
curl -fsS "$base_url/loans/$loan_id/schedule" -H "X-Demo-User: $officer"
curl -fsS -X POST "$base_url/loans/$loan_id/disburse" -H "X-Demo-User: $manager" -H 'Content-Type: application/json' -d '{"business_date":"2026-01-01"}'
payment="{\"amount_paise\":1000,\"source\":\"submission-demo\",\"external_event_id\":\"DEMO-E-$run_id\",\"occurred_at\":\"2026-01-31T10:00:00Z\",\"business_date\":\"2026-01-31\"}"
receipt=$(curl -fsS -X POST "$base_url/loans/$loan_id/repayments" -H "X-Demo-User: $officer" -H "Idempotency-Key: DEMO-K-$run_id" -H 'Content-Type: application/json' -d "$payment")
journal_id=$(printf '%s' "$receipt" | json_id journal_id)
retry=$(curl -fsS -X POST "$base_url/loans/$loan_id/repayments" -H "X-Demo-User: $officer" -H "Idempotency-Key: DEMO-K-$run_id" -H 'Content-Type: application/json' -d "$payment")
# Compare full parsed responses; repeat must not add a receipt or journal.
uv run python -c 'import json,sys; assert json.loads(sys.argv[1]) == json.loads(sys.argv[2]); print("Identical retry verified")' "$receipt" "$retry"
curl -fsS "$base_url/loans/$loan_id/ledger" -H "X-Demo-User: $auditor"
balance=$(curl -fsS "$base_url/loans/$loan_id/balance" -H "X-Demo-User: $auditor")
printf '\n%s\n' "$balance"
uv run python -c 'import json,sys; b=json.loads(sys.argv[1]); assert (b["principal_receivable_paise"],b["interest_receivable_paise"],b["penalty_receivable_paise"]) == (9100,0,0)' "$balance"
# A fresh demo database keeps this audit event in the first page; adjust/paginate otherwise.
audit=$(curl -fsS "$base_url/audit-events?limit=500&offset=0" -H "X-Demo-User: $auditor")
uv run python -c 'import json,sys; assert any(e["action"]=="repayment.posted" and e["details"].get("journal_id")==sys.argv[2] and e["actor_user_id"] and e["correlation_id"] for e in json.loads(sys.argv[1])); print("Actor and journal audit verified")' "$audit" "$journal_id"
printf 'Demo complete. Loan %s, repayment journal %s\n' "$loan_id" "$journal_id"
