from alembic import context
from sqlalchemy import create_engine, pool

from ledgercore.db.session import Settings
from ledgercore.models.entities import Base

config = context.config
target_metadata = Base.metadata


def run():
    url = Settings().database_url
    if context.is_offline_mode():
        context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
    else:
        engine = create_engine(
            url, poolclass=pool.NullPool, connect_args={"options": "-c timezone=UTC"}
        )
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )
            with context.begin_transaction():
                context.run_migrations()
        engine.dispose()


run()
