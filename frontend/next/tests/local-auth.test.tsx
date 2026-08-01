// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
    EmailVerificationAction,
    PasswordResetConfirmationForm,
    takeAccountCredentialFromFragment,
} from "@/components/account-credential-action";
import { AuthProvider } from "@/components/auth-provider";
import {
    AccountPasswordForm,
    LocalLoginForm,
    SignupForm,
} from "@/components/local-auth-forms";
import {
    AuthApiError,
    authApiPaths,
    authMutation,
    localLoginDestination,
    type MeResponse,
    validateNickname,
} from "@/lib/auth";

const anonymous: MeResponse = {
    authenticated: false,
    user: null,
    providers: {
        google: { available: true, connected: false },
        github: { available: true, connected: false },
    },
    csrf_token: "masked-csrf-token",
};

const verified: MeResponse = {
    authenticated: true,
    user: {
        id: 42,
        nickname: "Reader",
        display_name: "Reader",
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
    csrf_token: "rotated-csrf-token",
};

function response(
    payload: unknown,
    status = 200,
    headers?: HeadersInit,
): Response {
    const responseHeaders = new Headers({ "Content-Type": "application/json" });
    new Headers(headers).forEach((value, key) => {
        responseHeaders.set(key, value);
    });
    return new Response(JSON.stringify(payload), {
        status,
        headers: responseHeaders,
    });
}

function urlOf(input: RequestInfo | URL): string {
    return typeof input === "string"
        ? input
        : input instanceof URL
          ? input.href
          : input.url;
}

function bodyOf(options: RequestInit | undefined): Record<string, string> {
    if (typeof options?.body !== "string") {
        throw new Error("Expected a JSON string request body.");
    }
    return JSON.parse(options.body) as Record<string, string>;
}

async function waitFor(predicate: () => boolean): Promise<void> {
    for (let attempt = 0; attempt < 50; attempt += 1) {
        await act(async () => {
            await Promise.resolve();
        });
        if (predicate()) {
            return;
        }
    }
    throw new Error("Timed out waiting for local-auth state.");
}

async function renderWithAuth(
    child: React.ReactNode,
): Promise<{ container: HTMLDivElement; root: Root }> {
    const container = document.createElement("div");
    document.body.append(container);
    const root = createRoot(container);
    act(() => {
        root.render(<AuthProvider>{child}</AuthProvider>);
    });
    await waitFor(() => vi.mocked(fetch).mock.calls.length > 0);
    return { container, root };
}

function inputValue(input: HTMLInputElement, value: string): void {
    // eslint-disable-next-line @typescript-eslint/unbound-method
    const setter = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value",
    )?.set;
    setter?.call(input, value);
    act(() => {
        input.dispatchEvent(new Event("input", { bubbles: true }));
    });
}

function submit(form: HTMLFormElement): void {
    act(() => {
        form.dispatchEvent(
            new Event("submit", { bubbles: true, cancelable: true }),
        );
    });
}

beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    window.history.replaceState(null, "", "/");
    (
        globalThis as typeof globalThis & {
            IS_REACT_ACT_ENVIRONMENT: boolean;
        }
    ).IS_REACT_ACT_ENVIRONMENT = true;
});

afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    document.body.replaceChildren();
});

