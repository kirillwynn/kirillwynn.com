// @vitest-environment jsdom

import { readFileSync } from "node:fs";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { metadata as confirmMetadata } from "@/app/subscriptions/confirm/page";
import { metadata as unsubscribeMetadata } from "@/app/subscriptions/unsubscribe/page";
import { SubscriptionCredentialAction } from "@/components/subscription-credential-action";
import { SubscriptionForm } from "@/components/subscription-form";

const { authState } = vi.hoisted(() => ({
    authState: {
        value: {
            me: {
                authenticated: false,
                user: null,
                providers: {
                    google: { available: false, connected: false },
                    github: { available: false, connected: false },
                },
                csrf_token: "masked-csrf-token",
            },
            refresh: () => Promise.resolve(),
            status: "ready",
        },
    },
}));

vi.mock("@/components/auth-provider", () => ({
    useAuth: () => authState.value,
}));

function render(element: React.ReactNode): {
    container: HTMLDivElement;
    root: Root;
} {
    const container = document.createElement("div");
    document.body.append(container);
    const root = createRoot(container);
    act(() => {
        root.render(element);
    });
    return { container, root };
}

async function settle() {
    await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
    });
}

function setInput(input: HTMLInputElement, value: string) {
    const descriptor = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value",
    );
    if (descriptor?.set) {
        // eslint-disable-next-line @typescript-eslint/unbound-method
        Reflect.apply(descriptor.set, input, [value]);
    }
    act(() => {
        input.dispatchEvent(new Event("input", { bubbles: true }));
    });
}

function requiredElement<T extends Element>(
    container: ParentNode,
    selector: string,
    constructor: { new (): T },
): T {
    const element = container.querySelector(selector);
    if (!(element instanceof constructor)) {
        throw new Error(`Missing test element: ${selector}`);
    }
    return element;
}

async function submitForm(container: ParentNode) {
    await act(async () => {
        requiredElement(container, "form", HTMLFormElement).dispatchEvent(
            new Event("submit", { bubbles: true, cancelable: true }),
        );
        await Promise.resolve();
        await Promise.resolve();
    });
}

async function clickButton(container: ParentNode) {
    await act(async () => {
        requiredElement(container, "button", HTMLButtonElement).dispatchEvent(
            new MouseEvent("click", { bubbles: true }),
        );
        await Promise.resolve();
        await Promise.resolve();
    });
}

function fetchCall(index = 0) {
    const call = vi.mocked(fetch).mock.calls[index];
    return { input: call[0], init: call[1] };
}

beforeEach(() => {
    authState.value.status = "ready";
    authState.value.me.csrf_token = "masked-csrf-token";
    vi.stubGlobal("fetch", vi.fn());
    window.history.replaceState(null, "", "/");
    (
        globalThis as typeof globalThis & {
            IS_REACT_ACT_ENVIRONMENT: boolean;
        }
    ).IS_REACT_ACT_ENVIRONMENT = true;
});

afterEach(() => {
    document.body.replaceChildren();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
});

describe("subscription form", () => {
    it("uses native email semantics, CSRF, generic success, and no browser persistence", async () => {
        const fetchMock = vi.mocked(fetch);
        fetchMock.mockResolvedValue(
            new Response(
                JSON.stringify({
                    detail: "If the address can be subscribed, a confirmation email will be sent.",
                }),
                {
                    status: 202,
                    headers: { "Content-Type": "application/json" },
                },
            ),
        );
        const localSet = vi.spyOn(Storage.prototype, "setItem");
        const { container } = render(<SubscriptionForm />);
        const input = container.querySelector<HTMLInputElement>("input");
        const form = container.querySelector("form");
        expect(input?.type).toBe("email");
        expect(input?.required).toBe(true);
        expect(input?.getAttribute("autocomplete")).toBe("email");

        if (!input || !form) {
            throw new Error("Subscription form did not render");
        }
        setInput(input, "reader@example.com");
        await submitForm(container);

        expect(fetchMock).toHaveBeenCalledOnce();
        const call = fetchCall();
        expect(call.input).toBe("/api/v1/subscriptions/");
        expect(call.init?.method).toBe("POST");
        expect(call.init?.credentials).toBe("same-origin");
        expect(
            (call.init?.headers as Record<string, string>)["X-CSRFToken"],
        ).toBe("masked-csrf-token");
        expect(call.init?.body).toBe(
            JSON.stringify({ email: "reader@example.com" }),
        );
        expect(container.textContent).toContain("Check your inbox");
        expect(input.value).toBe("");
        expect(localSet).not.toHaveBeenCalled();
    });

    it.each([
        [403, "could not be completed"],
        [429, "Too many attempts"],
        [500, "could not be completed"],
    ])(
        "renders the %s failure state without automatic retry",
        async (status, text) => {
            const fetchMock = vi.mocked(fetch);
            fetchMock.mockResolvedValue(new Response("{}", { status }));
            const { container } = render(<SubscriptionForm />);
            const input = requiredElement(container, "input", HTMLInputElement);
            setInput(input, "reader@example.com");

            await submitForm(container);

            expect(container.textContent).toContain(text);
            expect(fetchMock).toHaveBeenCalledOnce();
        },
    );

    it("renders a network failure and does not retry", async () => {
        const fetchMock = vi.mocked(fetch);
        fetchMock.mockRejectedValue(new TypeError("offline"));
        const { container } = render(<SubscriptionForm />);
        setInput(
            requiredElement(container, "input", HTMLInputElement),
            "reader@example.com",
        );

        await submitForm(container);

        expect(container.textContent).toContain("could not be completed");
        expect(fetchMock).toHaveBeenCalledOnce();
    });
});

