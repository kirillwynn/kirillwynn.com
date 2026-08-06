import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";

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
    body_sha256: string;
    block_ids: string[];
    block_types: string[];
    decision: string;
    publication_outbox: number;
    deliveries: number;
    expire_at: string | null;
    go_live_at: string | null;
    latest_revision_excerpt: string | null;
    live: boolean;
    original_published_at: string | null;
    revision_count: number;
};

type CrossStackState = {
    all_blocks_post_id: number;
    all_blocks_post_slug: string;
};

function readCrossStackState(): CrossStackState {
    return JSON.parse(
        readFileSync("/tmp/kirillwynn-cross-stack-state.json", "utf-8"),
    ) as CrossStackState;
}

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

    const fixture = readCrossStackState();
    await page.goto(
        `${cmsOrigin}/cms/pages/${String(fixture.all_blocks_post_id)}/edit/`,
    );
    await expect(page.locator("html")).toHaveClass(/w-theme-dark/);
    await expect(
        page.locator('[data-editorial-surface="writing"]'),
    ).toBeVisible();
    await expectNoHorizontalOverflow(page);
    const editorViolations = await new AxeBuilder({ page })
        .include(".editorial-writing-tab")
        .analyze();
    expect(editorViolations.violations).toEqual([]);
});

test("Stage 19B preserves all blocks and keeps native Draftail controls independent", async ({
    page,
}) => {
    const fixture = readCrossStackState();
    const initialState = readCmsState(fixture.all_blocks_post_slug);
    const pageErrors: Error[] = [];
    page.on("pageerror", (error) => pageErrors.push(error));
    await page.emulateMedia({
        colorScheme: "light",
        reducedMotion: "reduce",
    });
    await loginCms(page);
    await page.goto(
        `${cmsOrigin}/cms/pages/${String(fixture.all_blocks_post_id)}/edit/`,
    );

    const writingSurface = page.locator('[data-editorial-surface="writing"]');
    const bodyPanel = page.locator('[data-editorial-field="body"]');
    const topLevelBlocks = bodyPanel.locator(
        "[data-streamfield-stream-container] > [data-streamfield-child]",
    );
    const topLevelTypes = await topLevelBlocks
        .locator(":scope > input[name$='-type']")
        .evaluateAll((inputs) =>
            inputs.map((input) => (input as HTMLInputElement).value),
        );
    expect(topLevelTypes).toEqual([
        "rich_text",
        "heading",
        "image",
        "gallery",
        "quote",
        "bulleted_list",
        "numbered_list",
        "checklist",
        "inline_code",
        "code_block",
        "table",
        "horizontal_divider",
        "link",
    ]);
    await expect(topLevelBlocks).toHaveCount(13);
    await expect(writingSurface).toHaveCSS("max-width", "896px");

    const addBlock = bodyPanel.locator("button.c-sf-add-button").first();
    await addBlock.click();
    for (const group of [
        "Text",
        "Media",
        "Lists",
        "Code / Data",
        "Structure",
    ]) {
        await expect(page.getByText(group, { exact: true })).toBeVisible();
    }
    for (const block of [
        "Rich text",
        "Heading",
        "Image",
        "Gallery",
        "Quote",
        "Bulleted list",
        "Numbered list",
        "Checklist",
        "Inline code",
        "Code block",
        "Table",
        "Horizontal divider",
        "Link",
    ]) {
        await expect(
            page
                .getByRole("listbox")
                .getByRole("option", { name: new RegExp(`^${block}`) }),
        ).toBeVisible();
    }
    await page.keyboard.press("Escape");
    await expect(addBlock).toBeFocused();
    await expect(topLevelBlocks).toHaveCount(13);

    await page.getByRole("button", { name: "Save draft" }).click();
    await expect
        .poll(() => readCmsState(fixture.all_blocks_post_slug))
        .toMatchObject({
            body_sha256: initialState.body_sha256,
            block_ids: initialState.block_ids,
            block_types: initialState.block_types,
            live: false,
            publication_outbox: 0,
            deliveries: 0,
            revision_count: initialState.revision_count + 1,
        });

    await page.getByRole("button", { name: "Toggle preview" }).click();
    await page
        .getByLabel("Preview mode")
        .selectOption({ label: "Backend fallback" });
    const preview = page.frameLocator("#w-preview-iframe");
    await expect(
        preview.getByRole("heading", { name: "All content blocks" }),
    ).toBeVisible();
    await expect(preview.getByText("Writing stays primary.")).toBeVisible();
    await page.getByRole("button", { name: "Toggle preview" }).click();

    const imageBlock = topLevelBlocks.nth(2);
    await imageBlock.getByRole("button", { name: "Actions" }).click();
    await imageBlock.getByRole("button", { name: "Change image" }).click();
    const imageDialog = page.getByRole("dialog");
    await expect(imageDialog).toBeVisible();
    await expect(
        imageDialog.getByRole("tab", { name: "Search" }),
    ).toBeVisible();
    await expect(
        imageDialog.getByRole("tab", { name: "Upload" }),
    ).toBeVisible();
    await imageDialog.focus();
    await imageDialog.press("Escape");
    await expect(imageDialog).toBeHidden();

    const firstBlock = topLevelBlocks.first();
    const firstEditor = firstBlock.locator('[contenteditable="true"]');
    await firstEditor.click();
    await firstEditor.press("Home");
    await firstEditor.press("Shift+ArrowRight");
    const pinToolbar = page.getByRole("button", { name: "Pin toolbar" });
    await expect(pinToolbar).toBeVisible();
    await pinToolbar.click();
    await expect(
        firstBlock.getByRole("toolbar").getByRole("button", { name: /Bold/ }),
    ).toBeVisible();
    await expect(
        firstBlock.getByRole("toolbar").getByRole("button", { name: /Italic/ }),
    ).toBeVisible();
    await expect(
        firstBlock.getByRole("toolbar").getByRole("button", { name: /Link/ }),
    ).toBeVisible();
    await expect(
        firstBlock
            .getByRole("toolbar")
            .getByRole("button", { name: /Add a comment/ }),
    ).toBeVisible();
    const boldButton = firstBlock
        .getByRole("toolbar")
        .getByRole("button", { name: /Bold/ });
    const italicButton = firstBlock
        .getByRole("toolbar")
        .getByRole("button", { name: /Italic/ });
    await firstEditor.click();
    await firstEditor.press("End");
    await firstEditor.press("ControlOrMeta+B");
    await expect(boldButton).toHaveClass(/Draftail-ToolbarButton--active/);
    await firstEditor.press("ControlOrMeta+B");
    await expect(boldButton).not.toHaveClass(/Draftail-ToolbarButton--active/);
    await firstEditor.press("ControlOrMeta+I");
    await expect(italicButton).toHaveClass(/Draftail-ToolbarButton--active/);
    await firstEditor.press("ControlOrMeta+I");
    await expect(italicButton).not.toHaveClass(
        /Draftail-ToolbarButton--active/,
    );

    await firstEditor.press("Home");
    await firstEditor.press("Shift+ArrowRight");
    await firstEditor.press("ControlOrMeta+K");
    const linkDialog = page.getByRole("dialog");
    await expect(linkDialog).toBeVisible();
    await expect(
        linkDialog.getByRole("link", { name: "External link" }),
    ).toBeVisible();
    const linkSearch = linkDialog.getByRole("textbox", { name: "Search term" });
    await linkSearch.click();
    await linkSearch.press("Escape");
    await expect(linkDialog).toBeHidden();

    await firstBlock.locator('[data-streamfield-action="DUPLICATE"]').click();
    await expect(
        bodyPanel.locator("[data-draftail-editor-wrapper]"),
    ).toHaveCount(2);
    await expect(bodyPanel.locator(".Draftail-Toolbar--pin")).toHaveCount(2);
    const richBlocks = bodyPanel
        .locator("[data-streamfield-child]")
        .filter({ has: page.locator("[data-draftail-editor-wrapper]") });
    await expect(richBlocks).toHaveCount(2);
    const richEditors = richBlocks.locator('[contenteditable="true"]');
    await richEditors.nth(1).click();
    await expect(richBlocks.nth(1).locator(".Draftail-Toolbar--pin")).toHaveCSS(
        "opacity",
        "1",
    );
    await expect(richBlocks.nth(0).locator(".Draftail-Toolbar--pin")).toHaveCSS(
        "opacity",
        "0.62",
    );

    await richBlocks
        .nth(0)
        .locator('[data-streamfield-action="MOVE_DOWN"]')
        .click();
    await expect(bodyPanel.locator(".Draftail-Toolbar--pin")).toHaveCount(2);
    const reorderedRichBlocks = bodyPanel
        .locator("[data-streamfield-child]")
        .filter({ has: page.locator("[data-draftail-editor-wrapper]") });
    await reorderedRichBlocks
        .nth(1)
        .locator('[contenteditable="true"]')
        .click();
    const activeRichBlock = bodyPanel
        .locator("[data-streamfield-child]:focus-within")
        .filter({ has: page.locator("[data-draftail-editor-wrapper]") });
    await expect(activeRichBlock).toHaveCount(1);
    await activeRichBlock.locator('[data-streamfield-action="DELETE"]').click();
    await expect(
        bodyPanel.locator("[data-draftail-editor-wrapper]:visible"),
    ).toHaveCount(1);
    await expect(
        bodyPanel.locator(".Draftail-Toolbar--pin:visible"),
    ).toHaveCount(1);
    await expect(
        bodyPanel.locator(
            "[data-streamfield-child]:focus-within [data-draftail-editor-wrapper]",
        ),
    ).toHaveCount(0);

    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(
        bodyPanel.locator("[data-draftail-editor-wrapper]"),
    ).toHaveCount(1);
    await expect(bodyPanel.locator(".Draftail-Toolbar--pin")).toHaveCount(1);

    for (const viewport of [
        { width: 768, height: 1024 },
        { width: 1024, height: 768 },
        { width: 1440, height: 900 },
        { width: 1920, height: 1080 },
    ]) {
        await page.setViewportSize(viewport);
        await expectNoHorizontalOverflow(page);
        await expect(page.locator('input[name="title"]')).toBeVisible();
        await expect(bodyPanel.locator(".Draftail-Toolbar--pin")).toBeVisible();
    }

    await page.evaluate(() => {
        document.documentElement.style.zoom = "2";
    });
    await expectNoHorizontalOverflow(page);
    await page.evaluate(() => {
        document.documentElement.style.zoom = "";
    });

    const violations = await new AxeBuilder({ page })
        .include(".editorial-writing-tab")
        .analyze();
    expect(violations.violations).toEqual([]);
    expect(pageErrors).toEqual([]);
});

