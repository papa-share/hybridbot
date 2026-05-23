#!/usr/bin/env python3
"""Gestion des comptes PostgreSQL. Usage : uv run python scripts/manage_user.py <commande>"""

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from chatbot.auth import (
    ROLE_ADMIN,
    ROLE_USER,
    create_account,
    list_accounts,
    reset_password,
    set_account_active,
    set_account_role,
)


def _cmd_create(args: argparse.Namespace) -> None:
    asyncio.run(
        create_account(
            args.identifier,
            args.password,
            role=args.role,
            display_name=args.name,
        )
    )
    print(f"Compte créé : {args.identifier} ({args.role})")


def _cmd_list(_args: argparse.Namespace) -> None:
    rows = asyncio.run(list_accounts())
    if not rows:
        print("Aucun compte.")
        return
    for row in rows:
        status = "actif" if row.get("active") else "inactif"
        name = row.get("display_name") or row["identifier"]
        print(f"{row['identifier']}\t{row.get('role', ROLE_USER)}\t{status}\t{name}")


def _cmd_disable(args: argparse.Namespace) -> None:
    asyncio.run(set_account_active(args.identifier, active=False))
    print(f"Compte désactivé : {args.identifier}")


def _cmd_enable(args: argparse.Namespace) -> None:
    asyncio.run(set_account_active(args.identifier, active=True))
    print(f"Compte activé : {args.identifier}")


def _cmd_reset_password(args: argparse.Namespace) -> None:
    asyncio.run(reset_password(args.identifier, args.password))
    print(f"Mot de passe mis à jour : {args.identifier}")


def _cmd_set_role(args: argparse.Namespace) -> None:
    asyncio.run(set_account_role(args.identifier, args.role))
    print(f"Rôle mis à jour : {args.identifier} → {args.role}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Comptes utilisateurs (PostgreSQL)")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Créer un compte")
    create.add_argument("identifier", help="Identifiant de connexion")
    create.add_argument("--password", required=True, help="Mot de passe")
    create.add_argument("--role", choices=[ROLE_USER, ROLE_ADMIN], default=ROLE_USER)
    create.add_argument("--name", help="Nom affiché (défaut : identifiant)")
    create.set_defaults(func=_cmd_create)

    sub.add_parser("list", help="Lister les comptes").set_defaults(func=_cmd_list)

    disable = sub.add_parser("disable", help="Désactiver un compte")
    disable.add_argument("identifier")
    disable.set_defaults(func=_cmd_disable)

    enable = sub.add_parser("enable", help="Réactiver un compte")
    enable.add_argument("identifier")
    enable.set_defaults(func=_cmd_enable)

    reset = sub.add_parser("reset-password", help="Changer le mot de passe")
    reset.add_argument("identifier")
    reset.add_argument("--password", required=True)
    reset.set_defaults(func=_cmd_reset_password)

    role = sub.add_parser("set-role", help="Changer le rôle")
    role.add_argument("identifier")
    role.add_argument("--role", choices=[ROLE_USER, ROLE_ADMIN], required=True)
    role.set_defaults(func=_cmd_set_role)

    args = parser.parse_args()
    try:
        args.func(args)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
