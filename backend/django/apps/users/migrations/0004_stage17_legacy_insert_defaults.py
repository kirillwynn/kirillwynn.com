from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("users", "0003_stage17_identity_backfill")]

    operations = [
        # ``default=`` is normally temporary during AddField. Persist these
        # database defaults before activation so the Stage 16 model (which
        # does not include the columns in INSERT statements) remains capable
        # of creating an OAuth user throughout an application rollback.
        migrations.AlterField(
            model_name="user",
            name="auth_state_version",
            field=models.PositiveIntegerField(default=1, db_default=1, editable=False),
        ),
        migrations.AlterField(
            model_name="user",
            name="nickname_confirmed",
            field=models.BooleanField(default=False, db_default=False),
        ),
    ]
