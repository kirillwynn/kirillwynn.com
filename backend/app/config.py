import os


class Config:
    """
    Application configuration (loaded from environment variables).

    FAANG-ish goals:
    - Production: fail-fast for truly required settings (DB + SECRET_KEY).
    - Staging/local: allow boot without DB to keep edge + health endpoints alive.
      (DB-backed features will still fail when used, which is acceptable early on.)
    - Optional subsystems (S3 media) are feature-flagged.
    """

    # ---------------------------------------------------------------
    # Environment
    # ---------------------------------------------------------------
    # APP_ENV: "production" | "staging" | "local"
    APP_ENV = os.getenv("APP_ENV", "production").lower()

    IS_PROD = APP_ENV == "production"

    # ---------------------------------------------------------------
    # Secret key
    # ---------------------------------------------------------------
    # In prod: required.
    # In staging/local: we allow a default dev key to boot the app.
    # (Do NOT use the default key in real prod.)
    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY and IS_PROD:
        raise RuntimeError("SECRET_KEY is required in production")
    if not SECRET_KEY:
        SECRET_KEY = "dev-insecure-secret-key"  # staging/local fallback

    # ---------------------------------------------------------------
    # Database
    # ---------------------------------------------------------------
    db_host = os.getenv("DB_HOST")
    db_name = os.getenv("DB_NAME")
    db_port = os.getenv("DB_PORT")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")

    required_db = {
        "DB_HOST": db_host,
        "DB_PORT": db_port,
        "DB_NAME": db_name,
        "DB_USER": db_user,
        "DB_PASSWORD": db_password,
    }

    missing_db = [k for k, v in required_db.items() if not v]

    if missing_db and IS_PROD:
        # Production must not start without DB.
        raise RuntimeError(f"Missing required ENV vars: {', '.join(missing_db)}")

    # If DB config is incomplete (staging/local), we still boot,
    # but DB-backed features will error if used.
    if not missing_db:
        SQLALCHEMY_DATABASE_URI = (
            f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        )
    else:
        SQLALCHEMY_DATABASE_URI = None  # explicit: DB not configured

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ---------------------------------------------------------------
    # SQLAlchemy engine (connection pool hardening)
    # ---------------------------------------------------------------
    # Some managed Postgres setups close idle SSL connections.
    # These settings keep the app resilient:
    # - pool_pre_ping: checks connection liveness before using it
    # - pool_recycle: periodically recreates connections to avoid stale SSL sockets
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "280")),  # seconds
        "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),   # seconds
    }

    # ---------------------------------------------------------------
    # Session cookies (recommended security defaults)
    # ---------------------------------------------------------------
    SESSION_COOKIE_HTTPONLY = True

    # In prod behind HTTPS, should be true.
    # Keep configurable to allow local HTTP development.
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    SESSION_COOKIE_SAMESITE = "Lax"

    # ---------------------------------------------------------------
    # S3 / Object Storage (optional, for MediaAsset feature)
    # ---------------------------------------------------------------
    S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
    S3_REGION = os.getenv("S3_REGION")
    S3_BUCKET = os.getenv("S3_BUCKET")
    S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID")
    S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY")

    S3_ADDRESSING_STYLE = os.getenv("S3_ADDRESSING_STYLE", "path")
    S3_PRESIGN_EXPIRES_IN = int(os.getenv("S3_PRESIGN_EXPIRES_IN", "900"))

    MEDIA_ENABLED = all(
        [
            S3_ENDPOINT_URL,
            S3_REGION,
            S3_BUCKET,
            S3_ACCESS_KEY_ID,
            S3_SECRET_ACCESS_KEY,
        ]
    )
