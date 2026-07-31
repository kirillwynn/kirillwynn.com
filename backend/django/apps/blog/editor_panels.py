from wagtail.admin.panels import FieldPanel


class ReadOnlyPropertyPanel(FieldPanel):
    """Render a model property through Wagtail's accessible read-only field UI."""

    def format_value_for_display(self, value):
        return "" if value is None else str(value)
