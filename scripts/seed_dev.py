"""Заполняет dev-БД тестовыми данными. Не запускать в проде.

Usage: docker compose run --rm api python scripts/seed_dev.py
"""

from __future__ import annotations

import asyncio
import os
from datetime import date, timedelta

from sqlalchemy import select

from apps.api.security import hash_password
from packages.db.base import async_session_factory
from packages.db.models import (
    ActiveContext, Expense, Project, ProjectMember, User,
)


async def main() -> None:
    if os.getenv("APP_ENV") not in (None, "dev", "test"):
        print("refusing to seed in non-dev env")
        return

    async with async_session_factory() as s:
        admin = await s.scalar(select(User).where(User.email == "dev@stager.local"))
        if not admin:
            admin = User(
                email="dev@stager.local",
                password_hash=hash_password("dev"),
                role="admin",
                full_name="Dev Admin",
                telegram_id=999_999,
            )
            s.add(admin)
            await s.flush()

        project = Project(owner_user_id=admin.id, name="ЖК Парнас — кв. 84", currency="RUB", budget_minor=15000000)
        s.add(project)
        await s.flush()
        s.add(ProjectMember(user_id=admin.id, project_id=project.id, role="owner"))
        s.add(ActiveContext(user_id=admin.id, current_project_id=project.id))

        sample = [
            ("furniture", 485050, "диван ИКЕА Кивик"),
            ("furniture", 120000, "торшер"),
            ("decor", 45000, "вазы ×3"),
            ("textile", 78000, "шторы льняные"),
            ("delivery", 35000, "грузовая газель"),
            ("labor", 600000, "бригада 2 дня"),
            ("supplies", 12000, "монтажный скотч"),
        ]
        today = date.today()
        for i, (cat, amount, desc) in enumerate(sample):
            s.add(Expense(
                project_id=project.id,
                amount_minor=amount,
                currency="RUB",
                category=cat,
                description=desc,
                paid_at=today - timedelta(days=i),
                created_by_user_id=admin.id,
                source="admin_web",
            ))
        await s.commit()
        print(f"seeded: project {project.id}, admin {admin.email}/dev")


if __name__ == "__main__":
    asyncio.run(main())
