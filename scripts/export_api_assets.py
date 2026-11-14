"""Export the running application OpenAPI and reproducible Postman v2.1 demo assets."""

import argparse
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def event(kind, source):
    return {
        "listen": kind,
        "script": {"type": "text/javascript", "exec": source.strip().splitlines()},
    }


def collection():
    items = []

    def add(
        name,
        method,
        path,
        status=200,
        *,
        actor="demoOfficer",
        body=None,
        key=None,
        tests="",
        pre="",
    ):
        headers = []
        if actor:
            headers.append({"key": "X-Demo-User", "value": "{{" + actor + "}}"})
        if key:
            headers.append({"key": "Idempotency-Key", "value": "{{" + key + "}}"})
        request = {
            "method": method,
            "header": headers,
            "url": "{{baseUrl}}" + path,
            "description": "Local demo identity only. Run this collection in order against a disposable demo database.",
        }
        if body is not None:
            headers.append({"key": "Content-Type", "value": "application/json"})
            request["body"] = {
                "mode": "raw",
                "raw": json.dumps(body, indent=2),
                "options": {"raw": {"language": "json"}},
            }
        events = [
            event(
                "test",
                f'pm.test("HTTP {status}", () => pm.response.to.have.status({status}));\n'
                + tests,
            )
        ]
        if pre:
            events.insert(0, event("prerequest", pre))
        items.append({"name": name, "request": request, "event": events})

    add(
        "01 Health and new demo run",
        "GET",
        "/health",
        actor=None,
        pre="""
const run = pm.variables.replaceIn("{{$guid}}");
pm.environment.set("runId", run);
pm.environment.set("externalEventId", "postman-event-" + run);
pm.environment.set("idempotencyKey", "postman-pay-" + run);
pm.environment.set("sourceDuplicateKey", "postman-alias-" + run);
pm.environment.set("rejectedKey", "postman-rejected-" + run);
["borrowerId", "loanId", "journalId", "repaymentId", "reversalJournalId", "originalResponse", "originalSchedule"].forEach(k => pm.environment.unset(k));
""",
        tests='pm.test("Database reachable", () => pm.expect(pm.response.json().database).to.eql("ok"));',
    )
    add(
        "02 List products",
        "GET",
        "/loan-products",
        tests="""
const product = pm.response.json().find(p => p.code === "PERSONAL_EMI");
pm.test("Three configured products", () => pm.expect(pm.response.json()).to.have.lengthOf(3));
pm.environment.set("productId", product.id);
""",
    )
    add(
        "03 Create invented borrower",
        "POST",
        "/borrowers",
        201,
        body={
            "external_reference": "POSTMAN-B-{{runId}}",
            "full_name": "Invented Postman Borrower",
        },
        tests='pm.environment.set("borrowerId", pm.response.json().id);',
    )
    add(
        "04 Read borrower",
        "GET",
        "/borrowers/{{borrowerId}}",
        tests='pm.test("Borrower captured", () => pm.expect(pm.response.json().id).to.eql(pm.environment.get("borrowerId")));',
    )
    add(
        "05 Originate loan",
        "POST",
        "/loans",
        201,
        body={
            "external_reference": "POSTMAN-L-{{runId}}",
            "borrower_id": "{{borrowerId}}",
            "product_id": "{{productId}}",
            "principal_paise": 10000,
            "tenure_periods": 2,
            "first_due_date": "{{firstDueDate}}",
        },
        tests='pm.environment.set("loanId", pm.response.json().id);',
    )
    add(
        "06 Read loan snapshot",
        "GET",
        "/loans/{{loanId}}",
        tests='pm.test("Originated, not disbursed", () => pm.expect(pm.response.json().status).to.eql("originated"));',
    )
    add(
        "07 View contractual schedule",
        "GET",
        "/loans/{{loanId}}/schedule",
        tests="""
const rows = pm.response.json();
pm.environment.set("originalSchedule", JSON.stringify(rows));
pm.test("Independent two-period example", () => pm.expect(rows.map(r => [r.principal_due_paise, r.interest_due_paise])).to.eql([[4975,100],[5025,50]]));
""",
    )
    disbursement = {"business_date": "{{disbursementDate}}"}
    add(
        "08 Auditor cannot disburse",
        "POST",
        "/loans/{{loanId}}/disburse",
        403,
        actor="demoAuditor",
        body=disbursement,
    )
    add(
        "09 Manager disburses once",
        "POST",
        "/loans/{{loanId}}/disburse",
        201,
        actor="demoManager",
        body=disbursement,
        tests='pm.environment.set("disbursementJournalId", pm.response.json().journal_id);',
    )
    add(
        "10 Duplicate disbursement conflicts",
        "POST",
        "/loans/{{loanId}}/disburse",
        409,
        actor="demoManager",
        body=disbursement,
    )
    repayment = {
        "amount_paise": 1000,
        "source": "postman-demo",
        "external_event_id": "{{externalEventId}}",
        "occurred_at": "{{occurredAt}}",
        "business_date": "{{businessDate}}",
    }
    add(
        "11 Receive repayment",
        "POST",
        "/loans/{{loanId}}/repayments",
        201,
        body=repayment,
        key="idempotencyKey",
        tests="""
const result = pm.response.json();
pm.environment.set("journalId", result.journal_id);
pm.environment.set("repaymentId", result.id);
pm.environment.set("originalResponse", JSON.stringify(result));
pm.test("Interest then principal", () => pm.expect(result.allocations.map(a => [a.component,a.amount_paise])).to.eql([["interest",100],["principal",900]]));
""",
    )
    same = 'pm.test("Exact original successful response", () => pm.expect(pm.response.json()).to.deep.eql(JSON.parse(pm.environment.get("originalResponse"))));'
    add(
        "12 Retry identical repayment",
        "POST",
        "/loans/{{loanId}}/repayments",
        201,
        body=repayment,
        key="idempotencyKey",
        tests=same,
    )
    add(
        "13 Source duplicate under another key",
        "POST",
        "/loans/{{loanId}}/repayments",
        201,
        body=repayment,
        key="sourceDuplicateKey",
        tests=same,
    )
    add(
        "14 Same key different payload conflicts",
        "POST",
        "/loans/{{loanId}}/repayments",
        409,
        body=repayment | {"amount_paise": 1001},
        key="idempotencyKey",
    )
    add(
        "15 Auditor cannot receive money",
        "POST",
        "/loans/{{loanId}}/repayments",
        403,
        actor="demoAuditor",
        body=repayment,
        key="rejectedKey",
    )
    add(
        "16 Read receipts - one financial receipt",
        "GET",
        "/loans/{{loanId}}/repayments",
        tests='pm.test("Duplicates did not add receipts", () => pm.expect(pm.response.json()).to.have.lengthOf(1));',
    )
    add(
        "17 Inspect posted ledger",
        "GET",
        "/loans/{{loanId}}/ledger",
        actor="demoAuditor",
        tests="""
pm.test("Every journal balances in integer paise", () => {
  pm.response.json().forEach(j => {
    pm.expect(j.entries.length).to.be.at.least(2);
    j.entries.forEach(e => pm.expect(Number.isSafeInteger(e.amount_paise)).to.eql(true));
    const net = j.entries.reduce((sum,e) => sum + (e.direction === "debit" ? 1n : -1n) * BigInt(e.amount_paise), 0n);
    pm.expect(net.toString()).to.eql("0");
  });
});
""",
    )
    add(
        "18 Inspect ledger-derived balance",
        "GET",
        "/loans/{{loanId}}/balance",
        actor="demoAuditor",
        tests="""
const b = pm.response.json();
pm.test("9100 principal, no recognized interest or penalties", () => {
  pm.expect([b.principal_receivable_paise,b.interest_receivable_paise,b.penalty_receivable_paise]).to.eql([9100,0,0]);
});
""",
    )
    add(
        "19 Verify actor audit trail",
        "GET",
        "/audit-events?limit=500&offset={{auditOffset}}",
        actor="demoAuditor",
        tests="""
pm.test("Receipt has actor, correlation and journal audit", () => pm.expect(pm.response.json().some(e =>
 e.action === "repayment.posted" && e.details.journal_id === pm.environment.get("journalId") && e.actor_user_id && e.correlation_id)).to.eql(true));
""",
    )
    add(
        "20 Verify unchanged original schedule",
        "GET",
        "/loans/{{loanId}}/schedule",
        tests='pm.test("Schedule immutable", () => pm.expect(pm.response.json()).to.deep.eql(JSON.parse(pm.environment.get("originalSchedule"))));',
    )
    reversal = {
        "business_date": "{{businessDate}}",
        "reason": "Submission demo bank settlement reversal",
    }
    add(
        "21 Manager reverses repayment",
        "POST",
        "/loans/{{loanId}}/journals/{{journalId}}/reverse",
        actor="demoManager",
        body=reversal,
        tests='pm.environment.set("reversalJournalId", pm.response.json().journal_id);',
    )
    add(
        "22 Retry reversal",
        "POST",
        "/loans/{{loanId}}/journals/{{journalId}}/reverse",
        actor="demoManager",
        body=reversal,
        tests='pm.test("Same reversal", () => pm.expect(pm.response.json().journal_id).to.eql(pm.environment.get("reversalJournalId")));',
    )
    add(
        "23 Balance after reversal",
        "GET",
        "/loans/{{loanId}}/balance",
        actor="demoAuditor",
        tests='pm.test("Receivables restored", () => { const b=pm.response.json(); pm.expect([b.principal_receivable_paise,b.interest_receivable_paise]).to.eql([10000,100]); });',
    )
    add(
        "24 Receipt history after reversal",
        "GET",
        "/loans/{{loanId}}/repayments",
        tests='pm.test("History preserved, marked reversed", () => pm.expect(pm.response.json().map(r => r.status)).to.eql(["reversed"]));',
    )
    add(
        "25 Auditor cannot reverse",
        "POST",
        "/loans/{{loanId}}/journals/{{journalId}}/reverse",
        403,
        actor="demoAuditor",
        body=reversal,
    )
    add("26 Missing identity is denied", "GET", "/loan-products", 403, actor=None)
    add("27 Officer cannot read audit history", "GET", "/audit-events", 403)
    add(
        "28 Overpayment rejected",
        "POST",
        "/loans/{{loanId}}/repayments",
        400,
        body=repayment
        | {"amount_paise": 100000000000, "external_event_id": "excess-{{runId}}"},
        key="rejectedKey",
    )
    add(
        "29 Zero amount rejected",
        "POST",
        "/loans/{{loanId}}/repayments",
        422,
        body=repayment | {"amount_paise": 0},
        key="rejectedKey",
    )
    add(
        "30 Running OpenAPI export",
        "GET",
        "/openapi.json",
        actor=None,
        tests='pm.test("OpenAPI 3", () => pm.expect(pm.response.json().openapi).to.match(/^3\\./));',
    )
    add("31 Swagger documentation", "GET", "/docs", actor=None)
    add("32 ReDoc documentation", "GET", "/redoc", actor=None)
    add("33 Swagger redirect support", "GET", "/docs/oauth2-redirect", actor=None)
    return {
        "info": {
            "_postman_id": "74dd4d99-f235-48bc-aab4-50967571875e",
            "name": "LedgerCore final submission — local demo only",
            "description": "Run all requests in order on a fresh/disposable local demo database. Header identities are NOT production authentication. Expected 400/403/409/422 responses are deliberate tests. First request resets run IDs. Audit page defaults to first 500 events; use a fresh demo DB or adjust auditOffset. No accrual job is run inside this API collection.",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "auth": {"type": "noauth"},
        "item": items,
    }


def environment():
    values = {
        "baseUrl": "http://127.0.0.1:8000",
        "demoOfficer": "demo-officer",
        "demoManager": "demo-manager",
        "demoAuditor": "demo-auditor",
        "borrowerId": "",
        "loanId": "",
        "journalId": "",
        "disbursementJournalId": "",
        "reversalJournalId": "",
        "repaymentId": "",
        "productId": "00000000-0000-0000-0000-000000000002",
        "idempotencyKey": "",
        "sourceDuplicateKey": "",
        "rejectedKey": "",
        "externalEventId": "",
        "runId": "",
        "businessDate": "2026-01-31",
        "disbursementDate": "2026-01-01",
        "firstDueDate": "2026-01-31",
        "occurredAt": "2026-01-31T10:00:00Z",
        "auditOffset": "0",
    }
    return {
        "id": "69773119-239f-4dab-957a-1fd3ffae3c30",
        "name": "LedgerCore local demo — no secrets",
        "_postman_variable_scope": "environment",
        "values": [
            {"key": k, "value": v, "enabled": True, "type": "default"}
            for k, v in values.items()
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    response = httpx.get(args.base_url.rstrip("/") + "/openapi.json", timeout=10)
    response.raise_for_status()
    save(ROOT / "docs/openapi.json", response.json())
    save(ROOT / "docs/postman/ledgercore.postman_collection.json", collection())
    save(ROOT / "docs/postman/local.postman_environment.json", environment())
    print("Exported running OpenAPI and Postman collection/environment")


if __name__ == "__main__":
    main()
