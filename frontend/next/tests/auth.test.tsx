// @vitest-environment jsdom

import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AccountPanel } from "@/components/account-panel";
import { AuthProvider } from "@/components/auth-provider";
import { ProviderForm } from "@/components/provider-form";
import { SiteHeader } from "@/components/site-header";
import { authErrorMessage, type MeResponse, safeReturnTo } from "@/lib/auth";
import { PUBLIC_URL_CHANGE_EVENT } from "@/lib/feed-browser";

let currentPath = "/";
let currentSearch = "";

vi.mock("next/navigation", () => ({
    usePathname: () => currentPath,
    useSearchParams: () => new URLSearchParams(currentSearch),
}));

const anonymous: MeResponse = {
    authenticated: false,
    user: null,
    providers: {
        google: { available: true, connected: false },
        github: { available: true, connected: false },
    },
    csrf_token: "masked-csrf-token",
};

const authenticated: MeResponse = {
    authenticated: true,
    user: {
        id: 42,
        nickname: "<Safe Reader>",
        display_name: "<Safe Reader>",
        nickname_suggestion: null,
        email: "reader@example.com",
        email_verified: true,
        profile_complete: true,
        has_usable_password: true,
        nickname_change_available_at: null,
        is_admin: false,
        is_banned: false,
        can_interact: true,
    },
    providers: {
        google: { available: true, connected: true },
        github: { available: true, connected: false },
    },
    csrf_token: "masked-csrf-token",
};

function jsonResponse(payload: MeResponse, status = 200): Response {
    return new Response(JSON.stringify(payload), {
        status,
        headers: { "Content-Type": "application/json" },
    });
}

async function renderWithAuth(
    child: React.ReactNode,
    payload: MeResponse,
): Promise<{ container: HTMLDivElement; root: Root }> {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(payload));
    const container = document.createElement("div");
    document.body.append(container);
    const root = createRoot(container);
    act(() => {
        root.render(createElement(AuthProvider, null, child));
    });
    await flushEffects();
    return { container, root };
}

async function flushEffects(): Promise<void> {
    await act(async () => {
        await Promise.resolve();
    });
}

beforeEach(() => {
    currentPath = "/";
    currentSearch = "";
    window.history.replaceState({}, "", "/");
    vi.stubGlobal("fetch", vi.fn());
    (
        globalThis as typeof globalThis & {
            IS_REACT_ACT_ENVIRONMENT: boolean;
        }
    ).IS_REACT_ACT_ENVIRONMENT = true;
});

afterEach(() => {
    vi.unstubAllGlobals();
    document.body.replaceChildren();
});

describe("auth forms and return-to policy", () => {
    it("renders provider login as a CSRF-protected browser POST form", () => {
        const html = renderToStaticMarkup(
            <ProviderForm
                available
                csrfToken="masked-token"
                next="/posts/привет?reply=7"
                provider="google"
            />,
        );

        expect(html).toContain('method="post"');
        expect(html).toContain('action="/accounts/google/login/"');
        expect(html).toContain('name="csrfmiddlewaretoken"');
        expect(html).toContain('value="masked-token"');
        expect(html).toContain('name="next"');
        expect(html).toContain('name="process" value="login"');
    });

    it("renders explicit provider connection without a disconnect affordance", () => {
        const html = renderToStaticMarkup(
            <ProviderForm
                available
                csrfToken="masked-token"
                next="/account"
                process="connect"
                provider="github"
            />,
        );

        expect(html).toContain("Connect GitHub");
        expect(html).toContain('name="process" value="connect"');
        expect(html).not.toContain("Disconnect");
    });

    it("mirrors the backend return-to allowlist and rejects redirect attacks", () => {
        expect(safeReturnTo("/posts/привет?reply=7")).toBe(
            "/posts/привет?reply=7",
        );
        expect(safeReturnTo("/bridge?from=menu%20item")).toBe(
            "/bridge?from=menu item",
        );
        for (const attack of [
            "//evil.example",
            "///evil.example",
            "///posts/foo",
            "////posts/foo",
            "/%2F%2Fposts/foo",
            "/%2f%2fposts/foo",
            "/%252F%252Fposts/foo",
            "/\\evil",
            "javascript:alert(1)",
            "data:text/html,boom",
            "http://evil.example/",
            "https://evil.example/",
            "/posts/good\\evil",
            "/posts/good%5Cevil",
            "/posts/good\rheader",
            "/posts/good\nheader",
            "/posts/good\theader",
            "/posts/good%0Dheader",
            "/posts/good%0Aheader",
            "/posts/good%09header",
            "/posts/good?value=ok\r\nLocation: //evil.example",
            "/bridge?value=%0D%0ALocation%3A%20%2F%2Fevil.example",
            "/account?value=%09header",
            "/posts/good%",
            "/posts/good%2",
            "/posts/good%GG",
            "/api/me/",
            "/accounts/google/login/",
            "/cms/",
            "/django-admin/",
            "/login",
            "/posts/good/extra",
        ]) {
            const result = safeReturnTo(attack);
            expect(result).toBe("/");
            expect(new URL(result, "https://example.com").origin).toBe(
                "https://example.com",
            );
        }
    });

    it("maps provider failures to generic messages", () => {
        expect(authErrorMessage("oauth")).toContain("could not be completed");
        expect(authErrorMessage("provider stack trace")).toContain(
            "could not be completed",
        );
        expect(authErrorMessage("verified_email_required")).toContain(
            "verified email",
        );
    });
});

