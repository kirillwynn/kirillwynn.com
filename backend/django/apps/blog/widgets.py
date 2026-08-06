from wagtail.admin.rich_text import DraftailRichTextArea


class AccessibleDraftailRichTextArea(DraftailRichTextArea):
    """Draftail with a stable accessible name and its native storage converter."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.options["ariaLabel"] = "Rich text editor"
