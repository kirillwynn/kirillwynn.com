from django.db.models import Count, F
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.blog.api.pagination import PostPagination
from apps.blog.api.query import parse_post_filters
from apps.blog.api.serializers import (
    PostDetailSerializer,
    PostListSerializer,
    prepare_list_lead_images,
)
from apps.blog.models import BlogPostTag
from apps.blog.services.preview import InvalidPreviewCredential, resolve_preview_credential
from apps.blog.services.visibility import public_blog_posts


class PublicAPIViewMixin:
    authentication_classes = []
    permission_classes = [AllowAny]
    http_method_names = ["get", "head", "options"]


class PostListAPIView(PublicAPIViewMixin, ListAPIView):
    serializer_class = PostListSerializer
    pagination_class = PostPagination

    def get_queryset(self):
        filters = parse_post_filters(self.request.query_params)
        queryset = public_blog_posts()
        if filters.tag:
            queryset = queryset.filter(tags__slug=filters.tag).distinct()
        if filters.query:
            return queryset.search(filters.query)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        posts = list(page if page is not None else queryset)
        context = self.get_serializer_context()
        context["lead_images"] = prepare_list_lead_images(posts)
        serializer = self.get_serializer(posts, many=True, context=context)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class TagListAPIView(PublicAPIViewMixin, APIView):
    def get(self, request):
        public_post_ids = public_blog_posts().order_by().values("pk")
        tags = (
            BlogPostTag.objects.filter(content_object_id__in=public_post_ids)
            .values(name=F("tag__name"), slug=F("tag__slug"))
            .annotate(count=Count("content_object_id", distinct=True))
            .order_by("slug", "name")
        )
        return Response({"results": list(tags)})


class PostDetailAPIView(PublicAPIViewMixin, RetrieveAPIView):
    serializer_class = PostDetailSerializer

    def get_object(self):
        if {"token", "credential"} & set(self.request.query_params):
            raise ValidationError("Preview credentials are not accepted by this endpoint.")
        return get_object_or_404(public_blog_posts(), slug=self.kwargs["slug"])


class PreviewResolveAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    http_method_names = ["post", "options"]

    def post(self, request):
        credential = request.data.get("credential")
        try:
            page = resolve_preview_credential(credential)
        except InvalidPreviewCredential as error:
            raise NotFound("Preview is unavailable.") from error

        response = Response(PostDetailSerializer(page, context={"request": request}).data)
        response["Cache-Control"] = "private, no-store"
        response["Pragma"] = "no-cache"
        return response
