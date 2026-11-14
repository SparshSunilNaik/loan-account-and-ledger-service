from uuid import uuid4

import pytest
from sqlalchemy import select, text

from ledgercore.models.entities import Loan, LoanProduct, RepaymentSchedule
from ledgercore.services.schedules import generate_schedule

pytestmark = pytest.mark.integration


def borrower(client, reference="B-001"):
    response = client.post(
        "/borrowers",
        json={
            "external_reference": reference,
            "full_name": "Asha Rao",
            "phone": "+919876543210",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def loan_body(client, product_code="PERSONAL_EMI"):
    b = borrower(client)
    products = client.get("/loan-products").json()
    product = next(p for p in products if p["code"] == product_code)
    return {
        "external_reference": "L-001",
        "borrower_id": b["id"],
        "product_id": product["id"],
        "principal_paise": 10000,
        "tenure_periods": 2,
        "first_due_date": "2026-01-31",
    }


def test_borrower_round_trip(client):
    b = borrower(client)
    assert client.get(f"/borrowers/{b['id']}").json() == b
    assert (
        client.post(
            "/borrowers", json={"external_reference": "B-001", "full_name": "Other"}
        ).status_code
        == 409
    )
    assert client.get(f"/borrowers/{uuid4()}").status_code == 404
    assert client.get("/borrowers/not-a-uuid").status_code == 422


@pytest.mark.parametrize(
    "patch",
    [
        {"full_name": "  "},
        {"full_name": 42},
        {"phone": "abc"},
        {"unknown": True},
        {"external_reference": "bad ref"},
    ],
)
def test_borrower_validation(client, patch):
    body = {"external_reference": "B-001", "full_name": "Asha"} | patch
    assert client.post("/borrowers", json=body).status_code == 422


def test_products(client):
    products = client.get("/loan-products").json()
    assert len(products) == 3
    assert {
        (p["code"], p["annual_rate"], p["frequency"], p["interest_method"])
        for p in products
    } == {
        ("WEEKLY_GROUP", "0.2400000000", "weekly", "flat"),
        ("PERSONAL_EMI", "0.1200000000", "monthly", "reducing"),
        ("SMALL_BUSINESS", "0.1800000000", "monthly", "flat"),
    }


@pytest.mark.parametrize("code", ["PERSONAL_EMI", "WEEKLY_GROUP", "SMALL_BUSINESS"])
def test_origination_schedule_and_snapshots(client, db, code):
    body = loan_body(client, code)
    response = client.post("/loans", json=body)
    assert response.status_code == 201, response.text
    loan = response.json()
    assert loan["status"] == "originated"
    assert not any("balance" in key or "outstanding" in key for key in loan)
    assert client.get(f"/loans/{loan['id']}").json() == loan
    rows = client.get(f"/loans/{loan['id']}/schedule").json()
    assert len(rows) == 2
    assert all(r["loan_id"] == loan["id"] for r in rows)
    assert sum(r["principal_due_paise"] for r in rows) == 10000
    if code == "PERSONAL_EMI":
        assert [(r["principal_due_paise"], r["interest_due_paise"]) for r in rows] == [
            (4975, 100),
            (5025, 50),
        ]
    # Product edits cannot alter either stored rows or reproducibility from the loan snapshot.
    db.rollback()  # finish GET's read transaction before starting an explicit write
    with db.begin():
        product = db.get(LoanProduct, loan["product_id"])
        product.annual_rate = 0
        product.frequency = "weekly"
    assert client.get(f"/loans/{loan['id']}/schedule").json() == rows
    snapshot = db.get(Loan, loan["id"])
    regenerated = generate_schedule(
        snapshot.principal_paise,
        snapshot.annual_rate,
        snapshot.tenure_periods,
        snapshot.interest_method,
        snapshot.frequency,
        snapshot.first_due_date,
    )
    assert [
        (r.principal_due_paise, r.interest_due_paise, r.due_date.isoformat())
        for r in regenerated
    ] == [
        (r["principal_due_paise"], r["interest_due_paise"], r["due_date"]) for r in rows
    ]


@pytest.mark.parametrize(
    "patch",
    [
        {"principal_paise": 0},
        {"principal_paise": -1},
        {"principal_paise": 1.5},
        {"principal_paise": True},
        {"principal_paise": "100"},
        {"principal_paise": 100000000001},
        {"tenure_periods": 0},
        {"tenure_periods": 601},
        {"tenure_periods": True},
        {"tenure_periods": "3"},
        {"first_due_date": "bad"},
        {"first_due_date": 0},
        {"first_due_date": True},
        {"first_due_date": "2026-01-31T00:00:00"},
        {"first_due_date": "9999-01-01"},
        {"annual_rate": "0.99"},
        {"borrower_id": "invalid"},
    ],
)
def test_invalid_loan_inputs(client, patch):
    body = loan_body(client) | patch
    assert client.post("/loans", json=body).status_code == 422


def test_missing_references_inactive_and_duplicates(client, db):
    body = loan_body(client)
    assert (
        client.post("/loans", json=body | {"borrower_id": str(uuid4())}).status_code
        == 422
    )
    assert (
        client.post("/loans", json=body | {"product_id": str(uuid4())}).status_code
        == 422
    )
    with db.begin():
        product = db.get(LoanProduct, body["product_id"])
        product.active = False
    assert client.post("/loans", json=body).status_code == 422
    with db.begin():
        product.active = True
    assert client.post("/loans", json=body).status_code == 201
    assert client.post("/loans", json=body).status_code == 409
    assert len(db.scalars(select(RepaymentSchedule)).all()) == 2
    assert client.get(f"/loans/{uuid4()}").status_code == 404
    assert client.get(f"/loans/{uuid4()}/schedule").status_code == 404


def test_health_and_openapi(client):
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}
    assert client.get("/docs").status_code == 200
    spec = client.get("/openapi.json").json()
    assert {"/borrowers", "/loan-products", "/loans", "/health"} <= set(spec["paths"])
    assert "/repayments" not in spec["paths"]


def test_fresh_migration_schema(db):
    tables = set(
        db.scalars(
            text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            )
        )
    )
    assert tables == {
        "alembic_version",
        "borrowers",
        "loan_products",
        "loans",
        "repayment_schedules",
        "repayments",
        "repayment_allocations",
        "idempotency_requests",
        "ledger_accounts",
        "ledger_journals",
        "ledger_entries",
        "accrual_records",
        "users",
        "audit_events",
    }
    assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0005"


def test_unavailable_database_is_503(client, monkeypatch):
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session

    def unavailable(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("unavailable"))

    monkeypatch.setattr(Session, "execute", unavailable)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
