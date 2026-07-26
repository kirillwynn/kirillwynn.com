from django.urls import path

from apps.discussions.api.views import (
    CommentDetailAPIView,
    CommentReplyAPIView,
    CommentThreadAPIView,
    PostCommentListCreateAPIView,
)

app_name = "discussions_api"

urlpatterns = [
    path(
        "posts/<str:slug>/comments/",
        PostCommentListCreateAPIView.as_view(),
        name="post-comments",
    ),
    path("comments/<int:pk>/thread/", CommentThreadAPIView.as_view(), name="comment-thread"),
    path("comments/<int:pk>/replies/", CommentReplyAPIView.as_view(), name="comment-replies"),
    path("comments/<int:pk>/", CommentDetailAPIView.as_view(), name="comment-detail"),
]
