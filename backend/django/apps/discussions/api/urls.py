from django.urls import path

from apps.discussions.api.views import (
    CommentDetailAPIView,
    CommentReactionAPIView,
    CommentReactionParticipantAPIView,
    CommentReactionToggleAPIView,
    CommentReplyAPIView,
    CommentThreadAPIView,
    PostCommentListCreateAPIView,
    PostReactionAPIView,
    PostReactionBatchAPIView,
    PostReactionParticipantAPIView,
    PostReactionToggleAPIView,
    ReactionConfigAPIView,
)

app_name = "discussions_api"

urlpatterns = [
    path(
        "reactions/posts/",
        PostReactionBatchAPIView.as_view(),
        name="post-reaction-batch",
    ),
    path(
        "posts/<str:slug>/comments/",
        PostCommentListCreateAPIView.as_view(),
        name="post-comments",
    ),
    path("comments/<int:pk>/thread/", CommentThreadAPIView.as_view(), name="comment-thread"),
    path("comments/<int:pk>/replies/", CommentReplyAPIView.as_view(), name="comment-replies"),
    path(
        "posts/<str:slug>/reactions/",
        PostReactionAPIView.as_view(),
        name="post-reactions",
    ),
    path(
        "posts/<str:slug>/reactions/toggle/",
        PostReactionToggleAPIView.as_view(),
        name="post-reaction-toggle",
    ),
    path(
        "posts/<str:slug>/reactions/<path:emoji>/participants/",
        PostReactionParticipantAPIView.as_view(),
        name="post-reaction-participants",
    ),
    path(
        "comments/<int:pk>/reactions/",
        CommentReactionAPIView.as_view(),
        name="comment-reactions",
    ),
    path(
        "comments/<int:pk>/reactions/toggle/",
        CommentReactionToggleAPIView.as_view(),
        name="comment-reaction-toggle",
    ),
    path(
        "comments/<int:pk>/reactions/<path:emoji>/participants/",
        CommentReactionParticipantAPIView.as_view(),
        name="comment-reaction-participants",
    ),
    path("reactions/config/", ReactionConfigAPIView.as_view(), name="reaction-config"),
    path("comments/<int:pk>/", CommentDetailAPIView.as_view(), name="comment-detail"),
]
