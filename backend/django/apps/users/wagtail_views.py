from functools import cached_property

from django.utils.translation import gettext_lazy
from wagtail.admin.ui.tables import BooleanColumn, BulkActionsCheckboxColumn, Column, DateColumn
from wagtail.users.views.users import EditView as WagtailEditView
from wagtail.users.views.users import HistoryView as WagtailHistoryView
from wagtail.users.views.users import IndexView as WagtailIndexView
from wagtail.users.views.users import UserColumn
from wagtail.users.views.users import UserViewSet as WagtailUserViewSet

from apps.users.services import public_display_name
from apps.users.wagtail_forms import (
    Stage17WagtailUserCreationForm,
    Stage17WagtailUserEditForm,
)


class Stage17WagtailUserIndexView(WagtailIndexView):
    @cached_property
    def columns(self):
        user_column = self._get_title_column_class(UserColumn)
        return [
            BulkActionsCheckboxColumn("bulk_actions", obj_type="user"),
            user_column(
                "nickname",
                accessor=public_display_name,
                label=gettext_lazy("Public nickname"),
                sort_key="nickname",
                get_url=self.get_edit_url,
                classname="name",
            ),
            Column(
                "email",
                label=gettext_lazy("Email"),
                sort_key="email",
                width="25%",
            ),
            Column(
                "is_superuser",
                accessor=lambda user: gettext_lazy("Admin") if user.is_superuser else None,
                label=gettext_lazy("Access level"),
                sort_key="is_superuser",
                classname="level",
                width="10%",
            ),
            BooleanColumn(
                "is_active",
                label=gettext_lazy("Active"),
                sort_key="is_active",
                classname="status",
                width="10%",
            ),
            DateColumn(
                "last_login",
                label=gettext_lazy("Last login"),
                sort_key="last_login",
                classname="last-login",
                width="15%",
            ),
        ]

    @cached_property
    def search_fields(self):
        return self.model_fields & {"nickname", "email"}


class Stage17WagtailUserEditView(WagtailEditView):
    def get_page_subtitle(self):
        return public_display_name(self.object)


class Stage17WagtailUserHistoryView(WagtailHistoryView):
    def get_page_subtitle(self):
        return public_display_name(self.object)


class Stage17WagtailUserViewSet(WagtailUserViewSet):
    ordering = "nickname"
    index_view_class = Stage17WagtailUserIndexView
    edit_view_class = Stage17WagtailUserEditView
    history_view_class = Stage17WagtailUserHistoryView

    def get_form_class(self, for_update=False):
        if for_update:
            return Stage17WagtailUserEditForm
        return Stage17WagtailUserCreationForm
