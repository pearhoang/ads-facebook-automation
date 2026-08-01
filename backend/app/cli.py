from __future__ import annotations

import argparse
import getpass
import os

from .config import Settings
from .db import Database
from .services.auth import provision_admin


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Meta Ads Copilot administration")
    subparsers = parser.add_subparsers(dest="command", required=True)
    provision = subparsers.add_parser("provision-admin", help="Create or update an owner account")
    provision.add_argument("--tenant-id", required=True)
    provision.add_argument("--tenant-name", required=True)
    provision.add_argument("--email", required=True)
    provision.add_argument("--display-name", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = Settings.from_env()
    database = Database(settings.database_url)
    if settings.app_env != "production":
        database.create_schema()
    if args.command == "provision-admin":
        password = os.getenv("ADS_ADMIN_PASSWORD") or getpass.getpass("Admin password: ")
        with database.session_factory() as db:
            user = provision_admin(
                db,
                tenant_id=args.tenant_id,
                tenant_name=args.tenant_name,
                email=args.email,
                display_name=args.display_name,
                password=password,
            )
        print(f"Provisioned owner account: {user.email}")


if __name__ == "__main__":
    main()
