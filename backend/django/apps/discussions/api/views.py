from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Max
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.cache import patch_cache_control, patch_vary_headers
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.blog.services.visibility import public_blog_posts
from apps.discussions.api.pagination import (
    ReactionParticipantPagination,
    ThreadReplyPagination,
    TopLevelCommentPagination,
)
from apps.discussions.api.query import parse_post_reaction_ids
from apps.discussions.api.serializers import (
    serialize_comment,
    serialize_reaction_participant,
)
from apps.discussions.emoji import normalize_emoji
from apps.discussions.models import (
    Comment,
    CommentRateLimitBucket,
    CommentReaction,
    PostReaction,
    ReactionSettings,
)
from apps.discussions.reactions import (
    ReactionRateLimitExceeded,
    ReactionTargetUnavailable,
    comment_reaction_groups,
    post_reaction_groups,
    post_reaction_groups_for_post,
    toggle_comment_reaction,
    toggle_post_reaction,
)
from apps.discussions.services import (
    RateLimitExceeded,
    consume_comment_rate_limit,
    create_reply,
    create_top_level_comment,
    edit_comment,
    ensure_can_interact,
    soft_delete_comment,
)


class CommentThrottled(APIException):
    status_code = 429
    default_detail = "Too many comment mutations. Please try again later."
    default_code = "comment_rate_limited"

    def __init__(self, retry_after):
        self.retry_after = retry_after
        super().__init__()


def _public_post_or_404(slug):
    return get_object_or_404(public_blog_posts(), slug=slug)


def _public_comment_or_404(comment_id):
    public_post_ids = public_blog_posts().order_by().values("pk")
    return get_object_or_404(
        Comment.objects.select_related(
            "author",
            "reply_to_user",
            "thread_root",
            "thread_root__author",
        ).filter(post_id__in=public_post_ids),
        pk=comment_id,
    )


def _roots(post):
    return (
        Comment.objects.filter(post=post, thread_root__isnull=True)
        .select_related("author")
        .annotate(
            reply_count=Count("thread_replies"),
            last_reply_at=Max("thread_replies__created_at"),
        )
        .order_by("-created_at", "-id")
    )


def _root_with_activity(root_id):
    return (
        Comment.objects.filter(pk=root_id)
        .select_related("author")
        .annotate(
            reply_count=Count("thread_replies"),
            last_reply_at=Max("thread_replies__created_at"),
        )
        .get()
    )


def _validate_payload(request, *, allowed):
    if not isinstance(request.data, dict):
        raise ValidationError({"detail": "A JSON object is required."})
    unexpected = set(request.data) - set(allowed)
    if unexpected:
        raise ValidationError({"detail": f"Unexpected field(s): {', '.join(sorted(unexpected))}."})


def _body(request):
    _validate_payload(request, allowed={"body"})
    if "body" not in request.data:
        raise ValidationError({"body": "This field is required."})
    return request.data["body"]


def _emoji(request):
    _validate_payload(request, allowed={"emoji"})
    if "emoji" not in request.data:
        raise ValidationError({"emoji": "This field is required."})
    return normalize_emoji(request.data["emoji"])


class CommentAPIViewMixin:
    permission_classes = [AllowAny]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        patch_cache_control(response, private=True, no_store=True)
        patch_vary_headers(response, ["Cookie"])
        if isinstance(getattr(response, "exception", None), CommentThrottled):
            response["Retry-After"] = str(response.exception.retry_after)
        return response

    def handle_exception(self, exc):
        if isinstance(exc, DjangoValidationError):
            detail = getattr(exc, "message_dict", None) or getattr(exc, "messages", None)
            exc = ValidationError(detail)
        elif isinstance(exc, DjangoPermissionDenied):
            exc = PermissionDenied(str(exc))
        elif isinstance(exc, RateLimitExceeded):
            exc = CommentThrottled(exc.retry_after)
        response = super().handle_exception(exc)
        if isinstance(exc, CommentThrottled):
            response["Retry-After"] = str(exc.retry_after)
        return response

    @staticmethod
    def _mutating_user(request):
        try:
            ensure_can_interact(request.user)
        except DjangoPermissionDenied as error:
            raise PermissionDenied(str(error)) from error
        return request.user

    @staticmethod
    def _consume(user, scope):
        try:
            consume_comment_rate_limit(user=user, scope=scope)
        except RateLimitExceeded as error:
            raise CommentThrottled(error.retry_after) from error


