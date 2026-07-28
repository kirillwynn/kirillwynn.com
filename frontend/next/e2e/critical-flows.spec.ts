import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

async function reset(page: Page) {
    await page.request.post("http://127.0.0.1:3101/__reset");
}

async function expectAccessible(page: Page) {
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
}

async function login(page: Page, provider: "Google" | "GitHub" = "Google") {
    await page.goto("/login?next=%2Fposts%2Ftesting-secure-systems");
    await page
        .getByRole("button", { name: `Continue with ${provider}` })
        .click();
    await expect(page).toHaveURL(/\/posts\/testing-secure-systems$/);
    await expect(
        page.getByRole("button", { name: "Mock Reader" }),
    ).toBeVisible();
}

test.beforeEach(async ({ page }) => {
    await reset(page);
});

test("anonymous reader, feed search, tags, and pagination", async ({
    page,
}) => {
    await page.goto("/");
    await expect(
        page.getByRole("heading", {
            level: 1,
            name: "Notes from building software and systems.",
        }),
    ).toBeVisible();
    await expect(
        page.getByRole("link", { name: "Testing secure systems" }),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Login" })).toBeVisible();

    await page
        .getByRole("searchbox", { name: "Search posts" })
        .fill("delivery");
    await page.getByRole("button", { name: "Search" }).click();
    await expect(page).toHaveURL("/?q=delivery");
    await expect(
        page.getByRole("link", { name: "Django delivery notes" }),
    ).toBeVisible();

    await page.getByRole("link", { name: "Django 2 posts" }).click();
    await expect(page).toHaveURL("/?q=delivery&tag=django");
    await page.getByRole("link", { name: "Clear search" }).click();
    await expect(page).toHaveURL("/?tag=django");
    await page.getByRole("link", { name: "Clear tag" }).click();
    await page.getByRole("link", { name: "Next →" }).click();
    await expect(page).toHaveURL("/?page=2");
    await expect(
        page.locator("#main-content").getByText("Page 2", { exact: true }),
    ).toBeVisible();
    await expectAccessible(page);
});

test("mock Google and GitHub provider login keep the safe return route", async ({
    page,
}) => {
    await login(page, "Google");
    await page.getByRole("button", { name: "Mock Reader" }).click();
    await page.getByRole("menuitem", { name: "Logout" }).click();
    await expect(
        page.getByRole("link", { name: "Login", exact: true }),
    ).toBeVisible();

    await login(page, "GitHub");
    await expect(page).toHaveURL("/posts/testing-secure-systems");
    await expectAccessible(page);
});

test("comment, thread, reaction, keyboard trap, Escape, and focus restoration", async ({
    page,
}, testInfo) => {
    await login(page);
    const textarea = page.getByPlaceholder("Write a plain-text comment");
    await textarea.fill("A browser-created comment.");
    await page.getByRole("button", { name: "Comment", exact: true }).click();
    await expect(page.getByText("A browser-created comment.")).toBeVisible();

    const postReactions = page
        .getByRole("group", { name: "Reactions" })
        .first();
    await postReactions
        .getByRole("button", { name: "Add 🔥 reaction" })
        .click();
    await expect(
        postReactions.getByRole("button", {
            name: "View 2 participants for 🔥",
        }),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(
        page.getByRole("dialog", { name: "🔥 reaction participants" }),
    ).toBeHidden();

    const root = page.locator('article[data-comment-id="10"]');
    const replyTrigger = root.getByRole("button", { name: "Reply" });
    await replyTrigger.click();
    const dialog = page.getByRole("dialog", {
        name: "Thread for comment by Site Author",
    });
    await expect(dialog).toBeVisible();
    await expect(
        dialog.getByRole("button", { name: "Close thread" }),
    ).toBeFocused();

    if (testInfo.project.name === "mobile-375") {
        const box = await dialog.boundingBox();
        expect(box?.width).toBeGreaterThanOrEqual(371);
        expect(box?.height).toBeGreaterThanOrEqual(808);
    }

    await page.keyboard.press("Shift+Tab");
    await expect
        .poll(() =>
            page.evaluate(() =>
                Boolean(document.activeElement?.closest('[role="dialog"]')),
            ),
        )
        .toBe(true);
    await dialog
        .getByPlaceholder("Write a reply")
        .fill("A nested browser reply.");
    await dialog
        .locator("footer")
        .getByRole("button", { name: "Reply", exact: true })
        .click();
    await expect(dialog.getByText("A nested browser reply.")).toBeVisible();
    await expectAccessible(page);
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(replyTrigger).toBeFocused();
});

test("subscription confirm and unsubscribe mutate only after explicit actions", async ({
    page,
}) => {
    await page.goto("/");
    await page
        .getByRole("textbox", { name: "Email address" })
        .fill("reader@example.test");
    await page.getByRole("button", { name: "Subscribe" }).click();
    await expect(page.getByText("Check your inbox.")).toBeVisible();

    await page.goto("/subscriptions/confirm#credential=e2e-confirm");
    await expect(page).not.toHaveURL(/credential=/);
    await page.getByRole("button", { name: "Confirm subscription" }).click();
    await expect(
        page.getByText("Your subscription is confirmed."),
    ).toBeVisible();

    await page.goto("/subscriptions/unsubscribe#credential=e2e-unsubscribe");
    await page.getByRole("button", { name: "Unsubscribe" }).click();
    await expect(page.getByText("You have been unsubscribed.")).toBeVisible();
    await expectAccessible(page);
});

test("Draft Mode revision remains isolated from a separate public context", async ({
    browser,
    context,
    page,
}) => {
    await context.addCookies([
        {
            name: "kw_preview_credential",
            value: "e2e-preview",
            domain: "localhost",
            path: "/api/draft",
            httpOnly: true,
            sameSite: "Lax",
        },
    ]);
    await page.goto("/api/draft");
    await expect(page).toHaveURL("/posts/testing-secure-systems");
    await expect(
        page.getByRole("heading", {
            level: 1,
            name: "Draft: testing secure systems",
        }),
    ).toBeVisible();
    await expect(
        page.getByRole("complementary", { name: "Draft preview" }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: "Comments" })).toHaveCount(
        0,
    );

    const publicContext = await browser.newContext({
        baseURL: "http://localhost:3100",
        viewport: page.viewportSize() ?? { width: 1440, height: 900 },
    });
    const publicPage = await publicContext.newPage();
    await publicPage.goto("/posts/testing-secure-systems");
    await expect(
        publicPage.getByRole("heading", {
            level: 1,
            name: "Testing secure systems",
        }),
    ).toBeVisible();
    await expect(
        publicPage.getByText("Draft: testing secure systems"),
    ).toHaveCount(0);
    await publicContext.close();
    await expectAccessible(page);
});
