import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";

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

async function expectVisuallyHidden(locator: Locator) {
    await expect(locator).toHaveClass(/sr-only/);
    await expect
        .poll(() =>
            locator.evaluate((element) => {
                const style = getComputedStyle(element);
                return (
                    style.position === "absolute" &&
                    Number.parseFloat(style.width) <= 1 &&
                    Number.parseFloat(style.height) <= 1 &&
                    style.overflow === "hidden"
                );
            }),
        )
        .toBe(true);
}

async function expectSharedContentBounds(page: Page) {
    const viewport = page.viewportSize();
    expect(viewport).not.toBeNull();
    if (!viewport) {
        return;
    }
    const selectors = [
        ".site-header__inner",
        "#main-content",
        ".site-footer__inner",
    ];
    const boxes = [];
    for (const selector of selectors) {
        const box = await page.locator(selector).boundingBox();
        expect(box).not.toBeNull();
        if (!box) {
            continue;
        }
        expect(box.x).toBeGreaterThanOrEqual(15.5);
        expect(viewport.width - box.x - box.width).toBeGreaterThanOrEqual(15.5);
        boxes.push(box);
    }
    expect(boxes).toHaveLength(selectors.length);
    for (const box of boxes.slice(1)) {
        expect(Math.abs(box.x - boxes[0].x)).toBeLessThanOrEqual(0.5);
        expect(
            Math.abs(box.x + box.width - (boxes[0].x + boxes[0].width)),
        ).toBeLessThanOrEqual(0.5);
    }
}

async function expectBridgeContent(page: Page) {
    const heading = page.getByRole("heading", { level: 1, name: "Bridge" });
    await expectVisuallyHidden(heading);
    await expect(
        page.getByText(
            "Profiles and places where you can find me elsewhere on the internet.",
            { exact: true },
        ),
    ).toHaveCount(0);
    const links = page.locator(".bridge-link");
    await expect(links).toHaveCount(8);
    const names = [
        "GitHub",
        "LeetCode",
        "Reddit",
        "Telegram",
        "Instagram",
        "X",
        "Steam",
        "Pulse",
    ];
    for (const [index, name] of names.entries()) {
        const link = links.nth(index);
        await expect(link).toHaveAttribute(
            "aria-label",
            `${name} (opens in a new tab)`,
        );
        await expect(link).toHaveText("");
        await expect(link).toBeVisible();
        await expect(link).toHaveAttribute("target", "_blank");
        await expect(link).toHaveAttribute("rel", "noopener noreferrer");
        const linkBox = await link.boundingBox();
        const imageBox = await link.locator("img").boundingBox();
        expect(linkBox).not.toBeNull();
        expect(imageBox).not.toBeNull();
        if (linkBox && imageBox) {
            expect(linkBox.width).toBeGreaterThanOrEqual(44);
            expect(linkBox.height).toBeGreaterThanOrEqual(44);
            expect(
                Math.abs(
                    linkBox.x +
                        linkBox.width / 2 -
                        (imageBox.x + imageBox.width / 2),
                ),
            ).toBeLessThanOrEqual(0.5);
            expect(
                Math.abs(
                    linkBox.y +
                        linkBox.height / 2 -
                        (imageBox.y + imageBox.height / 2),
                ),
            ).toBeLessThanOrEqual(0.5);
        }
        expect(
            await link.locator("img").evaluate((image) => {
                const element = image as HTMLImageElement;
                return element.complete && element.naturalWidth > 0;
            }),
        ).toBe(true);
    }
    const snapshot = await page.locator("#main-content").ariaSnapshot();
    expect(snapshot).toContain('- heading "Bridge" [level=1]');
    for (const name of names) {
        const accessibleName = `${name} (opens in a new tab)`;
        expect(snapshot.split(`link "${accessibleName}"`)).toHaveLength(2);
    }

    await links.first().focus();
    for (let index = 0; index < names.length; index += 1) {
        await expect(links.nth(index)).toBeFocused();
        await expect(links.nth(index)).toHaveText("");
        if (index < names.length - 1) {
            await page.keyboard.press("Tab");
        }
    }
    await links.last().hover();
    await expect(links.last()).toHaveText("");
}

