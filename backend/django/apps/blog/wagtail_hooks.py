from django.utils.html import escape
from wagtail import hooks
from wagtail.models import Page
from wagtail.rich_text import LinkHandler

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
