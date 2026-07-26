from wagtail.contrib.settings.registry import register_setting

from apps.discussions.models import ReactionSettings

register_setting(ReactionSettings, icon="pick")
