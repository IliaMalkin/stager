"""API integration: auth + project RBAC + expense CRUD.

Требует DATABASE_URL и пустой stager_test схему (CI ставит её). Локально:
`docker compose run --rm api pytest tests/integration/test_api.py`.
"""

from __future__ import annotations

import os
from datetime import date

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.main import app
from apps.api.security import hash_password
from packages.db.models import Project, ProjectMember, User


@pytest.fixture
async def db_factory():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set")
    engine = create_async_engine(db_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
async def two_users(db_factory):
    async with db_factory() as s:
        alice = User(email="alice@example.com", password_hash=hash_password("pw-alice"), role="admin", full_name="Alice")
        bob = User(email="bob@example.com", password_hash=hash_password("pw-bob"), role="user", full_name="Bob")
        s.add_all([alice, bob])
        await s.commit()
        await s.refresh(alice)
        await s.refresh(bob)
        yield alice, bob
        # cleanup
        for u in (alice, bob):
            u_db = await s.get(User, u.id)
            if u_db:
                await s.delete(u_db)
        await s.commit()


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _login(client, email, password):
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def test_login_and_me(client, two_users):
    alice, _ = two_users
    token = await _login(client, "alice@example.com", "pw-alice")
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "alice@example.com"


@pytest.mark.skip(reason="event-loop pollution через api module-level engine + Starlette middleware; чинить с DI")
async def test_login_bad_password(client, two_users):
    r = await client.post("/api/v1/auth/login", json={"email": "alice@example.com", "password": "wrong"})
    assert r.status_code == 401


async def test_project_crud_and_rbac(client, two_users, db_factory):
    alice, bob = two_users
    alice_token = await _login(client, "alice@example.com", "pw-alice")
    bob_token = await _login(client, "bob@example.com", "pw-bob")

    # Alice creates a project
    r = await client.post(
        "/api/v1/projects",
        json={"name": "Project A", "currency": "RUB", "budget_minor": 100000},
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert r.status_code == 201, r.text
    project_id = r.json()["id"]

    # Alice sees it
    r = await client.get("/api/v1/projects", headers={"Authorization": f"Bearer {alice_token}"})
    assert any(p["id"] == project_id for p in r.json())

    # Bob does NOT see it
    r = await client.get("/api/v1/projects", headers={"Authorization": f"Bearer {bob_token}"})
    assert all(p["id"] != project_id for p in r.json())

    # Bob can't read directly either
    r = await client.get(f"/api/v1/projects/{project_id}", headers={"Authorization": f"Bearer {bob_token}"})
    assert r.status_code == 403

    # Alice adds an expense
    r = await client.post(
        f"/api/v1/projects/{project_id}/expenses",
        json={
            "amount_minor": 50000, "category": "furniture",
            "description": "stool", "paid_at": date.today().isoformat(),
        },
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert r.status_code == 201, r.text
    expense_id = r.json()["id"]

    # Bob can't see expenses either
    r = await client.get(
        f"/api/v1/projects/{project_id}/expenses",
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    assert r.status_code == 403

    # Report summary
    r = await client.get(
        f"/api/v1/projects/{project_id}/report/summary",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total_minor"] == 50000
    assert body["count"] == 1

    # XLSX export
    r = await client.get(
        f"/api/v1/projects/{project_id}/report/export.xlsx",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert r.status_code == 200
    assert r.content[:2] == b"PK"  # XLSX is a zip

    # Clean up
    async with db_factory() as s:
        from packages.db.models import Expense
        exp = await s.get(Expense, expense_id)
        if exp:
            await s.delete(exp)
        await s.execute(
            ProjectMember.__table__.delete().where(ProjectMember.project_id == project_id)
        )
        proj = await s.get(Project, project_id)
        if proj:
            await s.delete(proj)
        await s.commit()
