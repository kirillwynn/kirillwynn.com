from django.urls import path

from apps.blog.api.views import (
    PostDetailAPIView,
    PostListAPIView,
    PreviewResolveAPIView,
    TagListAPIView,
)

app_name = "blog_api"

urlpatterns = [
    path("posts/", PostListAPIView.as_view(), name="post-list"),
    path("tags/", TagListAPIView.as_view(), name="tag-list"),
    path("posts/<str:slug>/", PostDetailAPIView.as_view(), name="post-detail"),
    path("preview/resolve/", PreviewResolveAPIView.as_view(), name="preview-resolve"),
]
