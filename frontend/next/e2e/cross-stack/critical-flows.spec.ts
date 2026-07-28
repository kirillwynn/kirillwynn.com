import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

const backend = "../../backend/django";
const djangoEnvironment = {
    ...process.env,
    DJANGO_SETTINGS_MODULE: "config.settings.cross_stack",
    DJANGO_TEST_DATABASE: "/tmp/kirillwynn-cross-stack.sqlite3",
};
type SessionResponse = {
    authenticated: boolean;
    providers: {
        google: { connected: boolean };
        github: { connected: boolean };
    };
};

function subscriptionState(action: string, email: string): string {
    return execFileSync(
        ".venv/bin/python",
        ["tests/e2e/subscription_state.py", action, email],
        {
            cwd: backend,
            encoding: "utf-8",
            env: djangoEnvironment,
        },
    ).trim();
}

async function login(page: Page, provider: "Google" | "GitHub" = "Google") {
    await page.goto("/login?next=%2Fposts%2Fcross-stack-systems");
    await page
        .getByRole("button", { name: `Continue with ${provider}` })
        .click();
    await expect(page).toHaveURL(/\/posts\/cross-stack-systems$/);
    await expect(page.getByRole("button", { name: /reader/i })).toBeVisible();
}

test("real allauth provider callbacks create and persist a Django database session", async ({
    page,
}) => {
    await login(page, "Google");
    const firstSession = await page.request.get("/api/me/");
    expect(firstSession.ok()).toBe(true);
    const firstSessionPayload = (await firstSession.json()) as SessionResponse;
    expect(firstSessionPayload.authenticated).toBe(true);

    await page.reload();
    await expect(page.getByRole("button", { name: /reader/i })).toBeVisible();
    await page.getByRole("button", { name: /reader/i }).click();
    await page.getByRole("menuitem", { name: "Logout" }).click();
    await expect(
        page.getByRole("link", { name: "Login", exact: true }),
    ).toBeVisible();

    await login(page, "GitHub");
    const currentSession = (await (
        await page.request.get("/api/me/")
    ).json()) as SessionResponse;
    const providers = currentSession.providers;
    expect(providers.google.connected).toBe(true);
    expect(providers.github.connected).toBe(true);
});

test("real CSRF, API views, rewrites, and database persistence cover comments, replies, and reactions", async ({
    page,
}, testInfo) => {
    await login(page);

    const rejected = await page.evaluate(async () => {
        const response = await fetch(
            "/api/v1/posts/cross-stack-systems/comments/",
            {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ body: "missing CSRF" }),
            },
        );
        return response.status;
    });
    expect(rejected).toBe(403);

    const body = `Persisted browser comment ${String(testInfo.retry)}`;
    await page.getByPlaceholder("Write a plain-text comment").fill(body);
    await page.getByRole("button", { name: "Comment", exact: true }).click();
    await expect(page.getByText(body)).toBeVisible();
    await page.reload();
    await expect(page.getByText(body)).toBeVisible();

    const root = page
        .locator("article[data-comment-id]")
        .filter({ hasText: "Seeded root for the real Django thread." });
    await root.getByRole("button", { name: "Reply" }).click();
    const dialog = page.getByRole("dialog", {
        name: "Thread for comment by Site Author",
    });
    const reply = `Persisted reply ${String(testInfo.retry)}`;
    await dialog.getByPlaceholder("Write a reply").fill(reply);
    await dialog
        .locator("footer")
        .getByRole("button", { name: "Reply", exact: true })
        .click();
    await expect(dialog.getByText(reply)).toBeVisible();
    await page.keyboard.press("Escape");
    await root.getByRole("button", { name: "Reply" }).click();
    await expect(
        page
            .getByRole("dialog", { name: "Thread for comment by Site Author" })
            .getByText(reply),
    ).toBeVisible();
    await page.keyboard.press("Escape");

    const postReactions = page
        .getByRole("group", { name: "Reactions" })
        .first();
    const fire = postReactions.getByRole("button", {
        name: /(?:Add|Remove) 🔥 reaction/,
    });
    const before = await fire.getAttribute("aria-pressed");
    await fire.click();
    await expect(fire).toHaveAttribute(
        "aria-pressed",
        before === "true" ? "false" : "true",
    );
    await page.reload();
    await expect(
        page
            .getByRole("group", { name: "Reactions" })
            .first()
            .getByRole("button", { name: /(?:Add|Remove) 🔥 reaction/ }),
    ).toHaveAttribute("aria-pressed", before === "true" ? "false" : "true");
});

test("real subscription endpoints persist confirm and unsubscribe transitions", async ({
    page,
}, testInfo) => {
    const email = `cross-stack-${String(testInfo.retry)}@example.test`;
    await page.goto("/");
    await page.getByRole("textbox", { name: "Email address" }).fill(email);
    await page.getByRole("button", { name: "Subscribe" }).click();
    await expect(page.getByText("Check your inbox.")).toBeVisible();
    expect(subscriptionState("status", email)).toBe("pending");

    const confirmation = subscriptionState("transport-confirm", email);
    await page.goto(
        `/subscriptions/confirm#credential=${encodeURIComponent(confirmation)}`,
    );
    await page.getByRole("button", { name: "Confirm subscription" }).click();
    await expect(
        page.getByText("Your subscription is confirmed."),
    ).toBeVisible();
    expect(subscriptionState("status", email)).toBe("active");

    const unsubscribe = subscriptionState("unsubscribe", email);
    await page.goto(
        `/subscriptions/unsubscribe#credential=${encodeURIComponent(unsubscribe)}`,
    );
    await page.getByRole("button", { name: "Unsubscribe" }).click();
    await expect(page.getByText("You have been unsubscribed.")).toBeVisible();
    expect(subscriptionState("status", email)).toBe("unsubscribed");
});

test("real preview endpoint and Next Draft Mode isolate the saved revision", async ({
    browser,
    context,
    page,
}) => {
    const state = JSON.parse(
        readFileSync("/tmp/kirillwynn-cross-stack-state.json", "utf-8"),
    ) as { preview_credential: string };
    await context.addCookies([
        {
            name: "kw_preview_credential",
            value: state.preview_credential,
            domain: "localhost",
            path: "/api/draft",
            httpOnly: true,
            sameSite: "Lax",
        },
    ]);
    await page.goto("/api/draft");
    await expect(page).toHaveURL("/posts/cross-stack-systems");
    await expect(
        page.getByRole("heading", {
            level: 1,
            name: "Draft: cross-stack systems",
        }),
    ).toBeVisible();
    await expect(
        page.getByRole("complementary", { name: "Draft preview" }),
    ).toBeVisible();

    const publicContext = await browser.newContext({
        baseURL: "http://localhost:3200",
    });
    const publicPage = await publicContext.newPage();
    await publicPage.goto("/posts/cross-stack-systems");
    await expect(
        publicPage.getByRole("heading", {
            level: 1,
            name: "Cross-stack systems",
        }),
    ).toBeVisible();
    await expect(
        publicPage.getByText("Draft: cross-stack systems"),
    ).toHaveCount(0);
    await publicContext.close();
});
