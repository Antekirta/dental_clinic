from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.dependencies import get_db_session
from app.db.models import Channel, Contact, ContactChannelIdentity
from app.main import app

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    future=True,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def override_get_db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db_session] = override_get_db_session
client = TestClient(app)


def setup_module(module) -> None:
    Channel.__table__.create(bind=engine, checkfirst=True)
    Contact.__table__.create(bind=engine, checkfirst=True)
    ContactChannelIdentity.__table__.create(bind=engine, checkfirst=True)


def teardown_function() -> None:
    with engine.begin() as connection:
        connection.execute(ContactChannelIdentity.__table__.delete())
        connection.execute(Contact.__table__.delete())
        connection.execute(Channel.__table__.delete())


def _seed_contact(
    session: Session,
    *,
    channel_code: str,
    contact_name: str,
    contact_phone: str | None,
    contact_email: str | None,
    lifecycle_stage: str,
    external_id: str,
    identity_phone: str | None = None,
    identity_email: str | None = None,
    username: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(UTC)

    channel = Channel(code=channel_code, display_name=channel_code.title(), notes=None)
    session.add(channel)
    session.flush()

    contact = Contact(
        full_name=contact_name,
        phone=contact_phone,
        email=contact_email,
        source_channel_id=channel.id,
        lifecycle_stage=lifecycle_stage,
        created_at=now,
        updated_at=now,
    )
    session.add(contact)
    session.flush()

    identity = ContactChannelIdentity(
        contact_id=contact.id,
        channel_id=channel.id,
        external_id=external_id,
        username=username,
        phone=identity_phone,
        email=identity_email,
        created_at=now,
        updated_at=now,
    )
    session.add(identity)
    session.commit()

    return {"channel": channel, "contact": contact, "identity": identity}


def test_resolve_contact_by_external_id() -> None:
    session = TestingSessionLocal()
    seeded = _seed_contact(
        session,
        channel_code="telegram",
        contact_name="Ante Petrovic",
        contact_phone=None,
        contact_email=None,
        lifecycle_stage="lead",
        external_id="telegram:741290268",
        username="An_t_e",
    )
    session.close()

    response = client.post(
        "/contacts/resolve",
        json={
            "channel": {"code": "telegram"},
            "contact": {
                "external_contact_id": "telegram:741290268",
                "username": "An_t_e",
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "found": True,
        "matched_by": "external_id",
        "contact": {
            "id": seeded["contact"].id,
            "full_name": "Ante Petrovic",
            "phone": None,
            "email": None,
            "lifecycle_stage": "lead",
        },
        "identity": {
            "id": seeded["identity"].id,
            "channel_id": seeded["channel"].id,
            "external_id": "telegram:741290268",
            "username": "An_t_e",
            "phone": None,
            "email": None,
        },
    }


def test_resolve_contact_by_phone_fallback() -> None:
    session = TestingSessionLocal()
    seeded = _seed_contact(
        session,
        channel_code="whatsapp",
        contact_name="Amelia Stone",
        contact_phone="+447700900403",
        contact_email="amelia@example.com",
        lifecycle_stage="patient",
        external_id="wa-447700900403",
        identity_phone="+447700900403",
        identity_email="amelia@example.com",
    )
    telegram_channel = Channel(code="telegram", display_name="Telegram", notes=None)
    session.add(telegram_channel)
    session.commit()
    session.close()

    response = client.post(
        "/contacts/resolve",
        json={
            "channel": {"code": "telegram"},
            "contact": {
                "external_contact_id": "telegram:new-user",
                "phone": "+447700900403",
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["found"] is True
    assert response.json()["matched_by"] == "phone"
    assert response.json()["contact"]["id"] == seeded["contact"].id


def test_resolve_contact_not_found() -> None:
    session = TestingSessionLocal()
    _seed_contact(
        session,
        channel_code="telegram",
        contact_name="Charlotte Hughes",
        contact_phone=None,
        contact_email=None,
        lifecycle_stage="qualified",
        external_id="telegram:existing-user",
    )
    session.close()

    response = client.post(
        "/contacts/resolve",
        json={
            "channel": {"code": "telegram"},
            "contact": {
                "external_contact_id": "telegram:unknown-user",
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "found": False,
        "matched_by": None,
        "contact": None,
        "identity": None,
    }
