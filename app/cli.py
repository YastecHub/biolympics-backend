"""Command-line entrypoint: `python -m app.cli <command>`.

Commands:
  seed [--demo]          Load tournament structure (add --demo for sample data)
  create-admin           Create an admin user (prompts for password securely)
  generate-vapid         Generate a VAPID keypair for web push
  simulate               Run the live demo simulator (dev only)
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import getpass
import sys

from app.core.config import settings
from app.db.session import get_sessionmaker


async def _seed(with_demo: bool) -> None:
    from app.seeds.seed import seed

    async with get_sessionmaker()() as db:
        summary = await seed(db, with_demo=with_demo)
    print("Seed complete:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print(
        f"\nSuper admin: {settings.initial_admin_email} "
        f"(password from INITIAL_ADMIN_PASSWORD)"
    )


async def _create_admin(email: str, full_name: str, role: str, password: str | None) -> None:
    from sqlalchemy import select

    from app.core.security import hash_password
    from app.models.auth import User, UserRole
    from app.models.enums import RoleName
    from app.seeds.seed import ensure_roles

    if role not in {r.value for r in RoleName}:
        print(f"Invalid role. Choose one of: {', '.join(r.value for r in RoleName)}")
        sys.exit(1)
    if not password:
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Confirm password: "):
            print("Passwords do not match.")
            sys.exit(1)
    if len(password) < 10:
        print("Password must be at least 10 characters.")
        sys.exit(1)

    async with get_sessionmaker()() as db:
        roles = await ensure_roles(db)
        existing = (
            await db.execute(select(User).where(User.email == email.lower()))
        ).scalar_one_or_none()
        if existing:
            print(f"User {email} already exists.")
            sys.exit(1)
        user = User(
            email=email.lower(),
            full_name=full_name,
            hashed_password=hash_password(password),
            is_active=True,
        )
        db.add(user)
        await db.flush()
        db.add(UserRole(user_id=user.id, role_id=roles[role].id))
        await db.commit()
    print(f"Created {role} user: {email}")


def _generate_vapid() -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    def b64url(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    priv = ec.generate_private_key(ec.SECP256R1())
    private_value = priv.private_numbers().private_value
    private_raw = private_value.to_bytes(32, "big")
    public_point = priv.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    print("Add these to your .env (keep the private key secret — backend only):\n")
    print(f"VAPID_PUBLIC_KEY={b64url(public_point)}")
    print(f"VAPID_PRIVATE_KEY={b64url(private_raw)}")
    print("VAPID_SUBJECT=mailto:admin@biolympics.example")
    print(f"\nFrontend (public key only):\nVITE_VAPID_PUBLIC_KEY={b64url(public_point)}")


async def _simulate(interval: float) -> None:
    if settings.is_production:
        print("Refusing to run the demo simulator in production.")
        sys.exit(1)

    import random

    from sqlalchemy import select

    from app.models.enums import FixtureStatus
    from app.models.fixtures import Fixture
    from app.services.events import bus, publish_event
    from app.services.scoring import live_payload

    await bus.connect()
    print(f"Demo simulator running (every {interval}s). Ctrl-C to stop.")
    try:
        while True:
            async with get_sessionmaker()() as db:
                fx = (
                    await db.execute(
                        select(Fixture).where(Fixture.status == FixtureStatus.LIVE).limit(1)
                    )
                ).scalar_one_or_none()
                if fx and fx.live_state:
                    if random.random() < 0.5:
                        fx.live_state.home_score += 1
                    else:
                        fx.live_state.away_score += 1
                    fx.version += 1
                    fx.live_state.version = fx.version
                    await db.commit()
                    await db.refresh(fx)
                    await publish_event(
                        "fixture.score_updated",
                        live_payload(fx),
                        fixture_id=fx.id,
                        sport=fx.sport.slug,
                        version=fx.version,
                    )
                    print(
                        f"  {fx.sport.slug}: {fx.live_state.home_score}-"
                        f"{fx.live_state.away_score} (v{fx.version})"
                    )
                else:
                    print("  no live fixture found; seed demo data first.")
            await asyncio.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        await bus.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p_seed = sub.add_parser("seed", help="Load tournament structure (lean by default)")
    p_seed.add_argument(
        "--demo",
        action="store_true",
        help="Also load sample results, a live match, announcements and sponsors (testing only)",
    )
    p_seed.add_argument("--with-demo", action="store_true", help=argparse.SUPPRESS)

    p_admin = sub.add_parser("create-admin", help="Create an admin user")
    p_admin.add_argument("--email", required=True)
    p_admin.add_argument("--full-name", default="Administrator")
    p_admin.add_argument("--role", default="SUPER_ADMIN")
    p_admin.add_argument("--password", default=None, help="Insecure; prefer the prompt")

    sub.add_parser("generate-vapid", help="Generate a VAPID keypair")

    p_sim = sub.add_parser("simulate", help="Run the demo live-score simulator")
    p_sim.add_argument("--interval", type=float, default=4.0)

    args = parser.parse_args()

    if args.command == "seed":
        asyncio.run(_seed(with_demo=args.demo or args.with_demo))
    elif args.command == "create-admin":
        asyncio.run(_create_admin(args.email, args.full_name, args.role, args.password))
    elif args.command == "generate-vapid":
        _generate_vapid()
    elif args.command == "simulate":
        asyncio.run(_simulate(args.interval))


if __name__ == "__main__":
    main()
