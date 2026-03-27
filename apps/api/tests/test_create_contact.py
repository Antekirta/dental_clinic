"""
Tests for contacts.service.create_contact_from_identity().

These are integration tests: they use an in-memory SQLite DB (same pattern
as test_contact_resolution.py) to verify actual DB writes.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Channel, Contact, ContactChannelIdentity
from app.modules.contacts.schemas import CreateContactFromChannelRequest
from app.modules.contacts.service import ChannelNotFoundError, create_contact_from_identity

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def setup_module(module) -> None:
    Channel.__table__.create(bind=engine, checkfirst=True)
    Contact.__table__.create(bind=engine, checkfirst=True)
    ContactChannelIdentity.__table__.create(bind=engine, checkfirst=True)


def teardown_function() -> None:
    with engine.begin() as conn:
        conn.execute(ContactChannelIdentity.__table__.delete())
        conn.execute(Contact.__table__.delete())
        conn.execute(Channel.__table__.delete())


def _seed_channel(session: Session, code: str = "telegram") -> Channel:
    channel = Channel(code=code, display_name=code.title(), notes=None, created_at=datetime.now(UTC))
    session.add(channel)
    session.commit()
    return channel


def _make_request(**kwargs) -> CreateContactFromChannelRequest:
    defaults = dict(
        channel_code="telegram",
        external_id="99887766",
        username="annapetrova",
        display_name="Anna Petrova",
        phone=None,
        email=None,
    )
    defaults.update(kwargs)
    return CreateContactFromChannelRequest(**defaults)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_returns_found_true_with_matched_by_created() -> None:
    session = SessionLocal()
    _seed_channel(session)

    result = create_contact_from_identity(session, _make_request())

    assert result.found is True
    assert result.matched_by == "created"
    session.close()


def test_contact_and_identity_are_populated_in_response() -> None:
    session = SessionLocal()
    _seed_channel(session)

    result = create_contact_from_identity(session, _make_request(
        display_name="Anna Petrova",
        username="annapetrova",
        external_id="99887766",
    ))

    assert result.contact is not None
    assert result.contact.full_name == "Anna Petrova"
    assert result.contact.lifecycle_stage == "lead"
    assert result.identity is not None
    assert result.identity.external_id == "99887766"
    assert result.identity.username == "annapetrova"
    session.close()


def test_contact_is_persisted_to_db() -> None:
    session = SessionLocal()
    _seed_channel(session)

    result = create_contact_from_identity(session, _make_request(display_name="Boris Ivanov"))
    session.commit()
    session.close()

    read_session = SessionLocal()
    contact = read_session.get(Contact, result.contact.id)
    assert contact is not None
    assert contact.full_name == "Boris Ivanov"
    assert contact.lifecycle_stage == "lead"
    read_session.close()


def test_identity_is_persisted_to_db() -> None:
    session = SessionLocal()
    channel = _seed_channel(session)
    channel_id = channel.id  # capture before session closes

    result = create_contact_from_identity(session, _make_request(
        external_id="99887766",
        username="annapetrova",
    ))
    session.commit()
    session.close()

    read_session = SessionLocal()
    identity = read_session.get(ContactChannelIdentity, result.identity.id)
    assert identity is not None
    assert identity.external_id == "99887766"
    assert identity.username == "annapetrova"
    assert identity.channel_id == channel_id
    assert identity.contact_id == result.contact.id
    read_session.close()


def test_source_channel_id_set_on_contact() -> None:
    session = SessionLocal()
    channel = _seed_channel(session)
    channel_id = channel.id  # capture before session closes

    result = create_contact_from_identity(session, _make_request())
    session.commit()
    session.close()

    read_session = SessionLocal()
    contact = read_session.get(Contact, result.contact.id)
    assert contact.source_channel_id == channel_id
    read_session.close()


# ---------------------------------------------------------------------------
# Phone and email propagation
# ---------------------------------------------------------------------------

def test_phone_stored_on_both_contact_and_identity() -> None:
    session = SessionLocal()
    _seed_channel(session)

    result = create_contact_from_identity(session, _make_request(phone="+447700900403"))
    session.commit()
    session.close()

    read_session = SessionLocal()
    contact = read_session.get(Contact, result.contact.id)
    identity = read_session.get(ContactChannelIdentity, result.identity.id)
    assert contact.phone == "+447700900403"
    assert identity.phone == "+447700900403"
    read_session.close()


def test_email_lowercased_and_stored() -> None:
    session = SessionLocal()
    _seed_channel(session)

    result = create_contact_from_identity(session, _make_request(email="Anna@Example.COM"))
    session.commit()
    session.close()

    read_session = SessionLocal()
    contact = read_session.get(Contact, result.contact.id)
    assert contact.email == "anna@example.com"
    read_session.close()


def test_no_phone_or_email_stored_as_none() -> None:
    session = SessionLocal()
    _seed_channel(session)

    result = create_contact_from_identity(session, _make_request(phone=None, email=None))
    session.commit()

    read_session = SessionLocal()
    contact = read_session.get(Contact, result.contact.id)
    assert contact.phone is None
    assert contact.email is None
    session.close()
    read_session.close()


# ---------------------------------------------------------------------------
# Whitespace normalisation
# ---------------------------------------------------------------------------

def test_display_name_whitespace_stripped() -> None:
    session = SessionLocal()
    _seed_channel(session)

    result = create_contact_from_identity(session, _make_request(display_name="  Anna Petrova  "))
    assert result.contact.full_name == "Anna Petrova"
    session.close()


def test_blank_display_name_stored_as_none() -> None:
    session = SessionLocal()
    _seed_channel(session)

    result = create_contact_from_identity(session, _make_request(display_name="   "))
    assert result.contact.full_name is None
    session.close()


def test_blank_username_stored_as_none() -> None:
    session = SessionLocal()
    _seed_channel(session)

    result = create_contact_from_identity(session, _make_request(username="   "))
    assert result.identity.username is None
    session.close()


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

def test_unknown_channel_raises_channel_not_found_error() -> None:
    session = SessionLocal()
    # no channel seeded

    with pytest.raises(ChannelNotFoundError, match="whatsapp"):
        create_contact_from_identity(
            session,
            _make_request(channel_code="whatsapp"),
        )
    session.close()


def test_does_not_commit_on_its_own() -> None:
    """flush() puts rows in the session but rollback() must undo them."""
    session = SessionLocal()
    _seed_channel(session)

    result = create_contact_from_identity(session, _make_request())
    contact_id = result.contact.id

    session.rollback()
    session.close()

    read_session = SessionLocal()
    contact = read_session.get(Contact, contact_id)
    assert contact is None  # was never committed
    read_session.close()
