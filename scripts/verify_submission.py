"""Review retained evidence and validate exports; optional live/fresh-replay comparisons.

Run with: uv run --with openapi-spec-validator==0.7.2 python scripts/verify_submission.py
"""

import argparse
import ast
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

import httpx

from ledgercore.simulation.generate import build_dataset
from ledgercore.simulation.replay import source_digest

ROOT = Path(__file__).resolve().parents[1]
BASE = "e88025dc66525f7d29048f1bb1840fe1bedc66a4"
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


def read(path):
    return json.loads(path.read_text())


def normalize_path(path):
    path = path.split("?")[0].replace("{{baseUrl}}", "")
    return re.sub(r"\{\{[^}]+\}\}|\{[^}]+\}", "{}", path)


def coverage(spec, collection):
    implemented = {
        (method.upper(), normalize_path(path))
        for path, item in spec["paths"].items()
        for method in item
        if method in HTTP_METHODS
    }
    requests = {
        (i["request"]["method"], normalize_path(i["request"]["url"]))
        for i in collection["item"]
    }
    assert implemented <= requests, sorted(implemented - requests)
    return len(implemented)


class NormalizeRevision(ast.NodeTransformer):
    def visit_Dict(self, node):
        self.generic_visit(node)
        for i, key in enumerate(node.keys):
            if isinstance(key, ast.Constant) and key.value == "source_base_commit":
                node.values[i] = ast.Constant(value=None)
        return node


def verify_revision_change(original, current):
    before, after = ast.parse(original), ast.parse(current)
    after.body = [
        n
        for n in after.body
        if not (isinstance(n, ast.FunctionDef) and n.name == "source_revision")
    ]
    assert ast.dump(NormalizeRevision().visit(before)) == ast.dump(
        NormalizeRevision().visit(after)
    ), "Unexpected production logic change"


def committed_source_review():
    # Validate the original report against the exact committed Phase 3 bytes, rather than
    # replacing its historical source digest after the ZIP metadata portability fix.
    names = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", BASE], cwd=ROOT, text=True
    ).splitlines()
    names = sorted(
        n
        for n in names
        if (n.startswith(("src/", "migrations/")) and n.endswith(".py"))
        or n in ("pyproject.toml", "uv.lock")
    )
    digest = hashlib.sha256()
    for name in names:
        content = subprocess.check_output(["git", "show", f"{BASE}:{name}"], cwd=ROOT)
        digest.update(name.encode() + b"\0" + content)
        if name == "src/ledgercore/simulation/replay.py":
            verify_revision_change(content.decode(), (ROOT / name).read_text())
        else:
            assert content == (ROOT / name).read_bytes(), (
                f"Financial/dependency source changed: {name}"
            )
    return digest.hexdigest()


def verify_evidence():
    directory = ROOT / "artifacts/phase3"
    manifest, report, rec = [
        read(directory / name)
        for name in (
            "scenario_manifest.json",
            "replay_report.json",
            "reconciliation_report.json",
        )
    ]
    generated = build_dataset()
    events = [
        json.loads(line)
        for line in (directory / "events.jsonl").read_text().splitlines()
    ]
    outcomes = [
        json.loads(line)
        for line in (directory / "replay_outcomes.jsonl").read_text().splitlines()
    ]
    assert events == generated["events"] and len(events) == len(outcomes) == 5000
    for name in ("borrowers", "loans", "products"):
        assert read(directory / f"{name}.json") == generated[name]
    assert {k: v for k, v in manifest.items() if k != "events_sha256"} == generated[
        "manifest"
    ]
    assert (
        hashlib.sha256((directory / "events.jsonl").read_bytes()).hexdigest()
        == report["reproducibility"]["events_sha256"]
        == manifest["events_sha256"]
    )
    identities, actual_counts, latest = {}, Counter(), {}
    inversions = 0
    for event, outcome in zip(events, outcomes, strict=True):
        assert event["delivery_id"] == outcome["delivery_id"]
        expectation = manifest["expectations"][event["delivery_id"]]
        assert outcome["http_status"] == expectation["status"]
        if outcome["http_status"] == 201:
            response = outcome["response"]
            if response["id"] in identities:
                assert response == identities[response["id"]]
                actual_counts["duplicate"] += 1
            else:
                identities[response["id"]] = response
                actual_counts["accepted_new"] += 1
                if event["occurred_at"] < latest.get(event["loan_id"], ""):
                    inversions += 1
                latest[event["loan_id"]] = max(
                    latest.get(event["loan_id"], ""), event["occurred_at"]
                )
        else:
            actual_counts[str(outcome["http_status"])] += 1
    assert dict(actual_counts) == {
        "accepted_new": 4510,
        "duplicate": 330,
        "400": 60,
        "403": 25,
        "409": 25,
        "422": 50,
    }
    assert inversions == 250
    assert (
        report["validation_passed"]
        and rec["passed"]
        and rec["unbalanced_journal_count"] == 0
    )
    assert rec["total_debit_paise"] == rec["total_credit_paise"] == 3641480368
    assert rec["posted_journals"] == 9903 and rec["penalty_basis_errors"] == 0
    assert not any(
        rec[k]
        for k in (
            "errors",
            "principal_differences",
            "interest_differences",
            "penalty_differences",
        )
    )
    for row in rec["per_loan"]:
        assert row["ledger"] == row["operational"]
        assert row["ledger"] == {
            c: manifest["expected_final"][row["loan_id"]][c + "_paise"]
            for c in ("principal", "interest", "penalty")
        }
    return report


def main():
    from jsonschema import Draft4Validator
    from openapi_spec_validator import validate

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url")
    parser.add_argument("--fresh-replay", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    spec, collection = (
        read(ROOT / "docs/openapi.json"),
        read(ROOT / "docs/postman/ledgercore.postman_collection.json"),
    )
    validate(spec)
    Draft4Validator(read(ROOT / "docs/postman/collection.schema.json")).validate(
        collection
    )
    operation_count = coverage(spec, collection)
    if args.base_url:
        response = httpx.get(args.base_url.rstrip("/") + "/openapi.json")
        response.raise_for_status()
        assert response.json() == spec
    report = verify_evidence()
    historical_verified = False
    if (ROOT / ".git").exists():
        assert committed_source_review() == report["reproducibility"]["source_sha256"]
        historical_verified = True
    fresh_verified = False
    if args.fresh_replay:
        fresh = read(args.fresh_replay)
        assert fresh["validation_passed"]
        for key in ("events_sha256", "financial_sha256"):
            assert fresh["reproducibility"][key] == report["reproducibility"][key]
        assert fresh["reproducibility"]["source_sha256"] == source_digest()
        fresh_verified = True
    result = {
        "passed": True,
        "openapi_version": spec["openapi"],
        "documented_operations": operation_count,
        "postman_requests": len(collection["item"]),
        "postman_official_schema_valid": True,
        "live_openapi_equal": bool(args.base_url),
        "retained_5000_outcomes_recounted": True,
        "phase3_commit_source_digest_verified": historical_verified,
        "financial_source_unchanged": historical_verified,
        "fresh_replay_financial_hash_matches": fresh_verified,
        "metadata_only_exception": "Replay revision becomes null when Git metadata is absent; checked by AST comparison in the repository",
    }
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
