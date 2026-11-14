# Five-minute technical demo

Start the application with demo authentication enabled on a **fresh local demo database**.
The demo creates invented financial history; it does not delete or edit it. Audit assertions
inspect the first 500 audit events, so use a fresh database or paginate/adjust the offset.

```sh
BASE_URL=http://127.0.0.1:8000 sh scripts/demo.sh
```

The script contains the actual curl commands and captures returned IDs automatically:

1. Create an invented borrower and a 10000-paise personal loan at 12%, two months.
2. View schedule: principal/interest pairs `(4975,100)` and `(5025,50)`.
3. Disburse as `demo-manager`: principal receivable debit 10000, cash credit 10000.
4. Receive 1000 as `demo-officer` on January 31: recognize 100 interest once, then collect
   100 interest and 900 principal.
5. Repeat the identical request with the same Idempotency-Key and compare the full response.
6. Inspect ledger and balance as `demo-auditor`: principal 9100, interest 0, penalty 0.
7. Verify a successful audit event has actor, correlation and the repayment journal ID.

To inspect manually afterward, substitute the IDs printed by the script:

```sh
curl -fsS http://127.0.0.1:8000/loans/LOAN_UUID/ledger -H 'X-Demo-User: demo-auditor'
curl -fsS http://127.0.0.1:8000/loans/LOAN_UUID/balance -H 'X-Demo-User: demo-auditor'
curl -fsS 'http://127.0.0.1:8000/audit-events?limit=500&offset=0' -H 'X-Demo-User: demo-auditor'
```

Import the [collection](postman/ledgercore.postman_collection.json) and
[environment](postman/local.postman_environment.json) into Postman, select that environment,
and run all requests in order. The collection additionally exercises reversal, source
aliases, idempotency conflicts, expected authorization denials and all public documentation
routes. The first health request resets IDs and keys for a new run; do not rerun it between
the original repayment and its retry. Adjust baseUrl rather than editing requests.

For command-line execution with no Postman account/cloud service:

```sh
npm exec --yes --package=newman@6.2.1 -- newman run docs/postman/ledgercore.postman_collection.json \
  -e docs/postman/local.postman_environment.json --env-var baseUrl=http://127.0.0.1:8000
```

To verify a timeout **after** commit (not an assumed network outcome):

```sh
uv run python scripts/verify_timeout_retry.py --base-url http://127.0.0.1:8000
```

That tool consumes a real upstream successful HTTP response, hides it from the caller with
an injected ReadTimeout, then verifies one receipt/journal and an identical-ID successful
retry. It adds a separate invented loan. This is fault injection, not a claim that a real
network failure happened spontaneously.

X-Demo-User is public local impersonation, **not production authentication**. Auditors cannot
mutate; officers cannot disburse/reverse; only managers can reverse supported repayment
journals. GET balance reads posted receivables and never runs accrual or quotes future payoff.
