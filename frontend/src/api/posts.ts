// frontend/src/api/posts.ts
//
// Posts API client.

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
};

export type GetPostResponse = {
  ok: boolean;
  item?: PostItem;
  error?: string;
};

export async function getPost(id: number): Promise<GetPostResponse> {
  return http<GetPostResponse>(`/api/posts/${id}`, { method: "GET" });
}
