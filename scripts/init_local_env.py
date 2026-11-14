"""Create a private local Compose configuration once; never overwrite existing values."""

import argparse
import os
import secrets
from pathlib import Path


def create_env(path: Path) -> bool:
    password = secrets.token_hex(24)
    content = (
        "# Local development only; keep this file out of Git.\n"
        "POSTGRES_USER=ledgercore\n"
        f"POSTGRES_PASSWORD={password}\n"
        "POSTGRES_DB=ledgercore\n"
        f"DATABASE_URL=postgresql+psycopg://ledgercore:{password}@127.0.0.1:5432/ledgercore\n"
        "DEMO_AUTH_ENABLED=true\n"
    )
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w") as stream:
        stream.write(content)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".env"))
    args = parser.parse_args()
    print(
        "Created private local configuration"
        if create_env(args.output)
        else "Existing configuration preserved"
    )


if __name__ == "__main__":
    main()
