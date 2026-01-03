# Admin Access Setup

This project provides a private admin area protected by Flask-Login. There is no public registration; the admin user is managed through environment variables and a CLI helper.

## Environment variables
Set the following variables before running the app or CLI commands:

- `SECRET_KEY` – Flask secret key.
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` – Database connection settings.
- `ADMIN_EMAIL` – Email for the admin account.
- `ADMIN_PASSWORD` – Password for the admin account (used only when creating/updating the admin user).
- `ADMIN_NAME` – Optional display name for the admin.
- `SESSION_COOKIE_SECURE` – Set to `true` when running behind HTTPS.

## Creating the admin user
Run the Flask CLI command (from the `backend` directory):

```bash
flask --app app:create_app create-admin
```

The command is idempotent: it creates the admin if missing, or updates the password and name if the user already exists.

## Logging in
Start the server and visit `/admin/login` to access the admin login form. Only the configured admin can sign in. Admin-only routes under `/admin` require authentication and admin status; unauthenticated access is redirected to the login page.

## Database migrations
Apply database migrations after pulling changes to keep the schema in sync:

```bash
flask --app app:create_app db upgrade
```

When working through Docker Compose, run the migration commands inside the app container to ensure the database schema is updated:

```bash
docker compose exec -T app flask --app app:create_app db upgrade
docker compose exec -T app flask --app app:create_app db current
docker compose exec -T app flask --app app:create_app db history
```
