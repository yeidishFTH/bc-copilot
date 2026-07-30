from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AccountRole,
    AccountType,
    Branch,
    UserAccount,
)
from app.db.session import (
    AsyncSessionFactory,
    dispose_engine,
)
from app.services.auth import PasswordService


INITIAL_PASSWORD = "12345678"


@dataclass(frozen=True, slots=True)
class BranchSeed:
    code: str
    name: str
    email: str
    address: str
    phone: str
    weekday_hours: str
    friday_hours: str
    is_accessible: bool


BRANCHES = (
    BranchSeed(
        code="tlv",
        name="תל אביב",
        email="tlv@bitcoinchange.co.il",
        address="קינג ג׳ורג׳ 50",
        phone="03-9181167",
        weekday_hours="א׳-ה׳ 10:00-20:00",
        friday_hours="ו׳ 09:00-14:00",
        is_accessible=False,
    ),
    BranchSeed(
        code="jerusalem",
        name="ירושלים",
        email="jerusalem@bitcoinchange.co.il",
        address="רחוב יפו 151",
        phone="02-5342313",
        weekday_hours="א׳-ה׳ 10:00-19:00",
        friday_hours="ו׳ 09:00-14:00",
        is_accessible=True,
    ),
    BranchSeed(
        code="netanya",
        name="נתניה",
        email="natanya@bitcoinchange.co.il",
        address="שער העמק 3",
        phone="09-7934808",
        weekday_hours="א׳-ה׳ 10:00-19:00",
        friday_hours="ו׳ 09:00-14:00",
        is_accessible=True,
    ),
    BranchSeed(
        code="beer-sheva",
        name="באר שבע",
        email="beersheva@bitcoinchange.co.il",
        address="שדרות יצחק רגר 53",
        phone="08-8506955",
        weekday_hours="א׳-ה׳ 10:00-20:00",
        friday_hours="ו׳ 09:00-15:00",
        is_accessible=True,
    ),
    BranchSeed(
        code="haifa",
        name="חיפה",
        email="haifa@bitcoinchange.co.il",
        address="חורב 18",
        phone="04-6951035",
        weekday_hours="א׳-ה׳ 10:00-20:00",
        friday_hours="ו׳ 09:00-14:00",
        is_accessible=True,
    ),
    BranchSeed(
        code="ramat-gan",
        name="רמת גן",
        email="ramatgan@bitcoinchange.co.il",
        address="תובל 36",
        phone="03-5362643",
        weekday_hours="א׳-ה׳ 10:00-19:00",
        friday_hours="ו׳ 09:00-13:00",
        is_accessible=True,
    ),
    BranchSeed(
        code="rishon-lezion",
        name="ראשון לציון",
        email="rishon@bitcoinchange.co.il",
        address="רוטשילד 1",
        phone="03-5334963",
        weekday_hours="א׳-ה׳ 10:00-19:00",
        friday_hours="ו׳ 09:00-14:00",
        is_accessible=False,
    ),
    BranchSeed(
        code="afula",
        name="עפולה",
        email="afula@bitcoinchange.co.il",
        address="מנחם בגין 72",
        phone="04-8451639",
        weekday_hours="א׳-ה׳ 10:00-19:00",
        friday_hours="ו׳ 09:00-14:00",
        is_accessible=True,
    ),
    BranchSeed(
        code="ein-shemer",
        name="עין שמר",
        email="einshemer@bitcoinchange.co.il",
        address="מתחם אלון עין שמר",
        phone="04-6990995",
        weekday_hours="א׳-ה׳ 10:00-21:00",
        friday_hours="ו׳ 09:00-15:00",
        is_accessible=True,
    ),
    BranchSeed(
        code="eilat",
        name="אילת",
        email="eilat@bitcoinchange.co.il",
        address="שדרות התמרים 4",
        phone="08-9707178",
        weekday_hours="א׳-ה׳ 10:00-18:00",
        friday_hours="ו׳ 10:00-13:00",
        is_accessible=False,
    ),
    BranchSeed(
        code="karmiel",
        name="כרמיאל",
        email="karmiel@bitcoinchange.co.il",
        address="מתחם דבאח מול",
        phone="04-9533493",
        weekday_hours="א׳-ה׳ 10:00-20:00",
        friday_hours="ו׳ 10:00-15:00",
        is_accessible=False,
    ),
)


