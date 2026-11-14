"""DEVELOPMENT ONLY: a database subject header is not production authentication."""

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ledgercore.accounting.posting import audit
from ledgercore.db.session import Settings, get_session
from ledgercore.models.entities import User


@dataclass(frozen=True)
class Actor:
    id: UUID
    role: str


def authorize(*roles):
    def dependency(
        request: Request,
        session: Annotated[Session, Depends(get_session)],
        subject: Annotated[
            str | None, Header(alias="X-Demo-User", max_length=200)
        ] = None,
    ) -> Actor:
        if not Settings().demo_auth_enabled:
            raise HTTPException(
                503,
                "Demo authentication is disabled; this service is for local development only",
            )
        actor = None
        # Close the identity read transaction before the route's financial transaction.
        with session.begin():
            user = (
                session.scalar(select(User).where(User.external_subject == subject))
                if subject
                else None
            )
            if user is not None and user.active and user.role in roles:
                actor = Actor(user.id, user.role)
            else:
                audit(
                    session,
                    user.id if user else None,
                    request.state.correlation_id,
                    "authorization.denied",
                    "http_request",
                    None,
                    method=request.method,
                    path=request.url.path,
                    reason="missing_or_inactive_identity"
                    if user is None or not user.active
                    else "role_not_permitted",
                )
        if actor is None:
            raise HTTPException(
                403, "Demo user is missing, inactive, unknown, or not permitted"
            )
        return actor

    return dependency


Reader = Annotated[Actor, Depends(authorize("loan_officer", "manager", "auditor"))]
Officer = Annotated[Actor, Depends(authorize("loan_officer", "manager"))]
Manager = Annotated[Actor, Depends(authorize("manager"))]
Reviewer = Annotated[Actor, Depends(authorize("manager", "auditor"))]
