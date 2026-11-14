"""Live local HTTP validation. Creates demo records; run against a disposable database."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import httpx

MANAGER = {"X-Demo-User": "demo-manager"}
AUDITOR = {"X-Demo-User": "demo-auditor"}


def create_disbursed_loan(client):
    suffix = uuid4().hex
    response = client.post(
        "/borrowers",
        json={"external_reference": "SMOKE-B-" + suffix, "full_name": "HTTP Smoke"},
    )
    assert response.status_code == 201, response.text
    response = client.post(
        "/loans",
        json={
            "external_reference": "SMOKE-L-" + suffix,
            "borrower_id": response.json()["id"],
            "product_id": "00000000-0000-0000-0000-000000000002",
            "principal_paise": 10000,
            "tenure_periods": 2,
            "first_due_date": "2026-01-31",
        },
    )
    assert response.status_code == 201, response.text
    loan_id = response.json()["id"]
    response = client.post(
        f"/loans/{loan_id}/disburse",
        headers=MANAGER,
        json={"business_date": "2026-01-01"},
    )
    assert response.status_code == 201, response.text
    assert (
        client.post(
            f"/loans/{loan_id}/disburse",
            headers=MANAGER,
            json={"business_date": "2026-01-01"},
        ).status_code
        == 409
    )
    return loan_id


def assert_balanced(client, loan_id):
    response = client.get(f"/loans/{loan_id}/ledger", headers=AUDITOR)
    assert response.status_code == 200, response.text
    for journal in response.json():
        assert len(journal["entries"]) >= 2
        assert (
            sum(
                e["amount_paise"] if e["direction"] == "debit" else -e["amount_paise"]
                for e in journal["entries"]
            )
            == 0
        )


def run(base_url):
    with httpx.Client(
        base_url=base_url, headers={"X-Demo-User": "demo-officer"}, timeout=30
    ) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/docs").status_code == 200
        assert (
            "/loans/{loan_id}/repayments" in client.get("/openapi.json").json()["paths"]
        )
        assert len(client.get("/loan-products").json()) == 3
        assert httpx.get(base_url.rstrip("/") + "/loan-products").status_code == 403
        loan_id = create_disbursed_loan(client)
        start = Barrier(20)

        def competing(index):
            start.wait(timeout=10)
            return client.post(
                f"/loans/{loan_id}/repayments",
                headers={"Idempotency-Key": f"smoke-{loan_id}-{index}"},
                json={
                    "amount_paise": 1000,
                    "source": "live-smoke",
                    "external_event_id": f"{loan_id}-{index}",
                    "occurred_at": "2026-01-15T10:00:00Z",
                    "business_date": "2026-01-15",
                },
            )

        with ThreadPoolExecutor(max_workers=20) as pool:
            responses = list(pool.map(competing, range(20)))
        statuses = [r.status_code for r in responses]
        assert statuses.count(201) == 10 and statuses.count(400) == 10, statuses
        assert (
            client.get(f"/loans/{loan_id}/balance").json()["principal_receivable_paise"]
            == 0
        )
        assert len(client.get(f"/loans/{loan_id}/repayments").json()) == 10
        assert_balanced(client, loan_id)
        print(
            "Live 20-request overlap: 10 accepted, 10 rejected, principal 0, journals balanced"
        )

        loan_id = create_disbursed_loan(client)
        path = f"/loans/{loan_id}/repayments"
        body = {
            "amount_paise": 1000,
            "source": "live-smoke",
            "external_event_id": loan_id,
            "occurred_at": "2026-01-31T10:00:00Z",
            "business_date": "2026-01-31",
        }
        key = f"receipt-{loan_id}"
        response = client.post(path, json=body, headers={"Idempotency-Key": key})
        assert response.status_code == 201, response.text
        original = response.json()
        assert (
            client.post(path, json=body, headers={"Idempotency-Key": key}).json()
            == original
        )
        assert (
            client.post(
                path, json=body, headers={"Idempotency-Key": "alias-" + key}
            ).json()
            == original
        )
        assert (
            client.post(
                path,
                json=body | {"amount_paise": 1001},
                headers={"Idempotency-Key": key},
            ).status_code
            == 409
        )
        assert (
            client.post(
                path, json=body, headers={**AUDITOR, "Idempotency-Key": "denied-" + key}
            ).status_code
            == 403
        )
        assert (
            client.get(f"/loans/{loan_id}/balance").json()["principal_receivable_paise"]
            == 9100
        )
        reverse_path = f"/loans/{loan_id}/journals/{original['journal_id']}/reverse"
        reverse_body = {"business_date": "2026-01-31", "reason": "Live smoke reversal"}
        reversed_response = client.post(
            reverse_path, json=reverse_body, headers=MANAGER
        )
        assert reversed_response.status_code == 200, reversed_response.text
        assert (
            client.post(reverse_path, json=reverse_body, headers=MANAGER).json()
            == reversed_response.json()
        )
        result = client.get(f"/loans/{loan_id}/balance").json()
        assert (
            result["principal_receivable_paise"],
            result["interest_receivable_paise"],
        ) == (10000, 100)
        assert client.get(path).json()[0]["status"] == "reversed"
        assert (
            client.post(path, json=body, headers={"Idempotency-Key": key}).json()
            == original
        )
        assert (
            client.post(
                path,
                json=body
                | {"amount_paise": 10101, "external_event_id": "excess-" + loan_id},
                headers={"Idempotency-Key": "excess-" + key},
            ).status_code
            == 400
        )
        events = client.get("/audit-events?limit=500", headers=AUDITOR)
        assert events.status_code == 200
        assert any(
            e["action"] == "repayment.posted"
            and e["actor_user_id"]
            and e["details"].get("journal_id") == original["journal_id"]
            for e in events.json()
        )
        assert_balanced(client, loan_id)
        print(
            "Live recognition, repayment, retry/source deduplication, RBAC, audit and reversal checks passed"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    run(parser.parse_args().base_url)
