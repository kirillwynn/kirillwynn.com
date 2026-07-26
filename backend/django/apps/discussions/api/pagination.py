from urllib.parse import urlsplit, urlunsplit

from rest_framework.pagination import CursorPagination


class RelativeCursorPagination(CursorPagination):
    page_size = 20

    @staticmethod
    def _relative(link):
        if link is None:
            return None
        parsed = urlsplit(link)
        return urlunsplit(("", "", parsed.path, parsed.query, ""))

    def get_next_link(self):
        return self._relative(super().get_next_link())

    def get_previous_link(self):
        return self._relative(super().get_previous_link())


class TopLevelCommentPagination(RelativeCursorPagination):
    ordering = ("-created_at", "-id")


class ThreadReplyPagination(RelativeCursorPagination):
    ordering = ("created_at", "id")
