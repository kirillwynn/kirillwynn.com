import os


class Config:
    """
    Application configuration (loaded from environment variables).

    Design goals:
    - Fail-fast for truly required settings (DB + SECRET_KEY)
    - Keep optional subsystems (S3 media) feature-flagged, so the app can boot
      even if media isn't configured yet.
    - Centralize all env parsing here so the rest of the code reads `app.config[...]`.
    """

    # -----------------------------------------------------------------
    # Database (required)
    # -----------------------------------------------------------------
    # We parse these early and enforce presence immediately ("fail-fast").
    db_host = os.getenv("DB_HOST")
    db_name = os.getenv("DB_NAME")
    db_port = os.getenv("DB_PORT")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")

    required = {
        "DB_HOST": db_host,
        "DB_PORT": db_port,
        "DB_NAME": db_name,
        "DB_USER": db_user,
        "DB_PASSWORD": db_password,
    }

    missing = [k for k, v in required.items() if not v]
    if missing:
        # If DB config is missing, the app should not start.
        raise RuntimeError(f"Missing required ENV vars: {', '.join(missing)}")

    # Secret key is required for session signing / CSRF / security primitives.
    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY is required")

    # SQLAlchemy connection string used by Flask-SQLAlchemy.
    SQLALCHEMY_DATABASE_URI = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # -----------------------------------------------------------------
    # Session cookies (recommended security defaults)
    # -----------------------------------------------------------------
    SESSION_COOKIE_HTTPONLY = True

    # In production behind HTTPS, this should be true.
    # We keep it configurable to allow local HTTP development.
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"

    # Lax is a good default for typical websites: helps mitigate CSRF while
    # still allowing normal top-level navigation.
    SESSION_COOKIE_SAMESITE = "Lax"

    # -----------------------------------------------------------------
    # S3 / Object Storage (optional, for MediaAsset feature)
    # -----------------------------------------------------------------
    # We store the actual bytes in S3-compatible storage, and keep only metadata in Postgres.
    #
    # IMPORTANT:
    # - These settings are optional for the app to boot.
    # - Media endpoints will return 503 if MEDIA_ENABLED=False.
    #
    # Example values for your provider:
    #   S3_ENDPOINT_URL=https://s3.twcstorage.ru
    #   S3_REGION=ru-1
    #   S3_BUCKET=<bucket name>
    #
    S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
    S3_REGION = os.getenv("S3_REGION")
    S3_BUCKET = os.getenv("S3_BUCKET")

    # Credentials (must be kept in GitHub Secrets / server env, never in code)
    S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID")
    S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY")

    # Addressing style:
    # - "path"    -> https://endpoint/bucket/key
    # - "virtual" -> https://bucket.endpoint/key
    # Many S3-compatible providers work best with "path".
    S3_ADDRESSING_STYLE = os.getenv("S3_ADDRESSING_STYLE", "path")

    # Presigned URL TTL (seconds). 15 minutes is a common default.
    S3_PRESIGN_EXPIRES_IN = int(os.getenv("S3_PRESIGN_EXPIRES_IN", "900"))

    # Feature flag: media is enabled only when ALL required S3 settings are present.
    MEDIA_ENABLED = all(
        [
            S3_ENDPOINT_URL,
            S3_REGION,
            S3_BUCKET,
            S3_ACCESS_KEY_ID,
            S3_SECRET_ACCESS_KEY,
        ]
    )
