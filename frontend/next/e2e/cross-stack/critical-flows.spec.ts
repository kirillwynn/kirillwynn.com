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
    user?: {
        nickname: string;
        email_verified: boolean;
        profile_complete: boolean;
        has_usable_password: boolean;
    } | null;
    providers: {
        google: { connected: boolean };
        github: { connected: boolean };
    };
};

type IdentityState = {
    id: number;
    nickname: string;
    email_verified: boolean;
    profile_complete: boolean;
    has_usable_password: boolean;
    social_accounts: string[];
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

function authState(
    action: "verification-credential" | "reset-credential",
    email: string,
): string;
function authState(action: "status", email: string): IdentityState;
function authState(
    action: "verification-credential" | "reset-credential" | "status",
    email: string,
): string | IdentityState {
    const result = execFileSync(
        ".venv/bin/python",
        ["tests/e2e/auth_state.py", action, email],
        {
            cwd: backend,
            encoding: "utf-8",
            env: djangoEnvironment,
        },
    ).trim();
    return action === "status" ? (JSON.parse(result) as IdentityState) : result;
}

async function login(page: Page, provider: "Google" | "GitHub" = "Google") {
    await page.goto("/login?next=%2Fposts%2Fcross-stack-systems");
    await page
        .getByRole("button", { name: `Continue with ${provider}` })
        .click();
    await page.waitForURL(/\/(?:account\/profile|posts\/cross-stack-systems)/);
    if (new URL(page.url()).pathname === "/account/profile") {
        await page.getByLabel("Public nickname").fill("Cross Stack Reader");
        await page.getByRole("button", { name: "Finish profile" }).click();
    }
    await expect(page).toHaveURL(/\/posts\/cross-stack-systems$/);
    await expect(page.getByRole("button", { name: /reader/i })).toBeVisible();
}

test("real batch reaction endpoint hydrates the cached Feed with one private read", async ({
    page,
}) => {
    const batchRequests: string[] = [];
    page.on("request", (request) => {
        const url = new URL(request.url());
        if (url.pathname === "/api/v1/reactions/posts/") {
            batchRequests.push(request.url());
        }
    });

    await page.goto("/");
    const seedEntry = page.locator(".feed-entry", {
        has: page.getByRole("link", {
            name: "Cross-stack systems",
            exact: true,
        }),
    });
    const feedReactions = seedEntry.getByRole("group", { name: "Reactions" });
    await expect(seedEntry.locator("time")).toHaveAttribute(
        "datetime",
        "2015-04-03T12:00:00Z",
    );
    await expect(
        feedReactions.getByRole("button", {
            name: "Add Clapping reaction",
        }),
    ).toHaveAttribute("aria-pressed", "false");
    await expect(
        feedReactions.getByRole("button", {
            name: "View 1 participant for Clapping",
        }),
    ).toBeVisible();
    expect(batchRequests).toHaveLength(1);
    await expect(
        page.getByRole("button", { name: "Choose reaction" }),
    ).toHaveCount(0);
});

test("real allauth provider callbacks create and persist a Django database session", async ({
    page,
}) => {
    await login(page, "Google");
    const firstSession = await page.request.get("/api/me/");
    expect(firstSession.ok()).toBe(true);
    const firstSessionPayload = (await firstSession.json()) as SessionResponse;
    expect(firstSessionPayload.authenticated).toBe(true);
    expect(firstSessionPayload.user?.profile_complete).toBe(true);

    await page.goto("/account");
    await page.getByRole("link", { name: "Set password" }).click();
    await page
        .getByLabel("New password", { exact: true })
        .fill("Cross-stack OAuth password 42!");
    await page
        .getByLabel("Confirm new password")
        .fill("Cross-stack OAuth password 42!");
    await page.getByRole("button", { name: "Set password" }).click();
    await expect(
        page.getByText("Password set.", { exact: false }),
    ).toBeVisible();

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
    expect(authState("status", "reader@example.test")).toMatchObject({
        nickname: "Cross Stack Reader",
        email_verified: true,
        profile_complete: true,
        has_usable_password: true,
        social_accounts: ["github", "google"],
    });
});

test("real local signup and password login keep one canonical nickname identity", async ({
    page,
}, testInfo) => {
    test.slow();
    const email = `local-stage17-${String(testInfo.retry)}@example.test`;
    const firstPassword = "Cross-stack local password 42!";
    const changedPassword = "Cross-stack changed password 84!";
    const resetPassword = "Cross-stack reset password 126!";
    const leakedRequests: string[] = [];
    page.on("request", (request) => leakedRequests.push(request.url()));
    await page.goto("/signup?next=%2Fposts%2Fcross-stack-systems");
    await page.getByLabel("Email").fill(email.toLocaleUpperCase());
    await page.getByLabel("Public nickname").fill("Local Cross Stack Reader");
    await page.getByLabel("Password", { exact: true }).fill(firstPassword);
    await page.getByLabel("Confirm password").fill(firstPassword);
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(
        page.getByText(/If the address can be registered/),
    ).toBeVisible();

    const verification = authState("verification-credential", email);
    await page.goto(
        `/account/verify-email#credential=${encodeURIComponent(verification)}`,
    );
    await expect(page).toHaveURL(/\/account\/verify-email$/);
    await expect(page.getByText(/Email verified/)).toBeVisible();
    expect(page.url()).not.toContain("#");
    expect(await page.content()).not.toContain(verification);

    await page.goto("/login?next=%2Fposts%2Fcross-stack-systems");
    await page.getByLabel("Email").fill(email.toLocaleUpperCase());
    await page.getByLabel("Password").fill(firstPassword);
    await page.getByRole("button", { name: "Login with email" }).click();
    await expect(page).toHaveURL(/\/posts\/cross-stack-systems$/);
    await expect(
        page.getByRole("button", { name: "Local Cross Stack Reader" }),
    ).toBeVisible();
    await expect(
        page
            .locator("#main-content article")
            .first()
            .locator(":scope > header")
            .getByText("by Site Author", { exact: true }),
    ).toBeVisible();

    const me = (await (
        await page.request.get("/api/me/")
    ).json()) as SessionResponse;
    expect(me).toMatchObject({
        authenticated: true,
        user: {
            nickname: "Local Cross Stack Reader",
            email_verified: true,
            profile_complete: true,
            has_usable_password: true,
        },
    });
    await page.reload();
    await expect(
        page.getByRole("button", { name: "Local Cross Stack Reader" }),
    ).toBeVisible();

    await page.goto("/account");
    await page.getByRole("link", { name: "Change password" }).click();
    await page.getByLabel("Current password").fill(firstPassword);
    await page
        .getByLabel("New password", { exact: true })
        .fill(changedPassword);
    await page.getByLabel("Confirm new password").fill(changedPassword);
    await page.getByRole("button", { name: "Change password" }).click();
    await expect(
        page.getByText("Password changed.", { exact: false }),
    ).toBeVisible();

    await page.goto("/account");
    await page.getByRole("button", { name: "Logout" }).click();
    await page.goto("/account/password/reset");
    await page.getByLabel("Email").fill(email);
    await page.getByRole("button", { name: "Send reset email" }).click();
    await expect(page.getByText(/If the account is eligible/)).toBeVisible();

    const reset = authState("reset-credential", email);
    await page.goto(
        `/account/password/reset/confirm#credential=${encodeURIComponent(reset)}`,
    );
    await expect(page).toHaveURL(/\/account\/password\/reset\/confirm$/);
    await page.getByLabel("New password", { exact: true }).fill(resetPassword);
    await page.getByLabel("Confirm new password").fill(resetPassword);
    await page.getByRole("button", { name: "Reset password" }).click();
    await expect(page.getByText(/Password reset/)).toBeVisible();
    expect(page.url()).not.toContain("#");
    expect(await page.content()).not.toContain(reset);

    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(resetPassword);
    await page.getByRole("button", { name: "Login with email" }).click();
    await expect(page).toHaveURL("/");
    await expect(
        page.getByRole("button", { name: "Local Cross Stack Reader" }),
    ).toBeVisible();
    expect(
        leakedRequests.some(
            (url) => url.includes(verification) || url.includes(reset),
        ),
    ).toBe(false);
    expect(
        await page.evaluate(
            (secrets) =>
                [localStorage, sessionStorage].every((storage) =>
                    Array.from({ length: storage.length }, (_, index) =>
                        storage.getItem(storage.key(index) ?? ""),
                    ).every(
                        (value) =>
                            value === null ||
                            secrets.every((secret) => !value.includes(secret)),
                    ),
                ),
            [
                firstPassword,
                changedPassword,
                resetPassword,
                verification,
                reset,
            ],
        ),
    ).toBe(true);
    expect(authState("status", email)).toMatchObject({
        nickname: "Local Cross Stack Reader",
        email_verified: true,
        profile_complete: true,
        has_usable_password: true,
        social_accounts: [],
    });
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
    const replyInput = dialog.getByRole("textbox", {
        name: "Reply to thread",
    });
    await replyInput.fill(reply);
    await dialog
        .locator("footer")
        .getByRole("button", { name: "Reply", exact: true })
        .click();
    await expect(
        dialog.locator("article").getByText(reply, { exact: true }),
    ).toBeVisible();
    await expect(replyInput).toHaveValue("");
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await root.getByRole("button", { name: "Reply" }).click();
    const reopenedDialog = page.getByRole("dialog", {
        name: "Thread for comment by Site Author",
    });
    await expect(
        reopenedDialog.locator("article").getByText(reply, { exact: true }),
    ).toBeVisible();
    await expect(
        reopenedDialog.getByRole("textbox", { name: "Reply to thread" }),
    ).toHaveValue("");
    await page.keyboard.press("Escape");

    const postReactions = page
        .getByRole("group", { name: "Reactions" })
        .first();
    const clap = postReactions.getByRole("button", {
        name: /(?:Add|Remove) Clapping reaction/,
    });
    const before = await clap.getAttribute("aria-pressed");
    await clap.click();
    await expect(clap).toHaveAttribute(
        "aria-pressed",
        before === "true" ? "false" : "true",
    );
    await page.reload();
    await expect(
        page
            .getByRole("group", { name: "Reactions" })
            .first()
            .getByRole("button", {
                name: /(?:Add|Remove) Clapping reaction/,
            }),
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
    await expect(
        publicPage.locator("article header time").first(),
    ).toHaveAttribute("datetime", "2015-04-03T12:00:00Z");
    await expect(
        publicPage.locator('meta[property="article:published_time"]'),
    ).toHaveAttribute("content", "2015-04-03T12:00:00Z");
    await publicContext.close();
});
