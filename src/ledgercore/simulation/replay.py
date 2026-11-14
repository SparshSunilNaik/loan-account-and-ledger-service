"""Replay every generated delivery through a real loopback HTTP server and isolated DB."""

import argparse
import hashlib
import os
import platform
import socket
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from ledgercore.jobs.accrual import run_job
from ledgercore.models.entities import (
    AccrualRecord,
    AuditEvent,
    LedgerJournal,
    Repayment,
)
from ledgercore.simulation.generate import (
    END,
    SEED,
    START,
    encoded,
    save_dataset,
    write_json,
)
from ledgercore.simulation.reconcile import reconcile
from ledgercore.simulation.reference import reference_schedule

ROOT = Path(__file__).resolve().parents[3]


def source_digest():
    digest = hashlib.sha256()
    files = sorted(
        [
            *ROOT.glob("src/**/*.py"),
            *ROOT.glob("migrations/**/*.py"),
            ROOT / "pyproject.toml",
            ROOT / "uv.lock",
        ]
    )
    for path in files:
        digest.update(str(path.relative_to(ROOT)).encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def must(response, status):
    if response.status_code != status:
        raise RuntimeError(
            f"Initialization HTTP status {response.status_code}; expected {status}"
        )
    return response.json()


def run_replay(admin_url, output: Path):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Replay output must be a fresh empty directory")
    data = save_dataset(output)
    manifest = data["manifest"]
    admin_url = make_url(admin_url)
    if admin_url.get_backend_name() != "postgresql":
        raise ValueError("Replay requires real PostgreSQL")
    database_name = "ledgercore_replay_" + uuid4().hex
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{database_name}"'))
    url = admin_url.set(database=database_name)
    env = {
        **os.environ,
        "DATABASE_URL": url.render_as_string(hide_password=False),
        "DEMO_AUTH_ENABLED": "true",
    }
    engine = create_engine(
        url,
        connect_args={"options": "-c timezone=UTC"},
        isolation_level="READ COMMITTED",
    )
    factory = sessionmaker(engine, expire_on_commit=False)
    process = None
    server_log = tempfile.TemporaryFile(mode="w+")
    started = time.perf_counter()
    started_at = datetime.now(UTC).isoformat()
    report = {
        "completed": False,
        "validation_passed": False,
        "seed": SEED,
        "submitted": 0,
    }
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "ledgercore.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
            ],
            cwd=ROOT,
            env=env,
            stdout=server_log,
            stderr=server_log,
        )
        base_url = f"http://127.0.0.1:{port}"
        with httpx.Client(
            base_url=base_url, headers={"X-Demo-User": "demo-officer"}, timeout=60
        ) as client:
            deadline = time.monotonic() + 20
            while True:
                try:
                    if client.get("/health").status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Loopback replay server did not become ready")
                time.sleep(0.05)
            products = must(client.get("/loan-products"), 200)
            if {p["code"] for p in products} != {p["code"] for p in data["products"]}:
                raise RuntimeError("Unexpected product seed data")
            borrowers, loans, schedule_numbers = {}, {}, {}
            for row in data["borrowers"]:
                body = {key: row[key] for key in ("external_reference", "full_name")}
                borrowers[row["id"]] = must(client.post("/borrowers", json=body), 201)[
                    "id"
                ]
            for row in data["loans"]:
                body = {
                    key: row[key]
                    for key in (
                        "external_reference",
                        "product_id",
                        "principal_paise",
                        "tenure_periods",
                        "first_due_date",
                    )
                }
                body["borrower_id"] = borrowers[row["borrower_id"]]
                created = must(client.post("/loans", json=body), 201)
                loans[row["id"]] = created["id"]
                schedule = must(client.get(f"/loans/{created['id']}/schedule"), 200)
                expected = reference_schedule(row)
                if [{k: r[k] for k in expected[0]} for r in schedule] != expected:
                    raise RuntimeError("Schedule differs from independent reference")
                schedule_numbers.update(
                    {r["id"]: r["instalment_number"] for r in schedule}
                )
                must(
                    client.post(
                        f"/loans/{created['id']}/disburse",
                        headers={"X-Demo-User": "demo-manager"},
                        json={"business_date": row["disbursement_date"]},
                    ),
                    201,
                )
            write_json(
                output / "identity_map.json", {"borrowers": borrowers, "loans": loans}
            )
            print(
                "Initialized 250 borrowers and 400 disbursed loans through HTTP",
                flush=True,
            )
            current_day = START
            mismatches, normalized = [], []
            originals, response_ids, latest_economic = {}, set(), {}
            behavior_counts, rejection_reasons, status_counts = (
                Counter(),
                Counter(),
                Counter(),
            )
            duplicate_subtypes = Counter()
            out_of_order = inversions_all = 0
            accrual_runs = []
            with (output / "replay_outcomes.jsonl").open("w") as outcomes:
                for event in data["events"]:
                    received_day = date.fromisoformat(event["received_at"][:10])
                    while current_day <= received_day:
                        result = run_job(
                            factory,
                            current_day,
                            catch_up=True,
                            loan_ids=[UUID(value) for value in loans.values()],
                        )
                        if result["failures"]:
                            raise RuntimeError(
                                "Replay accrual failed: " + encoded(result["failures"])
                            )
                        accrual_runs.append(
                            {
                                "business_date": current_day.isoformat(),
                                "evaluated_days": sum(
                                    r["evaluated_days"] for r in result["results"]
                                ),
                                "charged_days": sum(
                                    r["charged_days"] for r in result["results"]
                                ),
                                "penalty_paise": sum(
                                    r["penalty_paise"] for r in result["results"]
                                ),
                            }
                        )
                        print(
                            f"Accrued through {current_day}; delivered {report['submitted']} events",
                            flush=True,
                        )
                        current_day += timedelta(days=1)
                    body = {
                        key: event[key]
                        for key in (
                            "amount_paise",
                            "source",
                            "external_event_id",
                            "occurred_at",
                            "business_date",
                        )
                    }
                    attempted_at = datetime.now(UTC).isoformat()
                    response = client.post(
                        f"/loans/{loans[event['loan_id']]}/repayments",
                        json=body,
                        headers={
                            "X-Demo-User": event["actor"],
                            "Idempotency-Key": event["idempotency_key"],
                            "X-Correlation-ID": event["delivery_id"],
                        },
                    )
                    actual = response.json()
                    report["submitted"] += 1
                    status_counts[str(response.status_code)] += 1
                    expectation = manifest["expectations"][event["delivery_id"]]
                    mismatch = response.status_code != expectation["status"]
                    is_new = (
                        response.status_code == 201
                        and actual.get("id") not in response_ids
                    )
                    behavior = (
                        "accepted_new"
                        if is_new
                        else "duplicate"
                        if response.status_code == 201
                        else {
                            400: "overpayment_rejected",
                            403: "authorization_denied",
                            422: "invalid_amount",
                        }.get(
                            response.status_code,
                            "idempotency_collision"
                            if response.status_code == 409
                            and "Idempotency" in actual.get("detail", "")
                            else "unexpected_rejection",
                        )
                    )
                    behavior_counts[behavior] += 1
                    if behavior == "duplicate":
                        duplicate_subtypes[event["subtype"]] += 1
                    if response.status_code != 201:
                        rejection_reasons[
                            actual.get("detail", "validation_error")
                            if isinstance(actual.get("detail"), str)
                            else "validation_error"
                        ] += 1
                    allocations = []
                    if response.status_code == 201:
                        response_ids.add(actual["id"])
                        allocations = [
                            {
                                "instalment_number": schedule_numbers[a["schedule_id"]],
                                "component": a["component"],
                                "amount_paise": a["amount_paise"],
                            }
                            for a in actual["allocations"]
                        ]
                        mismatch |= allocations != expectation.get("allocations", [])
                        if behavior == "duplicate":
                            mismatch |= actual != originals.get(
                                expectation.get("canonical_delivery_id")
                            )
                        else:
                            originals[event["delivery_id"]] = actual
                            if event["occurred_at"] < latest_economic.get(
                                event["loan_id"], ""
                            ):
                                out_of_order += 1
                            latest_economic[event["loan_id"]] = max(
                                latest_economic.get(event["loan_id"], ""),
                                event["occurred_at"],
                            )
                    mismatch |= behavior != expectation["behavior"]
                    # All-attempt inversions are reported separately from unique accepted delayed events.
                    if event["occurred_at"] < latest_economic.get(event["loan_id"], ""):
                        inversions_all += 1
                    if mismatch:
                        mismatches.append(
                            {
                                "delivery_id": event["delivery_id"],
                                "expected": expectation,
                                "actual_status": response.status_code,
                                "actual_behavior": behavior,
                            }
                        )
                    outcomes.write(
                        encoded(
                            {
                                "delivery_id": event["delivery_id"],
                                "loan_id": event["loan_id"],
                                "scenario": event["scenario"],
                                "subtype": event["subtype"],
                                "simulated_received_at": event["received_at"],
                                "attempted_at": attempted_at,
                                "http_status": response.status_code,
                                "observed_behavior": behavior,
                                "response": actual,
                                "expectation_matched": not mismatch,
                            }
                        )
                        + "\n"
                    )
                    normalized.append(
                        {
                            "delivery_id": event["delivery_id"],
                            "status": response.status_code,
                            "behavior": behavior,
                            "allocations": allocations,
                        }
                    )
            api_mismatches = []
            for logical, actual_id in loans.items():
                observed = must(
                    client.get(
                        f"/loans/{actual_id}/balance",
                        headers={"X-Demo-User": "demo-auditor"},
                    ),
                    200,
                )
                expected = manifest["expected_final"][logical]
                for component in ("principal", "interest", "penalty"):
                    if (
                        observed[component + "_receivable_paise"]
                        != expected[component + "_paise"]
                    ):
                        api_mismatches.append(
                            {"loan_id": logical, "component": component}
                        )
            with factory() as session:
                before = [
                    session.scalar(select(func.count()).select_from(model))
                    for model in (LedgerJournal, AccrualRecord, AuditEvent, Repayment)
                ]
            repeated = run_job(
                factory,
                END,
                catch_up=True,
                loan_ids=[UUID(value) for value in loans.values()],
            )
            with factory() as session:
                after = [
                    session.scalar(select(func.count()).select_from(model))
                    for model in (LedgerJournal, AccrualRecord, AuditEvent, Repayment)
                ]
                reconciliation = reconcile(
                    session,
                    {key: UUID(value) for key, value in loans.items()},
                    manifest,
                )
                postgres_version = session.scalar(text("SHOW server_version"))
            repeat_passed = (
                before == after
                and not repeated["failures"]
                and all(
                    r["evaluated_days"] == 0 and r["interest_journals"] == 0
                    for r in repeated["results"]
                )
            )
            write_json(output / "reconciliation_report.json", reconciliation)
            financial_fingerprint = hashlib.sha256(
                encoded(
                    {
                        "outcomes": normalized,
                        "per_loan": reconciliation["per_loan"],
                        "debits": reconciliation["total_debit_paise"],
                        "credits": reconciliation["total_credit_paise"],
                        "journals": reconciliation["posted_journals"],
                    }
                ).encode()
            ).hexdigest()
            actual_counts = reconciliation["database_counts"]
            behavioral_counts_match = (
                dict(behavior_counts) == manifest["expected_behavior_counts"]
                and actual_counts["accepted_receipts"]
                == behavior_counts["accepted_new"]
            )
            counts_match = (
                actual_counts["borrowers"],
                actual_counts["loans"],
                actual_counts["products"],
            ) == (250, 400, 3)
            report.update(
                {
                    "completed": True,
                    "validation_passed": not mismatches
                    and not api_mismatches
                    and reconciliation["passed"]
                    and repeat_passed
                    and counts_match
                    and behavioral_counts_match
                    and report["submitted"] == 5000,
                    "generated_counts": manifest["counts"],
                    "database_counts": actual_counts,
                    "http_status_counts": dict(status_counts),
                    "observed_behavior_counts": dict(behavior_counts),
                    "accepted_new_repayments": behavior_counts["accepted_new"],
                    "duplicate_deliveries_detected": behavior_counts["duplicate"],
                    "exact_retry_deliveries": duplicate_subtypes["exact_retry"],
                    "source_duplicate_deliveries": duplicate_subtypes[
                        "source_duplicate_partial"
                    ],
                    "out_of_order_unique_accepted": out_of_order,
                    "economic_inversions_all_attempts": inversions_all,
                    "rejected_by_reason": dict(rejection_reasons),
                    "idempotency_collisions": behavior_counts["idempotency_collision"],
                    "expectation_mismatches": mismatches,
                    "api_balance_mismatches": api_mismatches,
                    "repeated_accrual_no_mutation": repeat_passed,
                    "posted_journals": reconciliation["posted_journals"],
                    "total_debit_paise": reconciliation["total_debit_paise"],
                    "total_credit_paise": reconciliation["total_credit_paise"],
                    "unbalanced_journal_count": reconciliation[
                        "unbalanced_journal_count"
                    ],
                    "principal_difference_count": len(
                        reconciliation["principal_differences"]
                    ),
                    "interest_difference_count": len(
                        reconciliation["interest_differences"]
                    ),
                    "penalty_difference_count": len(
                        reconciliation["penalty_differences"]
                    ),
                    "accrual_runs": accrual_runs,
                    "runtime_seconds": round(time.perf_counter() - started, 3),
                    "started_at": started_at,
                    "finished_at": datetime.now(UTC).isoformat(),
                    "reproducibility": {
                        "seed": SEED,
                        "events_sha256": manifest["events_sha256"],
                        "financial_sha256": financial_fingerprint,
                        "clock_start": START.isoformat(),
                        "clock_end": END.isoformat(),
                        "source_base_commit": subprocess.check_output(
                            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                        ).strip(),
                        "source_sha256": source_digest(),
                        "python": platform.python_version(),
                        "platform": platform.system(),
                        "postgresql": postgres_version,
                        "dependencies": {
                            name: version(name)
                            for name in ("fastapi", "sqlalchemy", "psycopg", "httpx")
                        },
                        "nondeterministic_fields": [
                            "API-generated UUIDs",
                            "server receipt/audit times",
                            "runtime",
                            "attempted_at",
                        ],
                        "transport": "real TCP loopback HTTP / Uvicorn",
                    },
                }
            )
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        raise
    finally:
        write_json(output / "replay_report.json", report)
        if process:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        server_log.close()
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE "{database_name}" WITH (FORCE)'))
        admin.dispose()
    if not report["validation_passed"]:
        raise RuntimeError(
            "Replay validation failed; inspect retained observed artifacts"
        )
    print(
        encoded(
            {
                key: report[key]
                for key in (
                    "submitted",
                    "accepted_new_repayments",
                    "duplicate_deliveries_detected",
                    "out_of_order_unique_accepted",
                    "validation_passed",
                    "runtime_seconds",
                )
            }
        ),
        flush=True,
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    url = os.getenv("REPLAY_ADMIN_DATABASE_URL")
    if not url:
        parser.error(
            "Set REPLAY_ADMIN_DATABASE_URL to a PostgreSQL role with CREATE DATABASE"
        )
    run_replay(url, args.output)


if __name__ == "__main__":
    main()