async function expectTeamFooter(page: Page) {
    const footer = page.getByRole("contentinfo");

    await expect(footer.getByText(/©|Kirill Wynn/)).toHaveCount(0);
    await expect(
        footer.getByText(
            "Writing about software, systems, and the work between.",
            { exact: true },
        ),
    ).toHaveCount(0);
    await expect(
        footer.getByText("Current Team", { exact: true }),
    ).toBeVisible();
    await expect(footer.getByText("Yandex", { exact: true })).toBeVisible();
    await expect(
        footer.getByText("Previous Team", { exact: true }),
    ).toBeVisible();
    await expect(footer.getByText("Deeplay", { exact: true })).toBeVisible();
    await expect(footer.locator("dl")).toHaveAttribute(
        "aria-label",
        "Team history",
    );
    await expect(footer).toHaveText(
        /^\s*Current Team\s*Yandex\s*Previous Team\s*Deeplay\s*$/,
    );
    await expect(footer.locator("dl")).toHaveCount(1);
    await expect(footer.locator("dt")).toHaveCount(2);
    await expect(footer.locator("dd")).toHaveCount(2);
    await expect(footer.locator("p, a")).toHaveCount(0);
    const rows = footer.locator(".site-team-context > div");
    await expect(rows).toHaveCount(2);
    const inner = await footer.locator(".site-footer__inner").boundingBox();
    const current = await rows.nth(0).boundingBox();
    const previous = await rows.nth(1).boundingBox();
    expect(inner).not.toBeNull();
    expect(current).not.toBeNull();
    expect(previous).not.toBeNull();
    if (inner && current && previous) {
        expect(current.y + current.height).toBeLessThanOrEqual(previous.y);
        const innerCenter = inner.x + inner.width / 2;
        expect(
            Math.abs(current.x + current.width / 2 - innerCenter),
        ).toBeLessThanOrEqual(0.75);
        expect(
            Math.abs(previous.x + previous.width / 2 - innerCenter),
        ).toBeLessThanOrEqual(0.75);
    }
    await expect
        .poll(() =>
            rows
                .first()
                .locator("dt")
                .evaluate((term) => getComputedStyle(term, "::after").content),
        )
        .toBe('" —"');
}

