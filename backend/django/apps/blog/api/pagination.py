from urllib.parse import urlsplit, urlunsplit

from rest_framework.pagination import PageNumberPagination


class PostPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50

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
