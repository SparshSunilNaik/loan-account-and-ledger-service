"""Invented deterministic input dataset and independent expected-outcome manifest."""

import argparse
import hashlib
import json
import random
from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from uuid import UUID, uuid5

from ledgercore.simulation.reference import ReferenceBook

SEED = 20261114
START, END = date(2026, 11, 1), date(2026, 11, 14)
NAMESPACE = UUID("cf11d580-fbcb-4aa1-a279-dea12233af39")
PRODUCTS = [
    {
        "id": "00000000-0000-0000-0000-000000000001",
        "code": "WEEKLY_GROUP",
        "annual_rate": "0.24",
        "frequency": "weekly",
        "interest_method": "flat",
    },
    {
        "id": "00000000-0000-0000-0000-000000000002",
        "code": "PERSONAL_EMI",
        "annual_rate": "0.12",
        "frequency": "monthly",
        "interest_method": "reducing",
    },
    {
        "id": "00000000-0000-0000-0000-000000000003",
        "code": "SMALL_BUSINESS",
        "annual_rate": "0.18",
        "frequency": "monthly",
        "interest_method": "flat",
    },
]


def stable_id(kind, index):
    return str(uuid5(NAMESPACE, f"{SEED}:{kind}:{index}"))


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def write_json(path, data):
    Path(path).write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")