INDIVIDUAL_ACCOUNTS = (
    (
        "ohad@bitcoinchange.co.il",
        "אוהד",
        AccountRole.management,
    ),
    (
        "miki@bitcoinchange.co.il",
        "מיקי",
        AccountRole.management,
    ),
    (
        "lihi@bitcoinchange.co.il",
        "ליהי",
        AccountRole.management,
    ),
    (
        "idan@bitcoinchange.co.il",
        "עידן",
        AccountRole.administrator,
    ),
    (
        "avi@bitcoinchange.co.il",
        "אבי",
        AccountRole.management,
    ),
    (
        "oren@bitcoinchange.co.il",
        "אורן",
        AccountRole.management,
    ),
)


async def seed_accounts(
    session: AsyncSession,
    *,
    initial_password: str = INITIAL_PASSWORD,
) -> tuple[int, int]:
    password_service = PasswordService()

    created_branches = 0
    created_accounts = 0

    branches_by_code: dict[str, Branch] = {}

    for item in BRANCHES:
        branch = (
            await session.execute(
                select(Branch).where(
                    Branch.code == item.code
                )
            )
        ).scalar_one_or_none()

        if branch is None:
            branch = Branch(
                code=item.code,
                name=item.name,
                email=item.email.lower(),
                address=item.address,
                phone=item.phone,
                weekday_hours=item.weekday_hours,
                friday_hours=item.friday_hours,
                is_accessible=item.is_accessible,
                is_active=True,
            )
            session.add(branch)
            await session.flush()
            created_branches += 1
        else:
            branch.name = item.name
            branch.email = item.email.lower()
            branch.address = item.address
            branch.phone = item.phone
            branch.weekday_hours = item.weekday_hours
            branch.friday_hours = item.friday_hours
            branch.is_accessible = item.is_accessible

        branches_by_code[item.code] = branch

        email = item.email.lower()

        account = (
            await session.execute(
                select(UserAccount).where(
                    UserAccount.email == email
                )
            )
        ).scalar_one_or_none()

        if account is None:
            session.add(
                UserAccount(
                    email=email,
                    display_name=f"סניף {item.name}",
                    account_type=AccountType.branch,
                    role=AccountRole.branch_user,
                    branch_id=branch.id,
                    password_hash=(
                        password_service.hash_password(
                            initial_password
                        )
                    ),
                    must_change_password=True,
                    is_active=True,
                )
            )
            created_accounts += 1

    for email, display_name, role in (
        INDIVIDUAL_ACCOUNTS
    ):
        normalized_email = email.lower()

        account = (
            await session.execute(
                select(UserAccount).where(
                    UserAccount.email
                    == normalized_email
                )
            )
        ).scalar_one_or_none()

        if account is None:
            session.add(
                UserAccount(
                    email=normalized_email,
                    display_name=display_name,
                    account_type=(
                        AccountType.individual
                    ),
                    role=role,
                    branch_id=None,
                    password_hash=(
                        password_service.hash_password(
                            initial_password
                        )
                    ),
                    must_change_password=True,
                    is_active=True,
                )
            )
            created_accounts += 1

    await session.commit()

    return created_branches, created_accounts


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Seed BC Workspace branches and "
            "initial accounts."
        )
    )
    parser.add_argument(
        "--initial-password",
        default=INITIAL_PASSWORD,
        help=(
            "Initial password for newly created "
            "accounts only."
        ),
    )

    return parser


async def async_main() -> int:
    args = build_argument_parser().parse_args()

    try:
        async with AsyncSessionFactory() as session:
            branches, accounts = await seed_accounts(
                session,
                initial_password=(
                    args.initial_password
                ),
            )

        print(f"Branches created: {branches}")
        print(f"Accounts created: {accounts}")
        print(
            "Existing account passwords were not reset."
        )

        return 0
    finally:
        await dispose_engine()


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
