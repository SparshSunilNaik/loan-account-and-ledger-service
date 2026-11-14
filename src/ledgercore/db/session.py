from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class Settings(BaseSettings):
    database_url: str
    demo_auth_enabled: bool = False
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def session_factory():
    return sessionmaker(
        create_engine(
            Settings().database_url,
            pool_pre_ping=True,
            isolation_level="READ COMMITTED",
            connect_args={"connect_timeout": 5, "options": "-c timezone=UTC"},
            pool_size=25,
            max_overflow=5,
        ),
        expire_on_commit=False,
    )


def get_session():
    with session_factory()() as session:
        yield session
