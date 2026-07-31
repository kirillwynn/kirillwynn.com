import { execFileSync } from "node:child_process";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const backend = "../../backend/django";
const cmsOrigin = "http://localhost:3201";
const djangoEnvironment = {
    ...process.env,
    DJANGO_SETTINGS_MODULE: "config.settings.cross_stack",
    DJANGO_TEST_DATABASE: "/tmp/kirillwynn-cross-stack.sqlite3",
};

type CmsState = {
    decision: string;
    publication_outbox: number;
    deliveries: number;
    live: boolean;
    original_published_at: string | null;
};

function readCmsState(slug: string): CmsState {
    return JSON.parse(
        execFileSync(".venv/bin/python", ["tests/e2e/cms_state.py", slug], {
            cwd: backend,
            encoding: "utf-8",
            env: djangoEnvironment,
        }),
    ) as CmsState;
}

async function loginCms(
    page: Page,
    username = "cms-owner",
    password = "cms-stage15-test-only",
) {
    await page.goto(`${cmsOrigin}/cms/login/?next=%2Fcms%2F`);
    await page.getByLabel("Username").fill(username);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(`${cmsOrigin}/cms/`);
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

test("editorial dashboard follows Wagtail's explicit dark preference", async ({
    page,
}) => {
    await loginCms(page, "cms-dark-owner");

    await expect(page.locator("html")).toHaveClass(/w-theme-dark/);
    await expect(page.locator(".editorial-home")).toBeVisible();
    await expectNoHorizontalOverflow(page);
    const colors = await page.locator(".editorial-home").evaluate((element) => {
        const style = getComputedStyle(element);
        return {
            background: style.backgroundColor,
            foreground: style.color,
        };
    });
    expect(colors.background).not.toBe("rgba(0, 0, 0, 0)");
    expect(colors.foreground).not.toBe(colors.background);
    const violations = await new AxeBuilder({ page })
        .include(".editorial-home")
        .analyze();
    expect(violations.violations).toEqual([]);
});

test("Wagtail writing-first editor creates a suppressed archive through normal revisions", async ({
    page,
}, testInfo) => {
    const retrySuffix =
        testInfo.retry === 0 ? "" : ` retry ${String(testInfo.retry)}`;
    const postTitle = `CMS archive QA${retrySuffix}`;
    const postSlug = `cms-archive-qa${retrySuffix.replaceAll(" ", "-")}`;
    const pageErrors: Error[] = [];
    page.on("pageerror", (error) => pageErrors.push(error));
    await page.emulateMedia({
        colorScheme: "light",
        reducedMotion: "reduce",
    });
    await loginCms(page);

    const dashboard = page.locator(".editorial-home");
    const newPost = dashboard.getByRole("link", { name: "New post" });
    await expect(dashboard.getByText("Start with the post")).toBeVisible();
    await expect(newPost).toBeVisible();
    await newPost.focus();
    await expect(newPost).toBeFocused();
    await expect
        .poll(() =>
            newPost.evaluate(
                (element) => getComputedStyle(element).outlineStyle,
            ),
        )
        .not.toBe("none");

    for (const viewport of [
        { width: 768, height: 1024 },
        { width: 1440, height: 900 },
        { width: 1920, height: 1080 },
    ]) {
        await page.setViewportSize(viewport);
        await expectNoHorizontalOverflow(page);
    }
    const dashboardAxe = await new AxeBuilder({ page })
        .include(".editorial-home")
        .analyze();
    expect(dashboardAxe.violations).toEqual([]);

    await newPost.click();
    await expect(page).toHaveURL(
        /\/cms\/pages\/add\/blog\/blogpostpage\/\d+\/$/,
    );
    const title = page.locator('input[name="title"]');
    const excerpt = page.locator('input[name="excerpt"]');
    const bodyPanel = page.locator('[data-editorial-field="body"]');
    await expect(title).toBeVisible();
    await expect(excerpt).toBeVisible();
    await expect(bodyPanel).toBeVisible();
    await title.fill(postTitle);
    await excerpt.fill(
        "A controlled archive created by cross-stack browser QA.",
    );

    await bodyPanel.locator("button.c-sf-add-button").first().click();
    for (const group of [
        "Text",
        "Media",
        "Lists",
        "Code / Data",
        "Structure",
    ]) {
        await expect(page.getByText(group, { exact: true })).toBeVisible();
    }
    await page.getByText("Rich text", { exact: true }).last().click();
    const richText = bodyPanel.locator('[contenteditable="true"]').last();
    await richText.click();
    await richText.pressSequentially("Controlled Stage 15 archive body.");
    await expect(richText).toContainText("Controlled Stage 15 archive body.");
    await expect(page.locator('input[name="body-0-value"]')).toHaveValue(
        /Controlled Stage 15 archive body/,
    );

    await expect(
        page.getByRole("button", { name: "Toggle preview" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page).toHaveURL(/\/cms\/pages\/\d+\/edit\/$/);
    await expect(page.getByText(/created|saved/i).first()).toBeVisible();
    await expect(
        page
            .locator('[data-editorial-field="body"] [contenteditable="true"]')
            .last(),
    ).toContainText("Controlled Stage 15 archive body.");
    await page.getByRole("button", { name: "Toggle preview" }).click();
    await expect(page.locator("#w-preview-iframe")).toBeVisible();
    await expect(
        page
            .frameLocator("#w-preview-iframe")
            .getByRole("heading", { name: postTitle }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Toggle preview" }).click();

    await page.getByRole("tab", { name: "Publish" }).click();
    await expect(page.getByLabel("Original publication date")).toBeVisible();
    await page
        .locator('input[name="original_published_at"]')
        .fill("2014-03-02 10:00");
    const notify = page.getByLabel("Notify subscribers on first publication");
    await expect(notify).toBeChecked();
    await notify.uncheck();
    await expect(
        page.getByText(/Pending — the choice will be locked/),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Toggle status" }).click();
    await expect(
        page.getByText("No publishing schedule set", { exact: true }),
    ).toBeVisible();
    await page.getByText("Set schedule", { exact: true }).click();
    const scheduleDialog = page.getByRole("dialog");
    await expect(scheduleDialog).toBeVisible();
    await expect(scheduleDialog).toContainText(/Go live/i);
    await expect(scheduleDialog).toContainText(/Expiry/i);
    await scheduleDialog.getByRole("button", { name: "Close dialog" }).click();

    const editorAxe = await new AxeBuilder({ page })
        .include('[data-editorial-field="title"]')
        .include('[data-editorial-field="excerpt"]')
        .include('[data-editorial-field="body"]')
        .analyze();
    expect(editorAxe.violations).toEqual([]);
    for (const viewport of [
        { width: 768, height: 1024 },
        { width: 1440, height: 900 },
        { width: 1920, height: 1080 },
    ]) {
        await page.setViewportSize(viewport);
        await expectNoHorizontalOverflow(page);
    }

    await page.getByRole("button", { name: "More actions" }).click();
    await page.getByRole("button", { name: "Publish", exact: true }).click();
    await expect(page.getByRole("status")).toContainText(
        `Page '${postTitle}' has been published.`,
    );

    await expect
        .poll(() => readCmsState(postSlug), { timeout: 15_000 })
        .toMatchObject({
            decision: "suppressed",
            publication_outbox: 0,
            deliveries: 0,
            live: true,
        });
    expect(readCmsState(postSlug).original_published_at).toContain(
        "2014-03-02",
    );

    const detail = await page.request.get(
        `${cmsOrigin}/api/v1/posts/${postSlug}/`,
    );
    expect(detail.ok()).toBe(true);
    const payload = (await detail.json()) as {
        published_at: string;
        original_published_at: string;
        display_published_at: string;
    };
    expect(payload.original_published_at).toBe("2014-03-02T10:00:00Z");
    expect(payload.display_published_at).toBe(payload.original_published_at);
    expect(payload.published_at).not.toBe(payload.display_published_at);

    await page.getByRole("link", { name: "Edit", exact: true }).click();
    await page.getByRole("tab", { name: "Publish" }).click();
    await expect(
        page.getByText(/Suppressed — no publication notification was created/),
    ).toBeVisible();
    await expect(
        page.getByLabel("Notify subscribers on first publication"),
    ).toBeDisabled();
    await expect(page.getByRole("link", { name: /History/ })).toBeVisible();
    expect(pageErrors).toEqual([]);
});