async function expectSlackReactionGeometry(pill: Locator) {
    await expect(pill).toBeVisible();
    const geometry = await pill.evaluate((element) => {
        const box = element.getBoundingClientRect();
        const visible = getComputedStyle(element, "::before");
        const asset = element.querySelector(".reaction-pill__asset");
        const count = element.querySelector(".reaction-pill__count");
        return {
            targetHeight: box.height,
            visibleHeight: Number.parseFloat(visible.height),
            assetSize: asset
                ? Number.parseFloat(getComputedStyle(asset).width)
                : 0,
            countSize: count
                ? Number.parseFloat(getComputedStyle(count).fontSize)
                : 0,
        };
    });
    expect(geometry.targetHeight).toBeGreaterThanOrEqual(44);
    expect(geometry.visibleHeight).toBeGreaterThanOrEqual(28);
    expect(geometry.visibleHeight).toBeLessThanOrEqual(32);
    expect(geometry.assetSize).toBeGreaterThanOrEqual(15);
    expect(geometry.assetSize).toBeLessThanOrEqual(16);
    expect(geometry.countSize).toBeGreaterThanOrEqual(12);
    expect(geometry.countSize).toBeLessThanOrEqual(13);

    const targets = pill.getByRole("button");
    await expect(targets).toHaveCount(2);
    const first = await targets.nth(0).boundingBox();
    const second = await targets.nth(1).boundingBox();
    expect(first?.height).toBeGreaterThanOrEqual(44);
    expect(second?.height).toBeGreaterThanOrEqual(44);
    if (first && second) {
        expect(first.x + first.width).toBeLessThanOrEqual(second.x + 0.5);
    }
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
    await expectVisuallyHidden(
        page.getByRole("heading", { level: 1, name: "Feed" }),
    );
    await expect(
        page.getByRole("link", { name: "Testing secure systems" }),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Login" })).toBeVisible({
        timeout: 15_000,
    });

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
    const search = page.getByRole("searchbox", { name: "Search posts" });
    await search.fill("");
    await expect(page).toHaveURL("/?tag=django");
    await page.getByRole("link", { name: "All", exact: true }).click();
    await page.getByRole("link", { name: "Next →" }).click();
    await expect(page).toHaveURL("/?page=2");
    await expect(
        page.locator("#main-content").getByText("Page 2", { exact: true }),
    ).toBeVisible();

    await search.pressSequentially("delivery", { delay: 25 });
    await expect(page).toHaveURL("/?q=delivery");
    await expect(search).toHaveValue("delivery");
    await expect(page.getByText("Clear search", { exact: true })).toHaveCount(
        0,
    );
    await expect(page.getByText("Clear filters", { exact: true })).toHaveCount(
        0,
    );
    await expect(page.getByText("Clear tag", { exact: true })).toHaveCount(0);

    await page.getByRole("link", { name: "Bridge", exact: true }).click();
    await page.goBack();
    await expect(page).toHaveURL("/?q=delivery");
    await expect(
        page.getByRole("searchbox", { name: "Search posts" }),
    ).toHaveValue("delivery");
    await page.goForward();
    await expect(page).toHaveURL("/bridge");
    await page.goBack();
    await expect(page).toHaveURL("/?q=delivery");

    const compositionInput = page.getByRole("searchbox", {
        name: "Search posts",
    });
    await compositionInput.evaluate((element) => {
        const input = element as HTMLInputElement;
        input.dispatchEvent(
            new CompositionEvent("compositionstart", { bubbles: true }),
        );
        const descriptor = Object.getOwnPropertyDescriptor(
            HTMLInputElement.prototype,
            "value",
        );
        descriptor?.set?.call(input, "日本");
        input.dispatchEvent(
            new InputEvent("input", {
                bubbles: true,
                data: "日本",
                inputType: "insertCompositionText",
                isComposing: true,
            }),
        );
    });
    await page.waitForTimeout(400);
    await expect(page).toHaveURL("/?q=delivery");
    await compositionInput.evaluate((element) => {
        element.dispatchEvent(
            new CompositionEvent("compositionend", {
                bubbles: true,
                data: "日本",
            }),
        );
    });
    await expect(page).toHaveURL("/?q=%E6%97%A5%E6%9C%AC");
    await expect(
        page.getByRole("searchbox", { name: "Search posts" }),
    ).toHaveValue("日本");
    await expectAccessible(page);
});

