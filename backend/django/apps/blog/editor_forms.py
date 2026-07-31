from wagtail.admin.forms import WagtailAdminPageForm


class BlogPostPageForm(WagtailAdminPageForm):
    """Keep revision intent editable only until the durable decision is made."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields.get("notify_subscribers_on_first_publication")
        if field is None or not self.instance.pk:
            return

        from apps.subscriptions.models import PostPublicationEmailDecision

        try:
            decision = self.instance.publication_email_decision
        except PostPublicationEmailDecision.DoesNotExist:
            return

        if decision.state == PostPublicationEmailDecision.State.QUEUED:
            field.disabled = True
            field.initial = True
            self.initial["notify_subscribers_on_first_publication"] = True
            field.help_text = (
                "Locked: a publication notification was queued when this post first became public."
            )
        elif decision.state == PostPublicationEmailDecision.State.SUPPRESSED:
            field.disabled = True
            field.initial = False
            self.initial["notify_subscribers_on_first_publication"] = False
            field.help_text = (
                "Locked: publication notification was permanently suppressed for this post."
            )