describe("confirmation and unsubscribe landing pages", () => {
    it.each([
        ["confirm", "/api/v1/subscriptions/confirm/", "confirmed"],
        ["unsubscribe", "/api/v1/subscriptions/unsubscribe/", "unsubscribed"],
    ] as const)(
        "requires an explicit %s click and removes the fragment before mutation",
        async (kind, endpoint, status) => {
            const fetchMock = vi.mocked(fetch);
            fetchMock.mockResolvedValue(
                new Response(JSON.stringify({ status }), {
                    status: 200,
                    headers: { "Content-Type": "application/json" },
                }),
            );
            window.history.replaceState(
                null,
                "",
                `/subscriptions/${kind}/#credential=secret%3Acredential`,
            );
            const storageSet = vi.spyOn(Storage.prototype, "setItem");
            const { container } = render(
                <SubscriptionCredentialAction kind={kind} />,
            );
            await settle();

            expect(window.location.hash).toBe("");
            expect(fetchMock).not.toHaveBeenCalled();
            await clickButton(container);

            const call = fetchCall();
            expect(call.input).toBe(endpoint);
            expect(call.init?.method).toBe("POST");
            expect(
                (call.init?.headers as Record<string, string>)["X-CSRFToken"],
            ).toBe("masked-csrf-token");
            expect(call.init?.body).toBe(
                JSON.stringify({
                    credential: "secret:credential",
                }),
            );
            expect(storageSet).not.toHaveBeenCalled();
        },
    );

    it("shows invalid links without any GET mutation", async () => {
        const fetchMock = vi.mocked(fetch);
        window.history.replaceState(null, "", "/subscriptions/confirm/");
        const { container } = render(
            <SubscriptionCredentialAction kind="confirm" />,
        );
        await settle();

        expect(container.textContent).toContain("invalid, expired");
        expect(container.querySelector("button")).toBeNull();
        expect(fetchMock).not.toHaveBeenCalled();
    });

    it("maps an invalid credential and infrastructure failure to distinct states", async () => {
        const fetchMock = vi.mocked(fetch);
        fetchMock
            .mockResolvedValueOnce(new Response("{}", { status: 400 }))
            .mockRejectedValueOnce(new TypeError("offline"));

        window.history.replaceState(
            null,
            "",
            "/subscriptions/confirm/#credential=invalid",
        );
        const invalid = render(<SubscriptionCredentialAction kind="confirm" />);
        await settle();
        await clickButton(invalid.container);
        expect(invalid.container.textContent).toContain("invalid, expired");
        act(() => {
            invalid.root.unmount();
        });

        window.history.replaceState(
            null,
            "",
            "/subscriptions/unsubscribe/#credential=valid",
        );
        const unavailable = render(
            <SubscriptionCredentialAction kind="unsubscribe" />,
        );
        await settle();
        await clickButton(unavailable.container);
        expect(unavailable.container.textContent).toContain(
            "could not be completed",
        );
    });

    it("sets noindex and no-referrer metadata", () => {
        for (const metadata of [confirmMetadata, unsubscribeMetadata]) {
            expect(metadata.robots).toEqual({
                index: false,
                follow: false,
            });
            expect(metadata.referrer).toBe("no-referrer");
        }
    });
});

describe("same-origin route boundary", () => {
    it("adds only exact subscription and webhook rewrites", () => {
        const config = readFileSync("next.config.ts", "utf8");
        for (const route of [
            "/api/v1/subscriptions/",
            "/api/v1/subscriptions/confirm/",
            "/api/v1/subscriptions/unsubscribe/",
            "/api/v1/subscriptions/unsubscribe/one-click/",
            "/api/v1/email/webhooks/resend/",
        ]) {
            expect(config).toContain(`source: "${route}"`);
        }
        expect(config).not.toContain('source: "/api/:path*"');
        expect(config).not.toContain('source: "/api/v1/:path*"');
    });

    it("moves the form to the dedicated Draft Mode-aware page", () => {
        const postPage = readFileSync("app/posts/[slug]/page.tsx", "utf8");
        const feedPage = readFileSync("app/page.tsx", "utf8");
        const subscriptionsPage = readFileSync(
            "app/subscriptions/page.tsx",
            "utf8",
        );

        expect(postPage).not.toContain("SubscriptionForm");
        expect(feedPage).not.toContain("SubscriptionForm");
        expect(subscriptionsPage).toContain("<SubscriptionForm />");
        expect(subscriptionsPage).toContain("draft.isEnabled");
    });
});
