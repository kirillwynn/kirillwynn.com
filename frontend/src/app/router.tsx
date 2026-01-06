// frontend/src/app/router.tsx
// Application routes.
// - Public: /login
// - Protected: everything else

import { createBrowserRouter } from "react-router-dom";

import { RootLayout } from "@/app/layouts/RootLayout";
import { HomePage } from "@/pages/home/HomePage";
import { LoginPage } from "@/pages/auth/LoginPage";
import { DebugAuthPage } from "@/pages/DebugAuthPage";
import { RequireAuth } from "@/lib/RequireAuth";

export const router = createBrowserRouter([
  {
    path: "/",
    element: (
      <RequireAuth>
        <RootLayout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <HomePage /> },
      { path: "debug/auth", element: <DebugAuthPage /> },
    ],
  },
  {
    path: "/login",
    element: <LoginPage />,
  },
]);
