import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { THEME_STORAGE_KEY } from "../../lib/theme";

async function reset(page: Page) {
    await page.request.post("http://127.0.0.1:3101/__reset");
}

async function expectAccessible(page: Page) {
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
}

async function expectNoHorizontalOverflow(page: Page) {
    await expect
        .poll(() =>
            page.evaluate(
                () =>
                    document.documentElement.scrollWidth <=
                    document.documentElement.clientWidth,
            ),
        )
        .toBe(true);
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
            name: "Feed",
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

test("responsive shell, skip link, and route-specific Bridge footer", async ({
    page,
}) => {
    for (const path of [
        "/",
        "/posts/testing-secure-systems",
        "/login",
        "/account",
    ]) {
        await page.goto(path);
        await expect(
            page
                .getByRole("contentinfo")
                .getByText("Current Team", { exact: true }),
        ).toHaveCount(0);
        await expectNoHorizontalOverflow(page);
    }

    await page.goto("/");
    await expect(
        page.getByRole("link", { name: "Feed", exact: true }),
    ).toHaveAttribute("aria-current", "page");
    await page.keyboard.press("Tab");
    const skipLink = page.getByRole("link", { name: "Skip to content" });
    await expect(skipLink).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.locator("#main-content")).toBeFocused();

    await page.goto("/bridge");
    await expect(
        page.getByRole("link", { name: "Bridge", exact: true }),
    ).toHaveAttribute("aria-current", "page");
    const main = page.locator("#main-content");
    await expect(main.getByText("Current Team", { exact: true })).toHaveCount(
        0,
    );
    await expect(main.getByText("Previous Team", { exact: true })).toHaveCount(
        0,
    );

    const footer = page.getByRole("contentinfo");
    await expect(
        footer.getByText("Current Team", { exact: true }),
    ).toBeVisible();
    await expect(footer.getByText("Yandex", { exact: true })).toBeVisible();
    await expect(
        footer.getByText("Previous Team", { exact: true }),
    ).toBeVisible();
    await expect(footer.getByText("Deeplay", { exact: true })).toBeVisible();
    await expectNoHorizontalOverflow(page);
    await expectAccessible(page);
});

test("theme follows the system, persists, and remains beside account", async ({
    browser,
    page,
}) => {
    const hydrationFailures: string[] = [];
    page.on("console", (message) => {
        if (
            ["error", "warning"].includes(message.type()) &&
            /hydration|did not match|server rendered html/i.test(message.text())
        ) {
            hydrationFailures.push(message.text());
        }
    });
    page.on("pageerror", (error) => {
        if (
            /hydration|did not match|server rendered html/i.test(error.message)
        ) {
            hydrationFailures.push(error.message);
        }
    });

    const response = await page.request.get("/");
    const markup = await response.text();
    expect(markup.indexOf('id="theme-init"')).toBeGreaterThan(0);
    expect(markup.indexOf('id="theme-init"')).toBeLessThan(
        markup.indexOf("<body"),
    );

    await page.emulateMedia({
        colorScheme: "dark",
        reducedMotion: "reduce",
    });
    await page.goto("/");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    expect(
        await page.evaluate(
            (storageKey) => window.localStorage.getItem(storageKey),
            THEME_STORAGE_KEY,
        ),
    ).toBeNull();

    let toggle = page.getByRole("button", { name: "Switch to light theme" });
    await expect(toggle).toBeVisible();
    const target = await toggle.boundingBox();
    expect(target?.width).toBeGreaterThanOrEqual(44);
    expect(target?.height).toBeGreaterThanOrEqual(44);
    expect(
        await toggle.evaluate((button) =>
            getComputedStyle(button)
                .transitionDuration.split(",")
                .every((duration) => Number.parseFloat(duration) <= 0.000_01),
        ),
    ).toBe(true);
    expect(
        await toggle.evaluate((button) =>
            button.nextElementSibling?.classList.contains("account-slot"),
        ),
    ).toBe(true);
    await expect(
        page.getByRole("link", { name: "Feed", exact: true }),
    ).toHaveCSS("white-space", "nowrap");

    await page.evaluate(() => {
        (document.activeElement as HTMLElement | null)?.blur();
    });
    for (let index = 0; index < 5; index += 1) {
        await page.keyboard.press("Tab");
    }
    await expect(toggle).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await expect(
        page.getByRole("button", { name: "Switch to dark theme" }),
    ).toBeVisible();
    expect(
        await page.evaluate(
            (storageKey) => window.localStorage.getItem(storageKey),
            THEME_STORAGE_KEY,
        ),
    ).toBe("light");

    await page.emulateMedia({
        colorScheme: "dark",
        reducedMotion: "reduce",
    });
    await page.goto("/bridge");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

    await login(page);
    toggle = page.getByRole("button", { name: "Switch to dark theme" });
    await expect(toggle).toBeVisible();
    expect(
        await toggle.evaluate((button) =>
            button.nextElementSibling?.classList.contains("account-slot"),
        ),
    ).toBe(true);
    await toggle.click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

    for (const path of [
        "/",
        "/?q=definitely-no-theme-results",
        "/?page=0",
        "/bridge",
        "/posts/testing-secure-systems",
        "/login",
        "/account",
        "/subscriptions/confirm",
        "/subscriptions/unsubscribe",
        "/missing-theme-route",
    ]) {
        await page.goto(path);
        await expect(page.locator("html")).toHaveAttribute(
            "data-theme",
            "dark",
        );
        await expect(
            page.getByRole("button", { name: "Switch to light theme" }),
        ).toBeVisible();
        await expectNoHorizontalOverflow(page);
        await expectAccessible(page);
    }

    const lightContext = await browser.newContext({
        baseURL: "http://localhost:3100",
        colorScheme: "light",
        reducedMotion: "reduce",
        viewport: page.viewportSize() ?? { width: 1440, height: 900 },
    });
    const lightPage = await lightContext.newPage();
    await lightPage.goto("/");
    await expect(lightPage.locator("html")).toHaveAttribute(
        "data-theme",
        "light",
    );
    expect(
        await lightPage.evaluate(
            (storageKey) => window.localStorage.getItem(storageKey),
            THEME_STORAGE_KEY,
        ),
    ).toBeNull();
    await lightContext.close();

    expect(hydrationFailures).toEqual([]);
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

    await page.goto("/");
    await expect(
        page.getByRole("complementary", { name: "Draft preview" }),
    ).toBeVisible();
    await expect(
        page.getByRole("heading", { name: "Get new posts by email" }),
    ).toHaveCount(0);

    await page.goto("/posts/unavailable-preview");
    await expect(
        page.getByRole("heading", { level: 1, name: "Page not found" }),
    ).toBeVisible();
    await expect(
        page.getByRole("complementary", { name: "Draft preview" }),
    ).toBeVisible();
    await page.getByRole("link", { name: "Exit preview" }).click();
    await expect(page).toHaveURL("/");
    await expect(
        page.getByRole("complementary", { name: "Draft preview" }),
    ).toHaveCount(0);

    await expectAccessible(page);
});