test("Stage 19B schedules future publication and expiry through Wagtail", async ({
    page,
}) => {
    const fixture = readCrossStackState();
    const initialState = readCmsState(fixture.all_blocks_post_slug);
    await loginCms(page);
    await page.goto(
        `${cmsOrigin}/cms/pages/${String(fixture.all_blocks_post_id)}/edit/`,
    );

    await page.getByRole("button", { name: "Toggle status" }).click();
    await page.getByRole("button", { name: "Set schedule" }).click();
    const scheduleDialog = page.getByRole("dialog", {
        name: "Set publishing schedule",
    });
    await scheduleDialog
        .getByRole("textbox", { name: "Go live date/time" })
        .fill("2030-08-07 10:00");
    const expiryField = scheduleDialog.getByRole("textbox", {
        name: "Expiry date/time",
    });
    await expiryField.fill("2030-08-08 10:00");
    const saveSchedule = scheduleDialog.getByRole("button", {
        name: "Save schedule",
    });
    await expiryField.press("Tab");
    await expect(saveSchedule).toBeFocused();
    await saveSchedule.press("Enter");

    await expect(page.getByText(/Once scheduled:/)).toBeVisible();
    await page.getByRole("button", { name: "More actions" }).click();
    await page
        .getByRole("button", { name: "Schedule to publish", exact: true })
        .click();
    await expect(page.getByRole("status")).toContainText(
        "has been scheduled for publishing",
    );

    await expect
        .poll(() => readCmsState(fixture.all_blocks_post_slug))
        .toMatchObject({
            decision: "pending",
            publication_outbox: 0,
            deliveries: 0,
            live: false,
            revision_count: initialState.revision_count + 2,
        });
    const scheduledState = readCmsState(fixture.all_blocks_post_slug);
    expect(scheduledState.go_live_at).toContain("2030-08-07T10:00:00");
    expect(scheduledState.expire_at).toContain("2030-08-08T10:00:00");
});

