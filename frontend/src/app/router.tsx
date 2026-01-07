// frontend/src/app/router.tsx
// Application routes for secretroom.
// - Public: / (the only entry point, shows login UI)
// - Protected: everything else (redirects back to / with ?next=...)

import { createBrowserRouter } from "react-router-dom";

import { RootLayout } from "@/app/layouts/RootLayout";
import { HomePage } from "@/pages/home/HomePage";
import { DebugAuthPage } from "@/pages/DebugAuthPage";
import { LoginPage } from "@/pages/auth/LoginPage";
import { RequireAuth } from "@/lib/RequireAuth";
import { PostsPage } from "@/pages/posts/PostsPage";
import { EditorPage } from "@/pages/editor/EditorPage";

export const router = createBrowserRouter([
  // Hidden door: only /
  {
    path: "/",
    element: <LoginPage />,
  },

  // Protected app lives under /app/*
  {
    path: "/app",
    element: (
      <RequireAuth>
        <RootLayout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <HomePage /> },
      { path: "posts", element: <PostsPage /> },
      { path: "posts/:id", element: <EditorPage /> },
      { path: "debug/auth", element: <DebugAuthPage /> },
    ],
  },
]);
