from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CreateContactFromChannelRequest(BaseModel):
    """
    Input for creating a brand-new contact + channel identity in one step.
    Used by inbound_messages after resolve_contact() returns found=False.
    """

    model_config = ConfigDict(extra="ignore")

    channel_code: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    username: str | None = None
    display_name: str | None = None  # stored as Contact.full_name
    phone: str | None = None
    email: str | None = None


class ResolveChannelPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str = Field(min_length=1)


class ResolveContactPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    external_id: str | None = None
    external_contact_id: str | None = None
    username: str | None = None
    phone: str | None = None
    email: str | None = None
    display_name: str | None = None


class ResolveContactMatchKeysPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    phone: str | None = None
    email: str | None = None


class ResolveContactRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    channel: ResolveChannelPayload
    contact: ResolveContactPayload
    contact_match_keys: ResolveContactMatchKeysPayload | None = None


class ResolvedContactPayload(BaseModel):
    id: int
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    lifecycle_stage: str


class ResolvedIdentityPayload(BaseModel):
    id: int
    channel_id: int
    external_id: str
    username: str | None = None
    phone: str | None = None
    email: str | None = None


class ResolveContactResponse(BaseModel):
    found: bool
    matched_by: Literal["external_id", "phone", "email", "created"] | None = None
    contact: ResolvedContactPayload | None = None
    identity: ResolvedIdentityPayload | None = None