test("Stage 19B keeps invalid blocks visible and focuses the first error", async ({
    page,
}) => {
    await loginCms(page);
    await page
        .locator(".editorial-home")
        .getByRole("link", { name: "New post" })
        .click();
    const title = page.locator('input[name="title"]');
    const bodyPanel = page.locator('[data-editorial-field="body"]');

    await page.getByRole("button", { name: "Save draft" }).click();

    await expect(title).toHaveAttribute("aria-invalid", "true");
    await expect(title).toBeFocused();
    await expect(bodyPanel).toBeVisible();

    await title.fill("Stage 19B invalid block QA");
    await page
        .locator('input[name="excerpt"]')
        .fill(
            "The invalid link must remain visible and receive accessible errors.",
        );
    await bodyPanel.locator("button.c-sf-add-button").first().click();
    await page
        .getByRole("listbox")
        .getByRole("option", { name: /^Link/ })
        .click();
    const linkBlock = bodyPanel.locator("[data-streamfield-child]").first();
    await linkBlock.getByLabel("Text*").fill("Missing destination");
    await page.getByRole("button", { name: "Save draft" }).click();

    await expect(linkBlock).toBeVisible();
    await expect(
        linkBlock.getByRole("button", { name: "Toggle section" }),
    ).toHaveAttribute("aria-expanded", "true");
    const linkErrors = linkBlock.locator('[data-field-errors][role="alert"]');
    await expect(linkErrors.first()).not.toBeEmpty();
    const invalidLinkControl = linkBlock
        .locator('[aria-invalid="true"]')
        .first();
    await expect(invalidLinkControl).toBeVisible();
    await expect(invalidLinkControl).toBeFocused();
    await expectNoHorizontalOverflow(page);
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
        { width: 1024, height: 768 },
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

    const publishedState = readCmsState(postSlug);
    const originalExcerpt =
        "A controlled archive created by cross-stack browser QA.";
    await page.getByRole("tab", { name: "Write" }).click();
    await page
        .locator('input[name="excerpt"]')
        .fill(
            "A later draft that will be rolled back through Wagtail history.",
        );
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect
        .poll(() => readCmsState(postSlug))
        .toMatchObject({
            decision: "suppressed",
            publication_outbox: 0,
            deliveries: 0,
            latest_revision_excerpt:
                "A later draft that will be rolled back through Wagtail history.",
            live: true,
            original_published_at: publishedState.original_published_at,
            revision_count: publishedState.revision_count + 1,
        });

    await page.getByRole("link", { name: "History", exact: true }).click();
    const priorDraftRow = page
        .getByRole("row")
        .filter({ hasText: "Draft saved" })
        .filter({ hasNotText: "Current draft" })
        .first();
    await priorDraftRow.getByRole("button", { name: "Actions" }).click();
    await priorDraftRow
        .getByRole("link", { name: "Review this version" })
        .click();
    await expect(
        page
            .getByRole("status")
            .filter({ hasText: "You are viewing a previous version" }),
    ).toBeVisible();
    await expect(page.locator('input[name="excerpt"]')).toHaveValue(
        originalExcerpt,
    );
    await page.getByRole("button", { name: "Replace current draft" }).click();
    await expect(
        page
            .getByRole("status")
            .filter({ hasText: "has been replaced with version" }),
    ).toBeVisible();
    await expect(page.locator('input[name="excerpt"]')).toHaveValue(
        originalExcerpt,
    );
    await expect
        .poll(() => readCmsState(postSlug))
        .toMatchObject({
            decision: "suppressed",
            publication_outbox: 0,
            deliveries: 0,
            latest_revision_excerpt: originalExcerpt,
            live: true,
            original_published_at: publishedState.original_published_at,
            revision_count: publishedState.revision_count + 2,
        });
    expect(pageErrors).toEqual([]);
});
