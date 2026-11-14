"""Inject a lost client response AFTER a real upstream HTTP repayment has committed."""

import argparse
import json
from pathlib import Path
from uuid import uuid4

import httpx


class LoseCommittedResponse(httpx.BaseTransport):
    def __init__(self):
        self.inner = httpx.HTTPTransport()

    def handle_request(self, request):
        response = self.inner.handle_request(request)
        response.read()
        response.close()
        raise httpx.ReadTimeout(
            "Injected client timeout after upstream response", request=request
        )

    def close(self):
        self.inner.close()


def verify(base_url):
    headers = {"X-Demo-User": "demo-officer"}
    unique = uuid4().hex
    with httpx.Client(base_url=base_url, headers=headers) as client:
        borrower = client.post(
            "/borrowers",
            json={
                "external_reference": "TIMEOUT-B-" + unique,
                "full_name": "Invented Timeout Borrower",
            },
        )
        assert borrower.status_code == 201
        loan = client.post(
            "/loans",
            json={
                "external_reference": "TIMEOUT-L-" + unique,
                "borrower_id": borrower.json()["id"],
                "product_id": "00000000-0000-0000-0000-000000000002",
                "principal_paise": 10000,
                "tenure_periods": 2,
                "first_due_date": "2026-01-31",
            },
        )
        assert loan.status_code == 201
        loan_id = loan.json()["id"]
        result = client.post(
            f"/loans/{loan_id}/disburse",
            headers={"X-Demo-User": "demo-manager"},
            json={"business_date": "2026-01-01"},
        )
        assert result.status_code == 201
        path = f"/loans/{loan_id}/repayments"
        payload = {
            "amount_paise": 1000,
            "source": "submission-timeout",
            "external_event_id": unique,
            "occurred_at": "2026-01-31T10:00:00Z",
            "business_date": "2026-01-31",
        }
        request_headers = {**headers, "Idempotency-Key": "TIMEOUT-K-" + unique}
        with httpx.Client(
            base_url=base_url, transport=LoseCommittedResponse()
        ) as lossy:
            try:
                lossy.post(path, json=payload, headers=request_headers)
            except httpx.ReadTimeout:
                pass
            else:
                raise AssertionError("Client did not observe timeout")
        before = client.get(path).json()
        assert len(before) == 1
        retry = client.post(path, json=payload, headers=request_headers)
        assert retry.status_code == 201
        assert (
            retry.json()["id"] == before[0]["id"]
            and retry.json()["journal_id"] == before[0]["journal_id"]
        )
        assert len(client.get(path).json()) == 1
        ledger = client.get(f"/loans/{loan_id}/ledger").json()
        assert sum(j["kind"] == "repayment" for j in ledger) == 1
        balance = client.get(f"/loans/{loan_id}/balance").json()
        assert (
            balance["principal_receivable_paise"],
            balance["interest_receivable_paise"],
        ) == (9100, 0)
        return {
            "passed": True,
            "injection": "Real loopback HTTP upstream response consumed, then client ReadTimeout raised",
            "retry_status": retry.status_code,
            "receipt_count": 1,
            "repayment_journal_count": 1,
            "principal_receivable_paise": 9100,
            "interest_receivable_paise": 0,
            "loan_id": loan_id,
            "receipt_id": retry.json()["id"],
            "journal_id": retry.json()["journal_id"],
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.base_url)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
