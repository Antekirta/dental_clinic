from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Channel, ContactChannelIdentity
from app.modules.contacts.schemas import (
    ResolveContactRequest,
    ResolveContactResponse,
    ResolvedContactPayload,
    ResolvedIdentityPayload,
)


class ChannelNotFoundError(Exception):
    """Raised when the requested channel code does not exist."""


def _normalize_optional_string(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip()
    return normalized or None


def _normalize_email(value: str | None) -> str | None:
    normalized = _normalize_optional_string(value)
    return normalized.lower() if normalized is not None else None


def _build_resolved_response(
    identity: ContactChannelIdentity,
    matched_by: str,
) -> ResolveContactResponse:
    contact = identity.contact

    return ResolveContactResponse(
        found=True,
        matched_by=matched_by,  # type: ignore[arg-type]
        contact=ResolvedContactPayload(
            id=contact.id,
            full_name=contact.full_name,
            phone=contact.phone,
            email=contact.email,
            lifecycle_stage=contact.lifecycle_stage,
        ),
        identity=ResolvedIdentityPayload(
            id=identity.id,
            channel_id=identity.channel_id,
            external_id=identity.external_id,
            username=identity.username,
            phone=identity.phone,
            email=identity.email,
        ),
    )


def _find_identity_by_external_id(
    session: Session,
    channel_id: int,
    external_id: str,
) -> ContactChannelIdentity | None:
    stmt = (
        select(ContactChannelIdentity)
        .options(selectinload(ContactChannelIdentity.contact))
        .where(
            ContactChannelIdentity.channel_id == channel_id,
            ContactChannelIdentity.external_id == external_id,
        )
        .order_by(ContactChannelIdentity.id)
        .limit(1)
    )
    return session.scalar(stmt)


def _find_identity_by_phone(
    session: Session,
    phone: str,
) -> ContactChannelIdentity | None:
    stmt = (
        select(ContactChannelIdentity)
        .options(selectinload(ContactChannelIdentity.contact))
        .where(ContactChannelIdentity.phone == phone)
        .order_by(ContactChannelIdentity.id)
        .limit(1)
    )
    return session.scalar(stmt)


def _find_identity_by_email(
    session: Session,
    email: str,
) -> ContactChannelIdentity | None:
    stmt = (
        select(ContactChannelIdentity)
        .options(selectinload(ContactChannelIdentity.contact))
        .where(func.lower(ContactChannelIdentity.email) == email)
        .order_by(ContactChannelIdentity.id)
        .limit(1)
    )
    return session.scalar(stmt)


def resolve_contact(
    session: Session,
    payload: ResolveContactRequest,
) -> ResolveContactResponse:
    channel_code = _normalize_optional_string(payload.channel.code)
    channel = session.scalar(select(Channel).where(Channel.code == channel_code))
    if channel is None:
        raise ChannelNotFoundError(f"Channel '{payload.channel.code}' not found.")

    external_id = _normalize_optional_string(
        payload.contact.external_id or payload.contact.external_contact_id
    )
    phone = _normalize_optional_string(
        payload.contact.phone
        or (
            payload.contact_match_keys.phone
            if payload.contact_match_keys is not None
            else None
        )
    )
    email = _normalize_email(
        payload.contact.email
        or (
            payload.contact_match_keys.email
            if payload.contact_match_keys is not None
            else None
        )
    )

    if external_id is not None:
        identity = _find_identity_by_external_id(session, channel.id, external_id)
        if identity is not None:
            return _build_resolved_response(identity, "external_id")

    if phone is not None:
        identity = _find_identity_by_phone(session, phone)
        if identity is not None:
            return _build_resolved_response(identity, "phone")

    if email is not None:
        identity = _find_identity_by_email(session, email)
        if identity is not None:
            return _build_resolved_response(identity, "email")

    return ResolveContactResponse(found=False)
