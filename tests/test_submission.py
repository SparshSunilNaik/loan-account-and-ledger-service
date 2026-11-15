import importlib.util
import json
import stat
from pathlib import Path

from ledgercore.main import app
from ledgercore.simulation import replay

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revision_metadata_without_git(monkeypatch, tmp_path):
    monkeypatch.setattr(replay, "ROOT", tmp_path)
    assert replay.source_revision() is None


def test_revision_metadata_without_git_executable(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(replay.subprocess, "check_output", missing)
    assert replay.source_revision() is None


def test_export_matches_app_and_collection_covers_all_operations():
    spec = json.loads((ROOT / "openapi/openapi.json").read_text())
    assert spec == app.openapi()
    collection = json.loads(
        (ROOT / "postman/ledgercore.postman_collection.json").read_text()
    )
    assert script("verify_submission").coverage(spec, collection) == 14
    assert len(collection["item"]) == 33


def test_private_config_and_existing_values_preserved(tmp_path):
    module = script("init_local_env")
    target = tmp_path / ".env"
    assert module.create_env(target)
    original = target.read_bytes()
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert not module.create_env(target)
    assert target.read_bytes() == original


def test_packager_excludes_runtime_and_rejects_symlinks(tmp_path):
    import pytest

    module = script("build_submission")
    (tmp_path / "src").mkdir()
    (tmp_path / "README.md").write_text("Example")
    (tmp_path / "src/app.py").write_text("pass")
    (tmp_path / "src/.env").write_text("not packaged")
    (tmp_path / "src/runtime.db").write_text("not packaged")
    (tmp_path / "src/__pycache__").mkdir()
    (tmp_path / "src/__pycache__/app.pyc").write_bytes(b"not packaged")
    assert module.source_files(tmp_path) == ["README.md", "src/app.py"]
    (tmp_path / "src/link.py").symlink_to(tmp_path / "README.md")
    with pytest.raises(ValueError, match="symlinks"):
        module.source_files(tmp_path)


def test_packager_manifest_matches_zip_bytes(tmp_path):
    import hashlib
    import zipfile

    (tmp_path / "README.md").write_text("Example")
    module = script("build_submission")
    manifest = module.build(tmp_path)
    with zipfile.ZipFile(tmp_path / "dist/ledgercore-submission.zip") as bundle:
        assert bundle.namelist() == [f["path"] for f in manifest["files"]]
        for row in manifest["files"]:
            assert hashlib.sha256(bundle.read(row["path"])).hexdigest() == row["sha256"]
    assert manifest["source_commit"] is None


def test_optional_demo_and_frontend_separation(tmp_path):
    module = script("build_submission")
    (tmp_path / "demo.txt").write_bytes(b"Exact optional script\r\n")
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend/package.json").write_text("{}")
    assert module.source_files(tmp_path) == ["demo.txt"]
    manifest = module.build(tmp_path)
    assert manifest["demo_script_included"]
    assert not manifest["frontend_included"]
    import zipfile

    with zipfile.ZipFile(tmp_path / "dist/ledgercore-submission.zip") as archive:
        assert archive.read("demo.txt") == b"Exact optional script\r\n"
        assert not any(p.startswith("frontend/") for p in archive.namelist())


def test_rebuild_preserves_previous_archive_and_writes_checksums(tmp_path):
    import hashlib

    module = script("build_submission")
    (tmp_path / "README.md").write_text("Original")
    first = module.build(tmp_path)
    original = (tmp_path / "dist/ledgercore-submission.zip").read_bytes()
    (tmp_path / "README.md").write_text("Revised")
    second = module.build(tmp_path)
    backup = tmp_path / second["previous_archive_backup"]
    assert (backup / "ledgercore-submission.zip").read_bytes() == original
    assert hashlib.sha256(original).hexdigest() == first["sha256"]
    for line in (tmp_path / "dist/SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == digest
    rows = (
        (tmp_path / "dist/ledgercore-submission.files.sha256").read_text().splitlines()
    )
    assert len(rows) == second["member_count"]
