"""Build an allowlisted submission ZIP and a byte-level member manifest (no Git required)."""

import hashlib
import json
import shutil
import stat
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    ".dockerignore",
    ".env.example",
    ".gitignore",
    ".gitattributes",
    ".python-version",
    "Dockerfile",
    "README.md",
    "alembic.ini",
    "docker-compose.yml",
    "demo.txt",
    "pyproject.toml",
    "uv.lock",
}
TREES = (
    "src",
    "migrations",
    "tests",
    "scripts",
    "openapi",
    "postman",
    "writeup",
    "artifacts/phase3",
)
EXCLUDED = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".env",
    "node_modules",
    "frontend",
    ".mypy_cache",
    ".coverage",
    ".DS_Store",
}


def include_file(relative):
    return not (
        any(
            part in EXCLUDED
            or (part.startswith(".env.") and part != ".env.example")
            or part in {".pgpass", ".netrc"}
            for part in relative.parts
        )
        or relative.suffix
        in {".pyc", ".pyo", ".log", ".db", ".sqlite", ".sqlite3", ".dump", ".zip"}
    )


def source_files(root=ROOT):
    candidates = [root / name for name in ROOT_FILES if (root / name).exists()]
    for tree in TREES:
        directory = root / tree
        if directory.exists():
            candidates.extend(p for p in directory.rglob("*") if p.is_file())
    paths = []
    for path in candidates:
        relative = path.relative_to(root)
        if not include_file(relative):
            continue
        if path.is_symlink():
            raise ValueError(f"Submission symlinks are not permitted: {relative}")
        paths.append(relative.as_posix())
    return sorted(set(paths))


def backup_existing(root):
    """Preserve the exact previous archive/evidence before replacing any inventory."""
    output = root / "dist"
    archive = output / "ledgercore-submission.zip"
    if not archive.exists():
        return None
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    backup = output / "backups" / f"{stamp}-{digest[:12]}"
    backup.mkdir(parents=True, exist_ok=False)
    for name in (
        archive.name,
        "ledgercore-submission.manifest.json",
        "ledgercore-submission.files.sha256",
        "ledgercore-submission.included-files.txt",
        "SHA256SUMS",
        "zip_validation.json",
        "archive_security_check.json",
    ):
        path = output / name
        if path.is_file():
            shutil.copy2(path, backup / name)
    assert hashlib.sha256((backup / archive.name).read_bytes()).hexdigest() == digest
    (backup / "backup_verification.json").write_text(
        json.dumps(
            {
                "archive_sha256": digest,
                "size_bytes": archive.stat().st_size,
                "byte_identical_backup": True,
            },
            indent=2,
        )
        + "\n"
    )
    return backup.relative_to(root).as_posix()


def build(root=ROOT):
    previous_backup = backup_existing(root)
    output = root / "dist"
    output.mkdir(exist_ok=True)
    included = output / "ledgercore-submission.included-files.txt"
    included.touch(exist_ok=True)
    paths = source_files(root)
    included.write_text("\n".join(paths) + "\n")
    archive = output / "ledgercore-submission.zip"
    members = []
    with zipfile.ZipFile(
        archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as bundle:
        for name in paths:
            path = root / name
            content = path.read_bytes()
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 14, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if path.suffix == ".sh" else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            bundle.writestr(info, content, compresslevel=9)
            members.append(
                {
                    "path": name,
                    "size_bytes": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            )
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.namelist() == paths
        assert bundle.testzip() is None
        for member in members:
            assert (
                hashlib.sha256(bundle.read(member["path"])).hexdigest()
                == member["sha256"]
            )
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=root, text=True
            )
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        revision, dirty = None, None
    manifest = {
        "archive": archive.name,
        "demo_script_included": "demo.txt" in paths,
        "frontend_included": False,
        "previous_archive_backup": previous_backup,
        "size_bytes": archive.stat().st_size,
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "member_count": len(members),
        "source_commit": revision,
        "working_tree_dirty_at_build": dirty,
        "files": members,
    }
    (output / "ledgercore-submission.manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    (output / "ledgercore-submission.files.sha256").write_text(
        "".join(f"{member['sha256']}  {member['path']}\n" for member in members)
    )
    checksummed = [
        "dist/ledgercore-submission.zip",
        "dist/ledgercore-submission.manifest.json",
        "dist/ledgercore-submission.files.sha256",
        "dist/ledgercore-submission.included-files.txt",
    ]
    (output / "SHA256SUMS").write_text(
        "".join(
            f"{hashlib.sha256((root / name).read_bytes()).hexdigest()}  {name}\n"
            for name in checksummed
        )
    )
    print(
        json.dumps(
            {
                k: manifest[k]
                for k in (
                    "archive",
                    "member_count",
                    "size_bytes",
                    "sha256",
                    "source_commit",
                    "working_tree_dirty_at_build",
                )
            },
            sort_keys=True,
        )
    )
    return manifest


if __name__ == "__main__":
    build()