describe("local account credential boundary", () => {
    it("rejects invisible Unicode nickname payloads defensively", () => {
        for (const value of [
            "a\u034fb",
            "a\u180bb",
            "a\ufe0fb",
            "\u115f\u1160",
            "\u3164a",
        ]) {
            expect(validateNickname(value)).toBe("Enter a valid nickname.");
        }
        expect(validateNickname("A\u030ake")).toBeNull();
    });

    it("consumes exactly one fragment credential and immediately clears the URL", () => {
        window.history.replaceState(
            null,
            "",
            "/account/verify-email?source=email#credential=v1.test%2Bvalue",
        );

        expect(takeAccountCredentialFromFragment()).toBe("v1.test+value");
        expect(window.location.pathname).toBe("/account/verify-email");
        expect(window.location.search).toBe("?source=email");
        expect(window.location.hash).toBe("");

        window.history.replaceState(
            null,
            "",
            "/account/verify-email#credential=one&credential=two",
        );
        expect(takeAccountCredentialFromFragment()).toBeNull();
        expect(window.location.hash).toBe("");
    });

    it("posts verification only in the CSRF body and never renders the credential", async () => {
        const raw = "v1.0123456789abcdef0123456789abcdef.1999999999.signature";
        let meCalls = 0;
        vi.mocked(fetch).mockImplementation((input) => {
            const url = urlOf(input);
            if (url === "/api/me/") {
                meCalls += 1;
                return Promise.resolve(
                    response(meCalls === 1 ? anonymous : verified),
                );
            }
            if (url === authApiPaths.verifyEmail) {
                return Promise.resolve(response({ status: "verified" }));
            }
            throw new Error(`Unexpected fetch: ${url}`);
        });
        window.history.replaceState(
            null,
            "",
            `/account/verify-email#credential=${encodeURIComponent(raw)}`,
        );

        const { container, root } = await renderWithAuth(
            <EmailVerificationAction />,
        );
        await waitFor(() => container.textContent.includes("Email verified"));

        const mutation = vi
            .mocked(fetch)
            .mock.calls.find(
                ([input]) => urlOf(input) === authApiPaths.verifyEmail,
            );
        if (!mutation) {
            throw new Error("Missing verification mutation.");
        }
        const options = mutation[1] ?? {};
        expect(options.method).toBe("POST");
        expect(options.credentials).toBe("same-origin");
        expect((options.headers as Record<string, string>)["X-CSRFToken"]).toBe(
            "masked-csrf-token",
        );
        expect(bodyOf(options)).toEqual({ credential: raw });
        expect(window.location.hash).toBe("");
        expect(container.innerHTML).not.toContain(raw);
        act(() => {
            root.unmount();
        });
    });

    it("retains an in-memory reset credential across validation but clears passwords", async () => {
        const raw = "v1.abcdefabcdefabcdefabcdefabcdefab.1999999999.signature";
        let confirmCalls = 0;
        vi.mocked(fetch).mockImplementation((input) => {
            const url = urlOf(input);
            if (url === "/api/me/") {
                return Promise.resolve(response(anonymous));
            }
            if (url === authApiPaths.passwordResetConfirm) {
                confirmCalls += 1;
                return Promise.resolve(
                    confirmCalls === 1
                        ? response(
                              {
                                  errors: {
                                      password: ["Choose a stronger password."],
                                  },
                              },
                              400,
                          )
                        : response({ status: "password_reset" }),
                );
            }
            throw new Error(`Unexpected fetch: ${url}`);
        });
        window.history.replaceState(
            null,
            "",
            `/account/password/reset/confirm#credential=${encodeURIComponent(raw)}`,
        );

        const { container, root } = await renderWithAuth(
            <PasswordResetConfirmationForm />,
        );
        await waitFor(
            () =>
                container.querySelectorAll('input[type="password"]').length ===
                2,
        );
        let inputs = Array.from(
            container.querySelectorAll<HTMLInputElement>(
                'input[type="password"]',
            ),
        );
        expect(inputs.map((input) => input.autocomplete)).toEqual([
            "new-password",
            "new-password",
        ]);
        inputValue(inputs[0], "too-weak");
        inputValue(inputs[1], "too-weak");
        submit(container.querySelector("form") as HTMLFormElement);
        await waitFor(() =>
            container.textContent.includes("Choose a stronger password"),
        );
        inputs = Array.from(
            container.querySelectorAll<HTMLInputElement>(
                'input[type="password"]',
            ),
        );
        expect(inputs.map((input) => input.value)).toEqual(["", ""]);

        inputValue(inputs[0], "Strong replacement passphrase 42!");
        inputValue(inputs[1], "Strong replacement passphrase 42!");
        submit(container.querySelector("form") as HTMLFormElement);
        await waitFor(() => container.textContent.includes("Password reset"));

        const bodies = vi
            .mocked(fetch)
            .mock.calls.filter(
                ([input]) => urlOf(input) === authApiPaths.passwordResetConfirm,
            )
            .map(([, options]) => bodyOf(options));
        expect(bodies).toHaveLength(2);
        expect(bodies.every((body) => body.credential === raw)).toBe(true);
        expect(container.querySelector('input[type="password"]')).toBeNull();
        expect(window.location.hash).toBe("");
        act(() => {
            root.unmount();
        });
    });

    it("retains a verification credential across a bounded 429 retry", async () => {
        const raw = "v1.0123456789abcdef0123456789abcdef.1999999999.signature";
        let verificationCalls = 0;
        let meCalls = 0;
        vi.mocked(fetch).mockImplementation((input) => {
            const url = urlOf(input);
            if (url === "/api/me/") {
                meCalls += 1;
                return Promise.resolve(
                    response(meCalls === 1 ? anonymous : verified),
                );
            }
            if (url === authApiPaths.verifyEmail) {
                verificationCalls += 1;
                return Promise.resolve(
                    verificationCalls === 1
                        ? response(
                              {
                                  detail: "Too many requests.",
                                  status: "auth_rate_limited",
                              },
                              429,
                              { "Retry-After": "30" },
                          )
                        : response({ status: "verified" }),
                );
            }
            throw new Error(`Unexpected fetch: ${url}`);
        });
        window.history.replaceState(
            null,
            "",
            `/account/verify-email#credential=${encodeURIComponent(raw)}`,
        );

        const { container, root } = await renderWithAuth(
            <EmailVerificationAction />,
        );
        await waitFor(() =>
            container.textContent.includes("Too many attempts"),
        );
        expect(window.location.hash).toBe("");
        expect(container.innerHTML).not.toContain(raw);

        const retry = Array.from(container.querySelectorAll("button")).find(
            (button) => button.textContent === "Retry verification",
        );
        if (!retry) {
            throw new Error("Missing verification retry action.");
        }
        act(() => {
            retry.click();
        });
        await waitFor(() => container.textContent.includes("Email verified"));

        const bodies = vi
            .mocked(fetch)
            .mock.calls.filter(
                ([input]) => urlOf(input) === authApiPaths.verifyEmail,
            )
            .map(([, options]) => bodyOf(options));
        expect(bodies).toHaveLength(2);
        expect(bodies.every((body) => body.credential === raw)).toBe(true);
        act(() => {
            root.unmount();
        });
    });

    it("retains a verification credential while retrying the initial CSRF session", async () => {
        const raw = "v1.0123456789abcdef0123456789abcdef.1999999999.signature";
        let meCalls = 0;
        vi.mocked(fetch).mockImplementation((input) => {
            const url = urlOf(input);
            if (url === "/api/me/") {
                meCalls += 1;
                if (meCalls === 1) {
                    return Promise.reject(new Error("network unavailable"));
                }
                return Promise.resolve(
                    response(meCalls === 2 ? anonymous : verified),
                );
            }
            if (url === authApiPaths.verifyEmail) {
                return Promise.resolve(response({ status: "verified" }));
            }
            throw new Error(`Unexpected fetch: ${url}`);
        });
        window.history.replaceState(
            null,
            "",
            `/account/verify-email#credential=${encodeURIComponent(raw)}`,
        );

        const { container, root } = await renderWithAuth(
            <EmailVerificationAction />,
        );
        await waitFor(() =>
            container.textContent.includes("could not be reached"),
        );
        expect(window.location.hash).toBe("");
        expect(container.innerHTML).not.toContain(raw);

        const retry = Array.from(container.querySelectorAll("button")).find(
            (button) => button.textContent === "Retry verification",
        );
        act(() => {
            retry?.click();
        });
        await waitFor(() => container.textContent.includes("Email verified"));

        const mutation = vi
            .mocked(fetch)
            .mock.calls.find(
                ([input]) => urlOf(input) === authApiPaths.verifyEmail,
            );
        expect(mutation ? bodyOf(mutation[1]).credential : null).toBe(raw);
        act(() => {
            root.unmount();
        });
    });

    it("can recover the CSRF session before showing reset password fields", async () => {
        const raw = "v1.abcdefabcdefabcdefabcdefabcdefab.1999999999.signature";
        let meCalls = 0;
        vi.mocked(fetch).mockImplementation((input) => {
            const url = urlOf(input);
            if (url === "/api/me/") {
                meCalls += 1;
                return meCalls === 1
                    ? Promise.reject(new Error("network unavailable"))
                    : Promise.resolve(response(anonymous));
            }
            throw new Error(`Unexpected fetch: ${url}`);
        });
        window.history.replaceState(
            null,
            "",
            `/account/password/reset/confirm#credential=${encodeURIComponent(raw)}`,
        );

        const { container, root } = await renderWithAuth(
            <PasswordResetConfirmationForm />,
        );
        await waitFor(() =>
            container.textContent.includes("could not be reached"),
        );
        expect(container.querySelector('input[type="password"]')).toBeNull();
        const retry = Array.from(container.querySelectorAll("button")).find(
            (button) => button.textContent === "Retry secure session",
        );
        act(() => {
            retry?.click();
        });
        await waitFor(
            () =>
                container.querySelectorAll('input[type="password"]').length ===
                2,
        );
        expect(window.location.hash).toBe("");
        expect(container.innerHTML).not.toContain(raw);
        act(() => {
            root.unmount();
        });
    });
});