describe("header auth behavior", () => {
    it("shows Login to anonymous readers without breaking public navigation", async () => {
        const { container, root } = await renderWithAuth(
            <SiteHeader />,
            anonymous,
        );

        const login = container.querySelector<HTMLAnchorElement>(
            'a[href^="/login?next="]',
        );
        expect(login?.textContent).toBe("Login");
        expect(container.textContent).not.toContain("kirillwynn.com");
        expect(container.querySelector('a[href="/"]')?.textContent).toBe(
            "Feed",
        );
        act(() => {
            root.unmount();
        });
    });

    it("keeps the anonymous Login return route synchronized with live search", async () => {
        window.history.replaceState({}, "", "/?q=%E6%97%A5%E6%9C%AC");
        const { container, root } = await renderWithAuth(
            <SiteHeader />,
            anonymous,
        );
        const loginTarget = () => {
            const href = container
                .querySelector<HTMLAnchorElement>('a[href^="/login?next="]')
                ?.getAttribute("href");
            return new URL(href ?? "", "http://localhost").searchParams.get(
                "next",
            );
        };
        expect(loginTarget()).toBe("/?q=日本");

        window.history.pushState({}, "", "/?q=stage18-no-result");
        act(() => {
            window.dispatchEvent(new Event(PUBLIC_URL_CHANGE_EVENT));
        });
        await flushEffects();

        expect(loginTarget()).toBe("/?q=stage18-no-result");
        act(() => {
            root.unmount();
        });
    });

    it("shows an escaped display name and closes the user menu with Escape", async () => {
        const { container, root } = await renderWithAuth(
            <SiteHeader />,
            authenticated,
        );
        const trigger = container.querySelector<HTMLButtonElement>(
            'button[aria-haspopup="menu"]',
        );
        expect(trigger?.textContent).toContain("<Safe Reader>");
        expect(container.innerHTML).toContain("&lt;Safe Reader&gt;");

        act(() => {
            trigger?.click();
        });
        expect(container.querySelector('[role="menu"]')).not.toBeNull();
        act(() => {
            document.dispatchEvent(
                new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
            );
        });

        expect(container.querySelector('[role="menu"]')).toBeNull();
        expect(document.activeElement).toBe(trigger);

        act(() => {
            trigger?.click();
        });
        currentPath = "/bridge";
        act(() => {
            root.render(
                createElement(AuthProvider, null, createElement(SiteHeader)),
            );
        });
        expect(container.querySelector('[role="menu"]')).toBeNull();
        act(() => {
            root.unmount();
        });
    });

    it("sends logout with masked CSRF and recovers from an expired session", async () => {
        const { container, root } = await renderWithAuth(
            <SiteHeader />,
            authenticated,
        );
        const trigger = container.querySelector<HTMLButtonElement>(
            'button[aria-haspopup="menu"]',
        );
        act(() => {
            trigger?.click();
        });
        vi.mocked(fetch)
            .mockResolvedValueOnce(new Response(null, { status: 403 }))
            .mockResolvedValueOnce(jsonResponse(anonymous));

        const logout = Array.from(container.querySelectorAll("button")).find(
            (button) => button.textContent === "Logout",
        );
        act(() => {
            logout?.click();
        });
        await flushEffects();
        await flushEffects();

        const logoutCall = vi.mocked(fetch).mock.calls[1];
        expect(logoutCall[0]).toBe("/api/v1/auth/logout/");
        const logoutOptions = logoutCall[1] as RequestInit;
        expect(logoutOptions.method).toBe("POST");
        expect(logoutOptions.credentials).toBe("same-origin");
        expect(logoutOptions.body).toBe("{}");
        expect(
            (logoutOptions.headers as Record<string, string>)["X-CSRFToken"],
        ).toBe("masked-csrf-token");
        expect(
            (logoutOptions.headers as Record<string, string>)["Content-Type"],
        ).toBe("application/json");
        expect(container.textContent).toContain("Login");
        act(() => {
            root.unmount();
        });
    });
});

describe("account provider state", () => {
    it("shows connected and available providers for an authenticated user", async () => {
        const { container, root } = await renderWithAuth(
            <AccountPanel />,
            authenticated,
        );

        expect(container.textContent).toContain("GoogleConnected");
        expect(container.textContent).toContain("Connect GitHub");
        expect(
            container
                .querySelector(
                    'form[action="/accounts/github/login/"] input[name="process"]',
                )
                ?.getAttribute("value"),
        ).toBe("connect");
        act(() => {
            root.unmount();
        });
    });

    it("keeps unavailable providers disabled", async () => {
        const unavailable = structuredClone(anonymous);
        unavailable.providers.github.available = false;
        const { container, root } = await renderWithAuth(
            <AccountPanel />,
            unavailable,
        );

        expect(container.textContent).toContain(
            "Sign in to view connected providers",
        );
        act(() => {
            root.unmount();
        });
    });

    it("does not initiate provider linking before primary-email verification", async () => {
        const unverified = structuredClone(authenticated);
        if (unverified.user) {
            unverified.user.email_verified = false;
            unverified.user.can_interact = false;
        }
        unverified.providers.google.connected = false;
        const { container, root } = await renderWithAuth(
            <AccountPanel />,
            unverified,
        );

        expect(container.textContent).toContain(
            "Verify the primary email before connecting another provider",
        );
        const providerButtons = Array.from(
            container.querySelectorAll<HTMLButtonElement>(
                'form[action^="/accounts/"] button',
            ),
        );
        expect(providerButtons).toHaveLength(2);
        expect(providerButtons.every((button) => button.disabled)).toBe(true);
        act(() => {
            root.unmount();
        });
    });
});
