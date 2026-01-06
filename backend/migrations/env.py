import logging
from logging.config import fileConfig

from alembic import context
from app import create_app
from app.extensions import db

config = context.config

# Configure Python logging using the config file (alembic.ini).
# This keeps Alembic logging consistent across environments.
fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")

app = create_app()

with app.app_context():
    # -------------------------------------------------------------------------
    # IMPORTANT: Alembic stores "sqlalchemy.url" in a ConfigParser instance.
    # ConfigParser uses %-interpolation by default, so if your DB password
    # contains '%', ConfigParser will crash with:
    #
    #   ValueError: invalid interpolation syntax ...
    #
    # Fix: escape % as %% ONLY for the value that goes into configparser.
    # This does NOT change the actual password; it's just a configparser-safe
    # representation of the URL string.
    # -------------------------------------------------------------------------
    db_url = app.config["SQLALCHEMY_DATABASE_URI"]
    db_url_for_alembic = db_url.replace("%", "%%")

    # Make Alembic aware of our DB URL (safe for configparser).
    config.set_main_option("sqlalchemy.url", db_url_for_alembic)

    # Target metadata for 'autogenerate' support (compare models -> migrations).
    target_metadata = db.metadata

    def run_migrations_offline():
        """Run migrations in 'offline' mode.

        Offline mode does not create an Engine/DBAPI connection.
        It generates SQL scripts based on the URL + metadata.
        """
        # Use the configparser-safe URL here as well to avoid any interpolation issues.
        context.configure(
            url=db_url_for_alembic,
            target_metadata=target_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
        )

        with context.begin_transaction():
            context.run_migrations()

    def run_migrations_online():
        """Run migrations in 'online' mode.

        Online mode uses a real DB connection and applies migrations directly.
        """

        def process_revision_directives(context, revision, directives):
            # If `alembic revision --autogenerate` produced no actual changes,
            # avoid creating an empty migration file.
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