class PostCommentListCreateAPIView(CommentAPIViewMixin, APIView):
    http_method_names = ["get", "post", "head", "options"]

    def get(self, request, slug):
        post = _public_post_or_404(slug)
        paginator = TopLevelCommentPagination()
        page = paginator.paginate_queryset(_roots(post), request, view=self)
        grouped = comment_reaction_groups(page, viewer=request.user)
        results = [
            serialize_comment(
                comment,
                viewer=request.user,
                reactions=grouped[comment.pk],
            )
            for comment in page
        ]
        return paginator.get_paginated_response(results)

    def post(self, request, slug):
        post = _public_post_or_404(slug)
        user = self._mutating_user(request)
        self._consume(user, CommentRateLimitBucket.Scope.CREATE)
        comment = create_top_level_comment(post=post, author=user, body=_body(request))
        comment.reply_count = 0
        comment.last_reply_at = None
        return Response(serialize_comment(comment, viewer=user, reactions=[]), status=201)


class CommentThreadAPIView(CommentAPIViewMixin, APIView):
    http_method_names = ["get", "head", "options"]

    def get(self, request, pk):
        selected = _public_comment_or_404(pk)
        root_id = selected.thread_root_id or selected.pk
        root = _root_with_activity(root_id)
        replies = (
            Comment.objects.filter(thread_root_id=root_id)
            .select_related("author", "reply_to_user", "thread_root")
            .order_by("created_at", "id")
        )
        paginator = ThreadReplyPagination()
        page = paginator.paginate_queryset(replies, request, view=self)
        grouped = comment_reaction_groups([root, *page], viewer=request.user)
        response = paginator.get_paginated_response(
            [
                serialize_comment(
                    reply,
                    viewer=request.user,
                    reactions=grouped[reply.pk],
                )
                for reply in page
            ]
        )
        response.data["root"] = serialize_comment(
            root,
            viewer=request.user,
            reactions=grouped[root.pk],
        )
        return response


class CommentReplyAPIView(CommentAPIViewMixin, APIView):
    http_method_names = ["post", "options"]

    def post(self, request, pk):
        _public_comment_or_404(pk)
        user = self._mutating_user(request)
        self._consume(user, CommentRateLimitBucket.Scope.CREATE)
        reply = create_reply(target_id=pk, author=user, body=_body(request))
        return Response(serialize_comment(reply, viewer=user, reactions=[]), status=201)


class CommentDetailAPIView(CommentAPIViewMixin, APIView):
    http_method_names = ["patch", "delete", "options"]

    def patch(self, request, pk):
        _public_comment_or_404(pk)
        user = self._mutating_user(request)
        self._consume(user, CommentRateLimitBucket.Scope.MUTATION)
        comment = edit_comment(comment_id=pk, actor=user, body=_body(request))
        if comment.thread_root_id is None:
            comment = _root_with_activity(comment.pk)
        else:
            comment = (
                Comment.objects.select_related(
                    "author",
                    "reply_to_user",
                    "thread_root",
                )
                .filter(pk=comment.pk)
                .get()
            )
        grouped = comment_reaction_groups([comment], viewer=user)
        return Response(serialize_comment(comment, viewer=user, reactions=grouped[comment.pk]))

    def delete(self, request, pk):
        _public_comment_or_404(pk)
        user = self._mutating_user(request)
        self._consume(user, CommentRateLimitBucket.Scope.MUTATION)
        soft_delete_comment(comment_id=pk, actor=user)
        return Response(status=204)


class ReactionThrottled(APIException):
    status_code = 429
    default_detail = "Too many reaction toggles. Please try again later."
    default_code = "reaction_rate_limited"

    def __init__(self, retry_after):
        self.retry_after = retry_after
        super().__init__()


class ReactionAPIViewMixin(CommentAPIViewMixin):
    def handle_exception(self, exc):
        if isinstance(exc, ReactionRateLimitExceeded):
            exc = ReactionThrottled(exc.retry_after)
        elif isinstance(exc, ReactionTargetUnavailable):
            exc = Http404()
        response = super().handle_exception(exc)
        if isinstance(exc, ReactionThrottled):
            response["Retry-After"] = str(exc.retry_after)
        return response

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        exception = getattr(response, "exception", None)
        if isinstance(exception, ReactionThrottled):
            response["Retry-After"] = str(exception.retry_after)
        return response


