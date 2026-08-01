from wagtail.users.apps import WagtailUsersAppConfig


class Stage17WagtailUsersAppConfig(WagtailUsersAppConfig):
    user_viewset = "apps.users.wagtail_views.Stage17WagtailUserViewSet"