test("Search and Bridge use perceptible contourless focus in both themes", async ({
    page,
}) => {
    const styles = (locator: Locator) =>
        locator.evaluate((element) => {
            const style = getComputedStyle(element);
            return {
                backgroundColor: style.backgroundColor,
                borderColor: style.borderColor,
                borderStyle: style.borderStyle,
                borderWidth: style.borderWidth,
                boxShadow: style.boxShadow,
                filter: style.filter,
                outlineStyle: style.outlineStyle,
                outlineWidth: style.outlineWidth,
                transform: style.transform,
            };
        });

    for (const colorScheme of ["light", "dark"] as const) {
        await page.emulateMedia({
            colorScheme,
            reducedMotion: "no-preference",
        });
        await page.goto("/");
        const search = page.getByRole("searchbox", { name: "Search posts" });
        const searchRest = await styles(search);
        await page.keyboard.press("Tab");
        await search.focus();
        const searchFocus = await styles(search);
        expect(searchFocus.borderColor).toBe(searchRest.borderColor);
        expect(searchFocus.borderStyle).toBe(searchRest.borderStyle);
        expect(searchFocus.borderWidth).toBe(searchRest.borderWidth);
        expect(searchFocus.outlineStyle).toBe("none");
        expect(searchFocus.outlineWidth).toBe("0px");
        expect(searchFocus.boxShadow).toBe("none");
        expect(searchFocus.backgroundColor).not.toBe(
            searchRest.backgroundColor,
        );
        await search.fill("delivery");
        const searchTyping = await styles(search);
        expect(searchTyping.borderColor).toBe(searchRest.borderColor);
        expect(searchTyping.outlineWidth).toBe("0px");
        expect(searchTyping.boxShadow).toBe("none");

        await page.goto("/bridge");
        const tile = page.locator(".bridge-link").first();
        const tileRest = await styles(tile);
        await tile.hover();
        const tileHover = await styles(tile);
        expect(tileHover.borderColor).toBe(tileRest.borderColor);
        expect(tileHover.borderStyle).toBe(tileRest.borderStyle);
        expect(tileHover.borderWidth).toBe(tileRest.borderWidth);
        expect(tileHover.outlineWidth).toBe("0px");
        expect(tileHover.boxShadow).toBe("none");
        expect(tileHover.transform).not.toBe("none");

        const box = await tile.boundingBox();
        expect(box).not.toBeNull();
        if (box) {
            await page.mouse.move(
                box.x + box.width / 2,
                box.y + box.height / 2,
            );
            await page.mouse.down();
            const tileActive = await styles(tile);
            expect(tileActive.borderColor).toBe(tileRest.borderColor);
            expect(tileActive.outlineWidth).toBe("0px");
            expect(tileActive.boxShadow).toBe("none");
            await page.mouse.up();
        }

        await page.keyboard.press("Tab");
        await tile.focus();
        const tileFocus = await styles(tile);
        expect(tileFocus.borderColor).toBe(tileRest.borderColor);
        expect(tileFocus.borderStyle).toBe(tileRest.borderStyle);
        expect(tileFocus.borderWidth).toBe(tileRest.borderWidth);
        expect(tileFocus.outlineStyle).toBe("none");
        expect(tileFocus.outlineWidth).toBe("0px");
        expect(tileFocus.boxShadow).toBe("none");
        expect(
            tileFocus.backgroundColor !== tileRest.backgroundColor ||
                tileFocus.filter !== tileRest.filter ||
                tileFocus.transform !== tileRest.transform,
        ).toBe(true);
    }

    await page.emulateMedia({
        colorScheme: "light",
        reducedMotion: "reduce",
    });
    await page.goto("/bridge");
    const reducedTile = page.locator(".bridge-link").first();
    const reducedRest = await styles(reducedTile);
    await reducedTile.hover();
    const reducedHover = await styles(reducedTile);
    expect(reducedHover.transform).toBe("none");
    expect(reducedHover.borderColor).toBe(reducedRest.borderColor);
    expect(reducedHover.outlineWidth).toBe("0px");
    expect(
        reducedHover.backgroundColor !== reducedRest.backgroundColor ||
            reducedHover.filter !== reducedRest.filter,
    ).toBe(true);
});

