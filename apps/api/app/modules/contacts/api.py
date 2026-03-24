from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db_session
from app.modules.contacts.schemas import ResolveContactRequest, ResolveContactResponse
from app.modules.contacts.service import ChannelNotFoundError, resolve_contact

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.post("/resolve", response_model=ResolveContactResponse, summary="Resolve contact")
def resolve_contact_endpoint(
    payload: ResolveContactRequest,
    session: Session = Depends(get_db_session),
) -> ResolveContactResponse:
    try:
        return resolve_contact(session, payload)
    except ChannelNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