describe("local account forms", () => {
    it("routes incomplete local login through trusted profile completion", () => {
        expect(localLoginDestination("/posts/welcome", true, "/")).toBe(
            "/account/profile?next=%2Fposts%2Fwelcome",
        );
        expect(localLoginDestination("/account/profile", false, "/")).toBe("/");
    });

    it("keeps signup fields inert until the CSRF session is ready", async () => {
        let resolveMe: ((value: Response) => void) | undefined;
        vi.mocked(fetch).mockImplementation((input) => {
            if (urlOf(input) !== "/api/me/") {
                throw new Error(`Unexpected fetch: ${urlOf(input)}`);
            }
            return new Promise<Response>((resolve) => {
                resolveMe = resolve;
            });
        });

        const rendered = await renderWithAuth(<SignupForm />);
        const inputs = Array.from(
            rendered.container.querySelectorAll<HTMLInputElement>("input"),
        );
        expect(inputs).toHaveLength(4);
        expect(inputs.every((input) => input.disabled)).toBe(true);

        await act(async () => {
            resolveMe?.(response(anonymous));
            await Promise.resolve();
        });
        await waitFor(() =>
            Array.from(
                rendered.container.querySelectorAll<HTMLInputElement>("input"),
            ).every((input) => !input.disabled),
        );

        act(() => {
            rendered.root.unmount();
        });
    });

    it("keeps password-set success visible after the refreshed account changes state", async () => {
        const oauthOnly: MeResponse = {
            ...verified,
            user: verified.user
                ? { ...verified.user, has_usable_password: false }
                : null,
        };
        let meCalls = 0;
        vi.mocked(fetch).mockImplementation((input) => {
            const url = urlOf(input);
            if (url === "/api/me/") {
                meCalls += 1;
                return Promise.resolve(
                    response(meCalls === 1 ? oauthOnly : verified),
                );
            }
            if (url === authApiPaths.passwordSet) {
                return Promise.resolve(
                    response({
                        status: "password_set",
                        csrf_token: "new-csrf-token",
                    }),
                );
            }
            throw new Error(`Unexpected fetch: ${url}`);
        });

        const rendered = await renderWithAuth(
            <AccountPasswordForm mode="set" />,
        );
        await waitFor(() => rendered.container.querySelector("form") !== null);
        const inputs = Array.from(
            rendered.container.querySelectorAll<HTMLInputElement>(
                'input[type="password"]',
            ),
        );
        inputValue(inputs[0], "OAuth local passphrase 42!");
        inputValue(inputs[1], "OAuth local passphrase 42!");
        submit(rendered.container.querySelector("form") as HTMLFormElement);
        await waitFor(() =>
            rendered.container.textContent.includes("Password set."),
        );

        expect(meCalls).toBe(2);
        expect(rendered.container.querySelector("form")).toBeNull();
        expect(rendered.container.textContent).not.toContain(
            "A password is already set.",
        );
        act(() => {
            rendered.root.unmount();
        });
    });

    it("does not render a password-set form without a verified connected provider", async () => {
        const unavailable: MeResponse = {
            ...verified,
            user: verified.user
                ? {
                      ...verified.user,
                      email_verified: false,
                      has_usable_password: false,
                  }
                : null,
            providers: {
                google: { available: true, connected: false },
                github: { available: true, connected: false },
            },
        };
        vi.mocked(fetch).mockResolvedValue(response(unavailable));

        const rendered = await renderWithAuth(
            <AccountPasswordForm mode="set" />,
        );
        await waitFor(() =>
            rendered.container.textContent.includes(
                "Password setup requires a verified primary email",
            ),
        );

        expect(rendered.container.querySelector("form")).toBeNull();
        expect(
            rendered.container.querySelector('input[type="password"]'),
        ).toBeNull();
        act(() => {
            rendered.root.unmount();
        });
    });

    it("uses password-manager fields and never exposes a username input", async () => {
        vi.mocked(fetch).mockResolvedValue(response(anonymous));
        const signup = await renderWithAuth(<SignupForm />);
        await waitFor(() => signup.container.querySelector("form") !== null);
        expect(
            Array.from(
                signup.container.querySelectorAll<HTMLInputElement>("input"),
            ).map((input) => [input.name, input.autocomplete]),
        ).toEqual([
            ["email", "email"],
            ["nickname", "nickname"],
            ["password", "new-password"],
            ["password_confirmation", "new-password"],
        ]);
        expect(
            signup.container.querySelector('input[name="username"]'),
        ).toBeNull();
        act(() => {
            signup.root.unmount();
        });

        const login = await renderWithAuth(<LocalLoginForm />);
        await waitFor(() => login.container.querySelector("form") !== null);
        expect(
            Array.from(
                login.container.querySelectorAll<HTMLInputElement>("input"),
            ).map((input) => [input.name, input.autocomplete]),
        ).toEqual([
            ["email", "email"],
            ["password", "current-password"],
        ]);
        act(() => {
            login.root.unmount();
        });
    });

    it("refreshes the masked CSRF session after a login 403", async () => {
        let meCalls = 0;
        vi.mocked(fetch).mockImplementation((input) => {
            const url = urlOf(input);
            if (url === "/api/me/") {
                meCalls += 1;
                return Promise.resolve(
                    response({
                        ...anonymous,
                        csrf_token:
                            meCalls === 1 ? "expired-csrf" : "refreshed-csrf",
                    }),
                );
            }
            if (url === authApiPaths.login) {
                return Promise.resolve(
                    response({ detail: "CSRF verification failed." }, 403),
                );
            }
            throw new Error(`Unexpected fetch: ${url}`);
        });

        const rendered = await renderWithAuth(<LocalLoginForm />);
        await waitFor(() => rendered.container.querySelector("form") !== null);
        inputValue(
            rendered.container.querySelector<HTMLInputElement>(
                'input[name="email"]',
            ) as HTMLInputElement,
            "reader@example.com",
        );
        const password = rendered.container.querySelector<HTMLInputElement>(
            'input[name="password"]',
        ) as HTMLInputElement;
        inputValue(password, "never-persist-this-password");
        submit(rendered.container.querySelector("form") as HTMLFormElement);
        await waitFor(() => meCalls === 2);

        const loginCall = vi
            .mocked(fetch)
            .mock.calls.find(([input]) => urlOf(input) === authApiPaths.login);
        expect(
            (loginCall?.[1]?.headers as Record<string, string>)["X-CSRFToken"],
        ).toBe("expired-csrf");
        expect(password.value).toBe("");
        expect(rendered.container.textContent).toContain(
            "CSRF verification failed.",
        );
        act(() => {
            rendered.root.unmount();
        });
    });

    it("surfaces bounded 429 retry guidance from fixed same-origin mutations", async () => {
        vi.mocked(fetch).mockResolvedValue(
            response(
                { detail: "Too many requests.", status: "auth_rate_limited" },
                429,
                { "Retry-After": "37" },
            ),
        );

        await expect(
            authMutation(
                authApiPaths.login,
                { email: "reader@example.com", password: "secret" },
                "csrf",
            ),
        ).rejects.toMatchObject({
            name: "AuthApiError",
            status: 429,
            code: "auth_rate_limited",
            retryAfter: 37,
        } satisfies Partial<AuthApiError>);
    });
});