class PostReactionAPIView(ReactionAPIViewMixin, APIView):
    http_method_names = ["get", "head", "options"]

    def get(self, request, slug):
        post = _public_post_or_404(slug)
        return Response({"reactions": post_reaction_groups_for_post(post, viewer=request.user)})


class PostReactionBatchAPIView(ReactionAPIViewMixin, APIView):
    authentication_classes = [SessionAuthentication]
    http_method_names = ["get", "head", "options"]

    def get(self, request):
        requested_ids = parse_post_reaction_ids(request.query_params)
        visible_posts = list(
            public_blog_posts()
            .filter(pk__in=requested_ids)
            .select_related(None)
            .prefetch_related(None)
            .only("pk", "slug")
        )
        posts_by_id = {post.pk: post for post in visible_posts}
        ordered_posts = [
            posts_by_id[post_id] for post_id in requested_ids if post_id in posts_by_id
        ]
        grouped = post_reaction_groups(ordered_posts, viewer=request.user)
        return Response(
            {
                "results": [
                    {
                        "post_id": post.pk,
                        "slug": post.slug,
                        "reactions": grouped[post.pk],
                    }
                    for post in ordered_posts
                ]
            }
        )


class PostReactionToggleAPIView(ReactionAPIViewMixin, APIView):
    http_method_names = ["post", "options"]

    def post(self, request, slug):
        post = _public_post_or_404(slug)
        user = self._mutating_user(request)
        post, added = toggle_post_reaction(
            post_id=post.pk,
            user=user,
            emoji=_emoji(request),
        )
        return Response(
            {
                "action": "added" if added else "removed",
                "reactions": post_reaction_groups_for_post(post, viewer=user),
            }
        )


class CommentReactionAPIView(ReactionAPIViewMixin, APIView):
    http_method_names = ["get", "head", "options"]

    def get(self, request, pk):
        comment = _public_comment_or_404(pk)
        grouped = comment_reaction_groups([comment], viewer=request.user)
        return Response({"reactions": grouped[comment.pk]})


class CommentReactionToggleAPIView(ReactionAPIViewMixin, APIView):
    http_method_names = ["post", "options"]

    def post(self, request, pk):
        _public_comment_or_404(pk)
        user = self._mutating_user(request)
        comment, added = toggle_comment_reaction(
            comment_id=pk,
            user=user,
            emoji=_emoji(request),
        )
        grouped = comment_reaction_groups([comment], viewer=user)
        return Response(
            {
                "action": "added" if added else "removed",
                "reactions": grouped[comment.pk],
            }
        )


class ReactionParticipantAPIView(ReactionAPIViewMixin, APIView):
    model = None
    target_field = ""

    def reactions(self, request, **kwargs):
        raise NotImplementedError

    def get(self, request, **kwargs):
        emoji_value = normalize_emoji(kwargs["emoji"])
        queryset = (
            self.reactions(request, **kwargs)
            .filter(emoji=emoji_value)
            .select_related("user")
            .order_by("created_at", "id")
        )
        paginator = ReactionParticipantPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(
            [serialize_reaction_participant(reaction.user) for reaction in page]
        )


class PostReactionParticipantAPIView(ReactionParticipantAPIView):
    http_method_names = ["get", "head", "options"]

    def reactions(self, request, **kwargs):
        post = _public_post_or_404(kwargs["slug"])
        return PostReaction.objects.filter(post=post, catalog_item__isnull=True)


class CommentReactionParticipantAPIView(ReactionParticipantAPIView):
    http_method_names = ["get", "head", "options"]

    def reactions(self, request, **kwargs):
        comment = _public_comment_or_404(kwargs["pk"])
        if comment.public_status != "visible":
            raise Http404
        return CommentReaction.objects.filter(comment=comment, catalog_item__isnull=True)


class ReactionConfigAPIView(ReactionAPIViewMixin, APIView):
    http_method_names = ["get", "head", "options"]

    def get(self, request):
        configured = ReactionSettings.for_request(request)
        return Response({"quick_reactions": configured.quick_reactions})