def build_dataset():
    rng = random.Random(SEED)
    borrowers = [
        {
            "id": stable_id("borrower", i),
            "external_reference": f"SIM-B-{i:04d}",
            "full_name": f"Invented Borrower {i:04d}",
        }
        for i in range(250)
    ]
    loans = []
    for i in range(400):
        product = PRODUCTS[i % 3]
        loans.append(
            {
                "id": stable_id("loan", i),
                "external_reference": f"SIM-L-{i:04d}",
                "borrower_id": borrowers[i % 250]["id"],
                "product_id": product["id"],
                "principal_paise": rng.randrange(250, 1501) * 10000,
                "tenure_periods": 26 if i % 3 == 0 else 12,
                "first_due_date": (START + timedelta(days=2 + i % 3)).isoformat(),
                "disbursement_date": "2026-10-27"
                if i % 3 == 0
                else "2026-10-04"
                if i % 3 == 1
                else "2026-10-05",
                "annual_rate": product["annual_rate"],
                "frequency": product["frequency"],
                "interest_method": product["interest_method"],
            }
        )
    events = []

    def add(
        loan_index,
        day,
        second,
        category,
        subtype,
        amount,
        *,
        occurred=None,
        copy=None,
        actor="demo-officer",
        duplicate_of=None,
    ):
        sequence = len(events)
        received = datetime.combine(day, time(9), UTC) + timedelta(seconds=second)
        event = {
            "delivery_id": stable_id("delivery", sequence),
            "loan_id": loans[loan_index]["id"],
            "actor": actor,
            "source": "invented-20261114",
            "external_event_id": f"SIM-E-{sequence:05d}",
            "idempotency_key": f"SIM-K-{sequence:05d}",
            "amount_paise": amount,
            "occurred_at": (occurred or received).isoformat(),
            "received_at": received.isoformat(),
            "business_date": day.isoformat(),
            "scenario": category,
            "subtype": subtype,
        }
        if copy:
            for field in (
                "loan_id",
                "actor",
                "source",
                "external_event_id",
                "idempotency_key",
                "amount_paise",
                "occurred_at",
                "business_date",
            ):
                event[field] = copy[field]
        if duplicate_of:
            event["duplicate_of"] = duplicate_of
        events.append(event)
        return event

    ordinary = []
    for i in range(4200):
        ordinary.append(
            add(
                i % 400,
                START + timedelta(days=i // 400),
                i % 400,
                "ordinary",
                "ordinary",
                rng.randrange(100, 301) * 100,
            )
        )
    for i in range(250):
        add(
            i,
            START + timedelta(days=11),
            3600 + i,
            "out_of_order",
            "delayed",
            rng.randrange(100, 301) * 100,
            occurred=datetime.combine(START, time(8), UTC),
        )
    partials = [
        add(
            i,
            START + timedelta(days=12),
            3600 + i,
            "partial_overpayment",
            "partial",
            125 + i,
        )
        for i in range(60)
    ]
    for i in range(60):
        add(
            i + 60,
            START + timedelta(days=12),
            7200 + i,
            "partial_overpayment",
            "overpayment",
            100000000000,
        )
    for i in range(30):
        event = add(
            i,
            START + timedelta(days=12),
            10800 + i,
            "partial_overpayment",
            "source_duplicate_partial",
            0,
            copy=partials[i],
            duplicate_of=partials[i]["delivery_id"],
        )
        event["idempotency_key"] = f"SIM-SOURCE-ALIAS-{i:03d}"
    for i in range(25):
        add(
            i + 100,
            START + timedelta(days=12),
            14400 + i,
            "invalid_unauthorized",
            "zero_amount",
            0,
        )
        add(
            i + 125,
            START + timedelta(days=12),
            18000 + i,
            "invalid_unauthorized",
            "negative_amount",
            -100,
        )
        add(
            i + 150,
            START + timedelta(days=12),
            21600 + i,
            "invalid_unauthorized",
            "auditor_denied",
            100,
            actor="demo-auditor",
        )
        event = add(
            i,
            START + timedelta(days=12),
            25200 + i,
            "invalid_unauthorized",
            "idempotency_collision",
            101,
        )
        event["idempotency_key"] = ordinary[i]["idempotency_key"]
    for i in range(300):
        add(
            i,
            END,
            3600 + i,
            "duplicate",
            "exact_retry",
            0,
            copy=ordinary[i],
            duplicate_of=ordinary[i]["delivery_id"],
        )
    events.sort(key=lambda event: (event["received_at"], event["delivery_id"]))
    oracle = ReferenceBook(loans)
    current_day = START
    for event in events:
        receipt_day = date.fromisoformat(event["received_at"][:10])
        while current_day <= receipt_day:
            oracle.start_day(current_day.isoformat())
            current_day += timedelta(days=1)
        event["expected_behavior"] = oracle.deliver(event)["behavior"]
    counts = Counter(event["scenario"] for event in events)
    assert dict(counts) == {
        "ordinary": 4200,
        "out_of_order": 250,
        "partial_overpayment": 150,
        "invalid_unauthorized": 100,
        "duplicate": 300,
    }
    assert len(events) == 5000
    manifest = {
        "schema_version": 1,
        "seed": SEED,
        "simulation_start": START.isoformat(),
        "simulation_end": END.isoformat(),
        "counts": {
            "borrowers": len(borrowers),
            "loans": len(loans),
            "products": len(PRODUCTS),
            "deliveries": len(events),
            "categories": dict(counts),
        },
        "expected_behavior_counts": dict(
            Counter(e["behavior"] for e in oracle.expected.values())
        ),
        "expectations": oracle.expected,
        "expected_final": oracle.summary(),
        "expected_journals": oracle.journals,
        "expected_penalty_evaluations": oracle.penalty_evaluations,
        "expected_zero_charge_days": oracle.penalty_zero_days,
        "reference_policy": "Independent Decimal annuity spec; chronological opening-day penalties; no posting/ORM/job imports",
        "identity_policy": "Stable logical UUIDv5 identifiers map to API-generated database UUIDs. Simulation arrival times are separate from server receipt times.",
    }
    return {
        "borrowers": borrowers,
        "loans": loans,
        "products": PRODUCTS,
        "events": events,
        "manifest": manifest,
    }


def save_dataset(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    data = build_dataset()
    for name in ("borrowers", "loans", "products"):
        write_json(output / f"{name}.json", data[name])
    (output / "events.jsonl").write_text(
        "".join(encoded(e) + "\n" for e in data["events"])
    )
    digest = hashlib.sha256((output / "events.jsonl").read_bytes()).hexdigest()
    data["manifest"]["events_sha256"] = digest
    write_json(output / "scenario_manifest.json", data["manifest"])
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = save_dataset(args.output)
    print(encoded(data["manifest"]["counts"]))


if __name__ == "__main__":
    main()
