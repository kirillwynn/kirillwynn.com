from django.urls import path

from apps.blog.api.views import PostDetailAPIView, PostListAPIView, PreviewResolveAPIView

app_name = "blog_api"

urlpatterns = [
    path("posts/", PostListAPIView.as_view(), name="post-list"),
    path("posts/<slug:slug>/", PostDetailAPIView.as_view(), name="post-detail"),
    path("preview/resolve/", PreviewResolveAPIView.as_view(), name="preview-resolve"),
]
