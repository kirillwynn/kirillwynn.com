import logging
from logging.config import fileConfig

from alembic import context
from app import create_app
from app.extensions import db

app = create_app()
app_context = app.app_context()
app_context.push()

config = context.config
fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")

config.set_main_option("sqlalchemy.url", app.config["SQLALCHEMY_DATABASE_URI"])

target_metadata = db.metadata

def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = app.config["SQLALCHEMY_DATABASE_URI"]
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""

    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, "autogenerate", False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info("No changes in schema detected.")

    connectable = db.engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            process_revision_directives=process_revision_directives,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
