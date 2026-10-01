"""FastAPI dependencies shared by every route."""

from typing import Annotated

from fastapi import Depends, Path

from app.core.config import Settings, get_settings
from app.models.store import Store, get_store


def settings_dep() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(settings_dep)]


def store_dep(settings: SettingsDep) -> Store:
    return get_store(settings)


StoreDep = Annotated[Store, Depends(store_dep)]


def valid_session(
    session_id: Annotated[str, Path(min_length=4, max_length=64)],
    store: StoreDep,
) -> str:
    """Reject unknown or expired sessions before any work happens."""
    store.require_session(session_id)
    return session_id


SessionDep = Annotated[str, Depends(valid_session)]
