// frontend/src/api/posts.ts
//
// Posts API client.
// - Typed responses
// - Typed patch payload (only fields the API supports)
// - Prepared for list/create flows (can be unused for now)

import { http } from "@/shared/api/http";

export type PostStatus = "draft" | "published";

export type PostItem = {
  id: number;
  title: string | null;
  slug: string | null;
  status: PostStatus | string | null;
  published_at: string | null;
  updated_at: string | null;
  created_at: string | null;

  // Post body (markdown source)
  body_md?: string | null;
};

export type ApiErrorResponse = {
  ok: false;
  error: string;
};

export type ApiOkResponse<T> = {
  ok: true;
  item: T;
};

export type GetPostResponse = ApiOkResponse<PostItem> | ApiErrorResponse;

export type PatchPostInput = Partial<Pick<PostItem, "title" | "body_md">>;
export type PatchPostResponse = ApiOkResponse<PostItem> | ApiErrorResponse;

/**
 * Fetch single post by id.
 */
export async function getPost(id: number): Promise<GetPostResponse> {
  return http<GetPostResponse>(`/api/posts/${id}`, { method: "GET" });
}

/**
 * Patch post fields supported by API (currently: title, body_md).
 * NOTE: This function does not try to validate business rules locally.
 * Backend remains the source of truth (e.g. empty title checks).
 */
export async function patchPost(id: number, patch: PatchPostInput): Promise<PatchPostResponse> {
  return http<PatchPostResponse>(`/api/posts/${id}`, {
    method: "PATCH",
    body: patch,
  });
}

/* ------------------------------------------------------------------ */
/* Prepared for next steps (optional to use right now)                  */
/* ------------------------------------------------------------------ */

export type ListPostsResponse =
  | { ok: true; items: PostItem[] }
  | ApiErrorResponse;

/**
 * List posts (admin feed). Backend endpoint must exist: GET /api/posts
 */
export async function listPosts(): Promise<ListPostsResponse> {
  return http<ListPostsResponse>(`/api/posts`, { method: "GET" });
}

export type CreatePostInput = {
  title?: string;
  body_md?: string;
};

export type CreatePostResponse = ApiOkResponse<PostItem> | ApiErrorResponse;

/**
 * Create a new post (draft). Backend endpoint must exist: POST /api/posts
 */
export async function createPost(input: CreatePostInput = {}): Promise<CreatePostResponse> {
  return http<CreatePostResponse>(`/api/posts`, {
    method: "POST",
    body: input,
  });
}
