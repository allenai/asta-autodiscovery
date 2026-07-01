#!/usr/bin/env python3
"""Administer the password_file auth store.

The PasswordFileProvider re-reads the file on every request, so changes made
here take effect immediately — no web-stack restart required.

The file path comes from --file or the AUTH_PASSWORD_FILE environment variable.

Usage:
    # From the api/ directory (or with PYTHONPATH=api):
    python scripts/auth_admin.py useradd alice --email alice@x.org --name Alice \
        --permission enroll:autodiscovery_admin
    python scripts/auth_admin.py passwd alice
    python scripts/auth_admin.py usermod alice --add-permission enroll:higher_upload_limit
    python scripts/auth_admin.py usermod alice --remove-permission enroll:ai1_datasets
    python scripts/auth_admin.py disable alice
    python scripts/auth_admin.py enable alice
    python scripts/auth_admin.py userdel alice
    python scripts/auth_admin.py list

    # From the project root with uv:
    uv run --env-file .env api/scripts/auth_admin.py list --file path/to/users.json
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

# Add api/ to path so we can import from utils.
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.auth.password_store import (  # noqa: E402
    PasswordStore,
    UserExistsError,
    UserNotFoundError,
)


def _resolve_path(args) -> str:
    path = args.file or os.environ.get("AUTH_PASSWORD_FILE")
    if not path:
        sys.exit("error: provide --file or set AUTH_PASSWORD_FILE")
    return path


def _prompt_password(username: str) -> str:
    pw = getpass.getpass(f"Password for {username}: ")
    if not pw:
        sys.exit("error: empty password")
    confirm = getpass.getpass("Confirm password: ")
    if pw != confirm:
        sys.exit("error: passwords do not match")
    return pw


def cmd_useradd(store: PasswordStore, args) -> None:
    password = args.password or _prompt_password(args.username)
    try:
        store.add_user(
            args.username,
            password,
            email=args.email,
            name=args.name,
            permissions=args.permission,
        )
    except UserExistsError as e:
        sys.exit(f"error: {e}")
    print(f"Created user '{args.username}'")


def cmd_passwd(store: PasswordStore, args) -> None:
    password = args.password or _prompt_password(args.username)
    try:
        store.set_password(args.username, password)
    except UserNotFoundError as e:
        sys.exit(f"error: {e}")
    print(f"Updated password for '{args.username}'")


def cmd_usermod(store: PasswordStore, args) -> None:
    try:
        if args.email is not None or args.name is not None:
            store.update_profile(args.username, email=args.email, name=args.name)
        if args.add_permission:
            store.add_permissions(args.username, args.add_permission)
        if args.remove_permission:
            store.remove_permissions(args.username, args.remove_permission)
    except UserNotFoundError as e:
        sys.exit(f"error: {e}")
    print(f"Updated user '{args.username}'")


def cmd_disable(store: PasswordStore, args) -> None:
    try:
        store.set_disabled(args.username, True)
    except UserNotFoundError as e:
        sys.exit(f"error: {e}")
    print(f"Disabled user '{args.username}'")


def cmd_enable(store: PasswordStore, args) -> None:
    try:
        store.set_disabled(args.username, False)
    except UserNotFoundError as e:
        sys.exit(f"error: {e}")
    print(f"Enabled user '{args.username}'")


def cmd_userdel(store: PasswordStore, args) -> None:
    try:
        store.delete_user(args.username)
    except UserNotFoundError as e:
        sys.exit(f"error: {e}")
    print(f"Deleted user '{args.username}'")


def cmd_list(store: PasswordStore, args) -> None:
    users = store.load().get("users", {})
    if not users:
        print("(no users)")
        return
    for username in sorted(users):
        rec = users[username]
        status = "disabled" if rec.get("disabled") else "active"
        perms = ",".join(rec.get("permissions", [])) or "-"
        print(f"{username}\t{status}\t{rec.get('email') or '-'}\t{perms}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Administer the password_file auth store.")
    parser.add_argument("--file", help="Path to the store (default: $AUTH_PASSWORD_FILE)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("useradd", help="Create a user")
    p.add_argument("username")
    p.add_argument("--email")
    p.add_argument("--name")
    p.add_argument("--permission", action="append", default=[], help="(repeatable)")
    p.add_argument("--password", help="Non-interactive password (prompts if omitted)")
    p.set_defaults(func=cmd_useradd)

    p = sub.add_parser("passwd", help="Change a user's password")
    p.add_argument("username")
    p.add_argument("--password", help="Non-interactive password (prompts if omitted)")
    p.set_defaults(func=cmd_passwd)

    p = sub.add_parser("usermod", help="Modify a user's profile/permissions")
    p.add_argument("username")
    p.add_argument("--email")
    p.add_argument("--name")
    p.add_argument("--add-permission", action="append", default=[], dest="add_permission")
    p.add_argument("--remove-permission", action="append", default=[], dest="remove_permission")
    p.set_defaults(func=cmd_usermod)

    p = sub.add_parser("disable", help="Disable a user")
    p.add_argument("username")
    p.set_defaults(func=cmd_disable)

    p = sub.add_parser("enable", help="Enable a user")
    p.add_argument("username")
    p.set_defaults(func=cmd_enable)

    p = sub.add_parser("userdel", help="Delete a user")
    p.add_argument("username")
    p.set_defaults(func=cmd_userdel)

    p = sub.add_parser("list", help="List users")
    p.set_defaults(func=cmd_list)

    return parser


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    store = PasswordStore(_resolve_path(args))
    args.func(store, args)


if __name__ == "__main__":
    main()
