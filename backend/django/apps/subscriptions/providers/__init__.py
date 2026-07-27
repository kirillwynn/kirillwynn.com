from django.conf import settings
from django.utils.module_loading import import_string


def configured_email_provider():
    provider_class = import_string(settings.EMAIL_PROVIDER_ADAPTER)
    return provider_class()