test("Feed hydrates existing reactions once without card-level requests or picker UI", async ({
    page,
}) => {
    const reactionRequests: string[] = [];
    page.on("request", (request) => {
        const path = new URL(request.url()).pathname;
        if (path.includes("/reactions/")) {
            reactionRequests.push(`${request.method()} ${path}`);
        }
    });

    await page.goto("/?tag=django");
    await expect(page.locator(".feed-entry")).toHaveCount(2);
    const feedReactions = page
        .locator(".feed-entry")
        .first()
        .getByRole("group", { name: "Reactions" });
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
    await expectSlackReactionGeometry(
        feedReactions.locator(".reaction-pill").first(),
    );
    expect(
        reactionRequests.filter(
            (request) => request === "GET /api/v1/reactions/posts/",
        ),
    ).toHaveLength(1);
    expect(
        reactionRequests.filter((request) =>
            /^GET \/api\/v1\/posts\/.+\/reactions\/$/.test(request),
        ),
    ).toHaveLength(0);
    await expect(
        page.getByRole("button", { name: "Choose reaction" }),
    ).toHaveCount(0);
    await expect(
        page.locator(".feed-entry .reaction-picker-trigger"),
    ).toHaveCount(0);

    const count = feedReactions.getByRole("button", {
        name: "View 1 participant for Clapping",
    });
    const participantRequests = () =>
        reactionRequests.filter((request) =>
            request.includes("/participants/"),
        );
    await count.hover();
    await count.focus();
    await page.waitForTimeout(50);
    expect(participantRequests()).toHaveLength(0);
    await expect(
        page.getByRole("dialog", {
            name: "Clapping reaction participants",
        }),
    ).toHaveCount(0);

    await count.press("Enter");
    await expect(
        page.getByRole("dialog", {
            name: "Clapping reaction participants",
        }),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(count).toBeFocused();
    await count.press("Space");
    await expect(
        page.getByRole("dialog", {
            name: "Clapping reaction participants",
        }),
    ).toBeVisible();
    await page
        .getByRole("button", { name: "Close reaction participants" })
        .click();
    await expect(count).toBeFocused();
    await count.click();
    await expect(
        page.getByRole("dialog", {
            name: "Clapping reaction participants",
        }),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    expect(participantRequests()).toHaveLength(3);

    await page.route(/\/api\/v1\/reactions\/posts\/\?ids=/, async (route) => {
        await route.fulfill({
            status: 503,
            contentType: "application/json",
            body: JSON.stringify({ detail: "Unavailable" }),
        });
    });
    await page.goto("/?tag=django");
    await expect(page.locator(".feed-entry")).toHaveCount(2);
    await expect(page.locator(".feed-entry-reactions")).toHaveCount(0);
    await expect(page.locator('.feed-entry [role="alert"]')).toHaveCount(0);
    await expectNoHorizontalOverflow(page);
    await expectAccessible(page);
});

test("reaction surfaces expose only aggregates and one lazy picker trigger", async ({
    page,
}) => {
    const requests: string[] = [];
    page.on("request", (request) => {
        requests.push(new URL(request.url()).pathname);
    });

    await page.goto("/posts/testing-secure-systems");
    const postGroup = page.getByRole("group", { name: "Reactions" }).first();
    const postTrigger = postGroup.getByRole("button", {
        name: "Choose reaction",
    });
    await expect(postGroup.locator(".reaction-pill")).toHaveCount(1);
    await expect(postTrigger).toHaveCount(1);
    await expect(postTrigger).toHaveAttribute("aria-expanded", "false");

    const comment = page.locator('article[data-comment-id="10"]').first();
    const commentGroup = comment.getByRole("group", { name: "Reactions" });
    await expect(commentGroup.locator(".reaction-pill")).toHaveCount(0);
    await expect(
        commentGroup.getByRole("button", { name: "Choose reaction" }),
    ).toHaveCount(1);
    await expect(
        page.getByRole("button", { name: /^React with / }),
    ).toHaveCount(0);
    expect(
        requests.filter((path) => path === "/api/v1/reactions/config/"),
    ).toHaveLength(0);
    expect(
        requests.filter((path) => path === "/api/v1/reactions/catalog/"),
    ).toHaveLength(0);
    expect(requests.some((path) => path.includes("/pepehmm/"))).toBe(false);
    expect(requests.some((path) => path.includes("/pepelove/"))).toBe(false);

    const triggerGeometry = await postTrigger.evaluate((element) => {
        const target = element.getBoundingClientRect();
        const visual = getComputedStyle(element, "::before");
        return {
            targetHeight: target.height,
            targetWidth: target.width,
            visualHeight: visual.height,
            visualWidth: visual.width,
        };
    });
    expect(triggerGeometry).toEqual({
        targetHeight: 44,
        targetWidth: 44,
        visualHeight: "30px",
        visualWidth: "30px",
    });
    expect(
        await postGroup.evaluate((group) => {
            const pill = group.querySelector(".reaction-pill");
            const trigger = group.querySelector(".reaction-picker-trigger");
            if (!pill || !trigger) {
                return true;
            }
            const pillBox = pill.getBoundingClientRect();
            const triggerBox = trigger.getBoundingClientRect();
            return !(
                pillBox.right <= triggerBox.left ||
                triggerBox.right <= pillBox.left ||
                pillBox.bottom <= triggerBox.top ||
                triggerBox.bottom <= pillBox.top
            );
        }),
    ).toBe(false);

    await postTrigger.press("Enter");
    const picker = page.getByRole("dialog", { name: "Choose a reaction" });
    await expect(picker).toBeVisible();
    await expect(postTrigger).toHaveAttribute("aria-expanded", "true");
    await expect(
        picker.getByRole("button", { name: "React with Clapping" }),
    ).toBeVisible();
    expect(
        requests.filter((path) => path === "/api/v1/reactions/catalog/"),
    ).toHaveLength(1);
    expect(
        requests.filter((path) => path === "/api/v1/reactions/config/"),
    ).toHaveLength(0);
    await page.keyboard.press("Escape");
    await expect(picker).toBeHidden();
    await expect(postTrigger).toBeFocused();

    await postTrigger.press("Space");
    await expect(picker).toBeVisible();
    await picker.getByRole("button", { name: "Close reaction picker" }).click();
    await expect(postTrigger).toBeFocused();

    await postTrigger.click();
    await expect(picker).toBeVisible();
    await postTrigger.click();
    await expect(picker).toBeHidden();
    await expect(postTrigger).toHaveAttribute("aria-expanded", "false");

    const threadTrigger = comment
        .getByRole("button", { name: /^(Reply|View thread)$/ })
        .first();
    await threadTrigger.click();
    const thread = page.getByRole("dialog", {
        name: "Thread for comment by Site Author",
    });
    await expect(thread).toBeVisible();
    await expect(
        thread.getByRole("button", { name: "Choose reaction" }),
    ).toHaveCount(2);
    await expect(
        thread.getByRole("button", { name: /^React with / }),
    ).toHaveCount(0);
    await expectNoHorizontalOverflow(page);
    await expectAccessible(page);
    await page.keyboard.press("Escape");
    await expect(thread).toBeHidden();
});

test("picker selection retains focus across an optimistic aggregate insertion", async ({
    page,
}) => {
    await login(page);

    const postGroup = page.getByRole("group", { name: "Reactions" }).first();
    const trigger = postGroup.getByRole("button", {
        name: "Choose reaction",
    });
    await expect(trigger).toHaveCount(1);

    let releaseToggle: (() => void) | undefined;
    await page.route(
        /\/api\/v1\/posts\/testing-secure-systems\/reactions\/toggle\/$/,
        async (route) => {
            await new Promise<void>((resolve) => {
                releaseToggle = resolve;
            });
            await route.fulfill({
                status: 400,
                contentType: "application/json",
                body: JSON.stringify({ detail: "Controlled rollback" }),
            });
        },
    );

    await trigger.click();
    const picker = page.getByRole("dialog", { name: "Choose a reaction" });
    await expect(picker).toBeVisible();
    await picker
        .getByRole("button", { name: "React with Sending love" })
        .click();

    const optimistic = postGroup.getByRole("button", {
        name: "Remove Sending love reaction",
    });
    await expect(optimistic).toBeVisible();
    await expect(trigger).toBeDisabled();
    expect(releaseToggle).toBeDefined();
    releaseToggle?.();

    await expect(optimistic).toHaveCount(0);
    await expect(trigger).toBeEnabled();
    await expect(trigger).toBeFocused();
});

test("responsive shell, right header group, skip link, and universal team footer", async ({
    page,
}, testInfo) => {
    for (const path of [
        "/",
        "/?q=definitely-no-footer-results",
        "/?q=force-upstream-error",
        "/?page=0",
        "/posts/testing-secure-systems",
        "/login",
        "/account",
        "/subscriptions/confirm",
        "/subscriptions/unsubscribe",
        "/missing-footer-route",
    ]) {
        await page.goto(path);
        await expectTeamFooter(page);
        await expect(
            page.locator(".site-header").getByText("kirillwynn.com", {
                exact: true,
            }),
        ).toHaveCount(0);
        await expectSharedContentBounds(page);
        await expectNoHorizontalOverflow(page);
        const header = await page.locator(".site-header__inner").boundingBox();
        const controls = await page
            .locator(".site-header__controls")
            .boundingBox();
        expect(header).not.toBeNull();
        expect(controls).not.toBeNull();
        if (header && controls) {
            expect(
                Math.abs(
                    controls.x + controls.width - (header.x + header.width),
                ),
            ).toBeLessThanOrEqual(0.5);
        }
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
    for (const text of ["Current Team", "Yandex", "Previous Team", "Deeplay"]) {
        await expect(main.getByText(text, { exact: true })).toHaveCount(0);
    }

    await expectBridgeContent(page);
    await expectTeamFooter(page);
    await expectSharedContentBounds(page);
    await expectNoHorizontalOverflow(page);
    await expectAccessible(page);

    if (testInfo.project.name === "mobile-375") {
        await page.setViewportSize({ width: 320, height: 812 });
        await page.goto("/");
        await expectTeamFooter(page);
        await expectSharedContentBounds(page);
        await expectNoHorizontalOverflow(page);
        const headerBounds = await page
            .locator(".site-header__inner")
            .boundingBox();
        expect(headerBounds).not.toBeNull();
        for (const control of [
            page.getByRole("link", { name: "Feed", exact: true }),
            page.getByRole("link", { name: "Bridge", exact: true }),
            page.locator(".theme-toggle"),
            page.getByRole("link", { name: "Login", exact: true }),
        ]) {
            const box = await control.boundingBox();
            expect(box?.height).toBeGreaterThanOrEqual(44);
            if (box && headerBounds) {
                expect(box.x).toBeGreaterThanOrEqual(headerBounds.x);
                expect(box.x + box.width).toBeLessThanOrEqual(
                    headerBounds.x + headerBounds.width + 0.5,
                );
            }
        }
    }
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
    for (let index = 0; index < 4; index += 1) {
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
        if (path === "/bridge") {
            await expectBridgeContent(page);
        }
        await expectTeamFooter(page);
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
    await expectTeamFooter(lightPage);
    await lightPage.goto("/bridge");
    await expectBridgeContent(lightPage);
    await expectTeamFooter(lightPage);
    await expectNoHorizontalOverflow(lightPage);
    await expectAccessible(lightPage);
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
    await expectSlackReactionGeometry(
        postReactions.locator(".reaction-pill").first(),
    );
    await postReactions
        .getByRole("button", { name: "Add Clapping reaction" })
        .click();
    await expect(
        postReactions.getByRole("button", {
            name: "View 2 participants for Clapping",
        }),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(
        page.getByRole("dialog", {
            name: "Clapping reaction participants",
        }),
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
    await expectSharedContentBounds(page);
    await expectNoHorizontalOverflow(page);
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
    await expectSharedContentBounds(page);
    await expectNoHorizontalOverflow(page);
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
    await expectSharedContentBounds(page);
    await expectNoHorizontalOverflow(page);
    await page.getByRole("link", { name: "Exit preview" }).click();
    await expect(page).toHaveURL("/");
    await expect(
        page.getByRole("complementary", { name: "Draft preview" }),
    ).toHaveCount(0);

    await expectAccessible(page);
});
