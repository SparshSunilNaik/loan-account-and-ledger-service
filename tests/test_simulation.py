"""Generator/reference tests plus a complete 5,000-delivery real HTTP replay."""

import hashlib
import json
import os
from collections import Counter
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from ledgercore.jobs.accrual import daily_charge
from ledgercore.simulation.generate import build_dataset, encoded, save_dataset
from ledgercore.simulation.reference import reference_schedule
from ledgercore.simulation.replay import run_replay


def test_exact_counts_and_deterministic_order(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    data = save_dataset(first)
    save_dataset(second)
    for path in first.iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes()
    assert len(data["borrowers"]) == 250 and len(data["loans"]) == 400
    assert len(data["events"]) == 5000 and len(data["products"]) == 3
    assert Counter(e["scenario"] for e in data["events"]) == {
        "ordinary": 4200,
        "duplicate": 300,
        "out_of_order": 250,
        "partial_overpayment": 150,
        "invalid_unauthorized": 100,
    }
    assert data["events"] == sorted(
        data["events"], key=lambda event: (event["received_at"], event["delivery_id"])
    )
    assert all(
        b["full_name"].startswith("Invented Borrower") and "phone" not in b
        for b in data["borrowers"]
    )


def test_duplicate_identity_and_economic_inversions():
    data = build_dataset()
    by_id = {e["delivery_id"]: e for e in data["events"]}
    payload_fields = (
        "loan_id",
        "actor",
        "source",
        "external_event_id",
        "idempotency_key",
        "amount_paise",
        "occurred_at",
        "business_date",
    )
    maxima, delayed = {}, 0
    financial_dates = {}
    for event in data["events"]:
        if event["subtype"] == "exact_retry":
            original = by_id[event["duplicate_of"]]
            assert {k: event[k] for k in payload_fields} == {
                k: original[k] for k in payload_fields
            }
            assert event["received_at"] > original["received_at"]
        if event["scenario"] == "out_of_order":
            assert event["occurred_at"] < maxima[event["loan_id"]]
            assert event["business_date"] == event["received_at"][:10]
            delayed += 1
        if event["expected_behavior"] == "accepted_new":
            assert event["business_date"] >= financial_dates.get(event["loan_id"], "")
            financial_dates[event["loan_id"]] = event["business_date"]
            maxima[event["loan_id"]] = max(
                maxima.get(event["loan_id"], ""), event["occurred_at"]
            )
    assert delayed == 250


def test_independent_manifest_has_specific_expected_outcomes():
    manifest = build_dataset()["manifest"]
    assert manifest["expected_behavior_counts"] == {
        "accepted_new": 4510,
        "duplicate": 330,
        "invalid_amount": 50,
        "authorization_denied": 25,
        "idempotency_collision": 25,
        "overpayment_rejected": 60,
    }
    assert len(manifest["expectations"]) == 5000
    assert manifest["expected_journals"] == 9903
    assert manifest["expected_zero_charge_days"] == 78


def test_independent_schedule_matches_manual_annuity_example():
    rows = reference_schedule(
        {
            "principal_paise": 10000,
            "annual_rate": "0.12",
            "tenure_periods": 2,
            "frequency": "monthly",
            "interest_method": "reducing",
            "first_due_date": "2026-01-31",
        }
    )
    assert [(r["principal_due_paise"], r["interest_due_paise"]) for r in rows] == [
        (4975, 100),
        (5025, 50),
    ]
    assert [r["due_date"] for r in rows] == ["2026-01-31", "2026-02-28"]


@pytest.mark.parametrize(
    "basis,expected",
    [(0, 0), (999, 0), (1000, 1), (2999, 1), (3000, 2), (100000000000, 50000000)],
)
def test_daily_rounding_examples_and_ambient_precision(basis, expected):
    with localcontext() as ctx:
        ctx.prec = 4
        assert daily_charge(basis) == expected


@pytest.mark.parametrize("invalid", [True, -1, 1.5, Decimal("1"), 100000000001])
def test_daily_charge_requires_bounded_integer_basis(invalid):
    with pytest.raises(ValueError):
        daily_charge(invalid)


@pytest.mark.integration
def test_full_5000_delivery_http_replay(pg_engine, tmp_path):
    output = Path(os.environ.get("REPLAY_TEST_OUTPUT", str(tmp_path / "observed")))
    report = run_replay(pg_engine.url.set(database="postgres"), output)
    assert report["validation_passed"] and report["completed"]
    assert report["submitted"] == 5000
    assert report["accepted_new_repayments"] == 4510
    assert report["duplicate_deliveries_detected"] == 330
    assert report["exact_retry_deliveries"] == 300
    assert report["source_duplicate_deliveries"] == 30
    assert report["out_of_order_unique_accepted"] == 250
    assert report["idempotency_collisions"] == 25
    assert report["http_status_counts"] == {
        "201": 4840,
        "400": 60,
        "403": 25,
        "409": 25,
        "422": 50,
    }
    assert (
        report["unbalanced_journal_count"] == 0
        and report["total_debit_paise"] == report["total_credit_paise"]
    )
    assert report["repeated_accrual_no_mutation"]
    outcomes = [
        json.loads(line)
        for line in (output / "replay_outcomes.jsonl").read_text().splitlines()
    ]
    assert len(outcomes) == 5000 and len({e["delivery_id"] for e in outcomes}) == 5000
    assert all(e["expectation_matched"] for e in outcomes)
    assert (
        Counter(e["observed_behavior"] for e in outcomes)
        == report["observed_behavior_counts"]
    )
    manifest = json.loads((output / "scenario_manifest.json").read_text())
    assert (
        hashlib.sha256((output / "events.jsonl").read_bytes()).hexdigest()
        == manifest["events_sha256"]
    )
    assert (
        len(encoded(report["reproducibility"]["financial_sha256"])) == 66
    )  # 64 hex characters and JSON quotes
    reconciliation = json.loads((output / "reconciliation_report.json").read_text())
    assert reconciliation["passed"] and reconciliation["penalty_basis_errors"] == 0
    assert not any(
        reconciliation[k]
        for k in (
            "principal_differences",
            "interest_differences",
            "penalty_differences",
            "errors",
        )
    )
