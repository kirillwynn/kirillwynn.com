from apps.blog.models import BlogIndexPage, BlogPostPage


def frontend_page_path(page):
    specific_page = page.specific
    if isinstance(specific_page, BlogPostPage):
        return f"/posts/{specific_page.slug}"
    if isinstance(specific_page, BlogIndexPage) or specific_page.is_root():
        return "/"
    return None
