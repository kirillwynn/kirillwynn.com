from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.templatetags.static import static
from django.urls import path, reverse
from django.utils.html import escape, format_html
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.admin.ui.components import Component
from wagtail.models import Page
from wagtail.rich_text import LinkHandler

from apps.blog.editorial import NewPostTargetStatus, resolve_new_post_target
from apps.blog.models import BlogPostPage
from apps.blog.services.content_routes import frontend_page_path


class FrontendPageLinkHandler(LinkHandler):
    identifier = "page"

    @classmethod
    def expand_db_attributes(cls, attrs):
        try:
            page = Page.objects.get(pk=attrs["id"])
        except (KeyError, Page.DoesNotExist):
            return "<a>"

        href = frontend_page_path(page)
        return f'<a href="{escape(href)}">' if href else "<a>"


@hooks.register("register_rich_text_features", order=100)
def register_frontend_page_link_handler(features):
    features.register_link_type(FrontendPageLinkHandler)


def new_post_add_url(parent):
    return reverse(
        "wagtailadmin_pages:add",
        args=(
            BlogPostPage._meta.app_label,
            BlogPostPage._meta.model_name,
            parent.pk,
        ),
    )


def new_post(request):
    target = resolve_new_post_target(request.user)
    if target.status == NewPostTargetStatus.FORBIDDEN:
        raise PermissionDenied(target.message)
    if not target.available:
        messages.error(request, target.message)
        return redirect("wagtailadmin_home")
    return redirect(new_post_add_url(target.parent))


@hooks.register("register_admin_urls")
def register_editorial_admin_urls():
    return [path("new-post/", new_post, name="blog_new_post")]


class NewPostMenuItem(MenuItem):
    def is_shown(self, request):
        return resolve_new_post_target(request.user).available


@hooks.register("register_admin_menu_item")
def register_new_post_menu_item():
    return NewPostMenuItem(
        "New post",
        reverse("blog_new_post"),
        name="new-post",
        classname="editorial-new-post-menu",
        icon_name="plus",
        order=50,
    )


class EditorialDashboardPanel(Component):
    name = "editorial_start"
    template_name = "blog/admin/editorial_dashboard.html"
    order = 50

    def get_context_data(self, parent_context):
        context = super().get_context_data(parent_context)
        target = resolve_new_post_target(parent_context["request"].user)
        context.update(
            {
                "new_post_url": reverse("blog_new_post") if target.available else "",
                "new_post_message": target.message,
            }
        )
        return context


@hooks.register("construct_homepage_panels")
def add_editorial_dashboard_panel(request, panels):
    panels.append(EditorialDashboardPanel())


@hooks.register("insert_global_admin_css")
def insert_editorial_admin_css():
    return format_html(
        '<link rel="stylesheet" href="{}">',
        static("blog/css/editorial-admin.css"),
    )


@hooks.register("insert_editor_js")
def insert_editorial_editor_js():
    return format_html(
        '<script src="{}" defer></script>',
        static("blog/js/editorial-admin.js"),
    )
