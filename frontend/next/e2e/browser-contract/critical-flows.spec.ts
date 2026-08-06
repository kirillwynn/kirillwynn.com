import { Buffer } from "node:buffer";
import { randomUUID } from "node:crypto";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";

import { signBody } from "../../lib/revalidation-contract";
import { THEME_STORAGE_KEY } from "../../lib/theme";

const BACKEND_ORIGIN = "http://127.0.0.1:3101";
const REVALIDATION_SECRET = "browser-contract-revalidation-secret-42";

type BackendMetrics = {
    max_concurrent_post_list_requests: number;
    requests: string[];
};

async function reset(page: Page) {
    await page.request.post(`${BACKEND_ORIGIN}/__reset`);
}

async function backendMetrics(page: Page): Promise<BackendMetrics> {
    const response = await page.request.get(`${BACKEND_ORIGIN}/__metrics`);
    expect(response.ok()).toBe(true);
    return (await response.json()) as BackendMetrics;
}

async function changeMockContent(
    page: Page,
    content: { published?: boolean; slug?: string; title?: string },
) {
    const response = await page.request.post(`${BACKEND_ORIGIN}/__content`, {
        data: content,
    });
    expect(response.ok()).toBe(true);
}

async function revalidatePublicContent(
    page: Page,
    event: {
        action: "published" | "updated" | "unpublished" | "expired";
        page_id: number;
        slug: string;
        previous_slug?: string;
    },
) {
    const timestamp = String(Math.floor(Date.now() / 1000));
    const body = JSON.stringify({
        ...event,
        event_id: randomUUID(),
        occurred_at: new Date().toISOString(),
    });
    const response = await page.request.post("/api/revalidate", {
        data: body,
        headers: {
            "Content-Type": "application/json",
            "X-Revalidation-Signature": signBody(
                body,
                timestamp,
                REVALIDATION_SECRET,
            ),
            "X-Revalidation-Timestamp": timestamp,
        },
    });
    expect(response.ok()).toBe(true);
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
    const selectors = [".site-header__inner:visible", "#main-content:visible"];
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
    const footer = await page
        .locator(".site-footer__inner:visible")
        .boundingBox();
    expect(footer).not.toBeNull();
    if (footer) {
        expect(footer.x).toBeGreaterThanOrEqual(15.5);
        expect(viewport.width - footer.x - footer.width).toBeGreaterThanOrEqual(
            15.5,
        );
        expect(footer.width).toBeLessThanOrEqual(544.5);
        expect(
            Math.abs(footer.x + footer.width / 2 - viewport.width / 2),
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
        .toBe('":"');
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
    await page.route(/\/media\/reactions\//, async (route) => {
        await route.fulfill({
            body: Buffer.from(
                "R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==",
                "base64",
            ),
            contentType: "image/gif",
            status: 200,
        });
    });
    await reset(page);
});

test("public list/detail cache is reused and signed invalidation covers publish lifecycle", async ({
    page,
}, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-1440");

    const token = `cache-contract-${randomUUID().slice(0, 8)}`;
    const originalSlug = `${token}-original`;
    const renamedSlug = `${token}-renamed`;
    await changeMockContent(page, {
        slug: originalSlug,
        title: `Cache contract ${token}`,
    });

    const listPath = `/?q=${encodeURIComponent(token)}`;
    const detailPath = `/posts/${originalSlug}`;
    const firstList = await page.request.get(listPath);
    const secondList = await page.request.get(listPath);
    expect(firstList.status()).toBe(200);
    expect(secondList.status()).toBe(200);
    expect(await secondList.text()).toContain(`Cache contract ${token}`);

    const firstDetail = await page.request.get(detailPath);
    const secondDetail = await page.request.get(detailPath);
    expect(firstDetail.status()).toBe(200);
    expect(secondDetail.status()).toBe(200);

    let metrics = await backendMetrics(page);
    expect(
        metrics.requests.filter(
            (request) =>
                request === `GET /api/v1/posts/?q=${encodeURIComponent(token)}`,
        ),
    ).toHaveLength(1);
    expect(
        metrics.requests.filter(
            (request) => request === `GET /api/v1/posts/${originalSlug}/`,
        ),
    ).toHaveLength(1);

    await changeMockContent(page, { title: `Invalidated ${token}` });
    await revalidatePublicContent(page, {
        action: "updated",
        page_id: 1,
        slug: originalSlug,
    });
    await expect
        .poll(async () => (await page.request.get(listPath)).text())
        .toContain(`Invalidated ${token}`);
    await expect
        .poll(async () => (await page.request.get(detailPath)).text())
        .toContain(`Invalidated ${token}`);

    await changeMockContent(page, { slug: renamedSlug });
    await revalidatePublicContent(page, {
        action: "updated",
        page_id: 1,
        previous_slug: originalSlug,
        slug: renamedSlug,
    });
    await expect
        .poll(
            async () =>
                (await page.request.get(`/posts/${renamedSlug}`)).status(),
            { timeout: 10_000 },
        )
        .toBe(200);
    await expect
        .poll(async () => (await page.request.get(detailPath)).text(), {
            timeout: 10_000,
        })
        .toContain("Page not found");

    await changeMockContent(page, { published: false });
    await revalidatePublicContent(page, {
        action: "unpublished",
        page_id: 1,
        slug: renamedSlug,
    });
    await expect
        .poll(
            async () =>
                (await page.request.get(`/posts/${renamedSlug}`)).text(),
            { timeout: 10_000 },
        )
        .toContain("Page not found");

    await changeMockContent(page, {
        published: true,
        slug: "testing-secure-systems",
        title: "Testing secure systems",
    });
    await revalidatePublicContent(page, {
        action: "published",
        page_id: 1,
        previous_slug: renamedSlug,
        slug: "testing-secure-systems",
    });
    await expect
        .poll(
            async () =>
                (
                    await page.request.get("/posts/testing-secure-systems")
                ).status(),
            { timeout: 10_000 },
        )
        .toBe(200);

    await changeMockContent(page, { published: false });
    await revalidatePublicContent(page, {
        action: "expired",
        page_id: 1,
        slug: "testing-secure-systems",
    });
    await expect
        .poll(
            async () =>
                (
                    await page.request.get("/posts/testing-secure-systems")
                ).text(),
            { timeout: 10_000 },
        )
        .toContain("Page not found");

    await changeMockContent(page, { published: true });
    await revalidatePublicContent(page, {
        action: "published",
        page_id: 1,
        slug: "testing-secure-systems",
    });
    await expect
        .poll(
            async () =>
                (
                    await page.request.get("/posts/testing-secure-systems")
                ).status(),
            { timeout: 10_000 },
        )
        .toBe(200);

    metrics = await backendMetrics(page);
    expect(
        metrics.requests.filter(
            (request) =>
                request === `GET /api/v1/posts/?q=${encodeURIComponent(token)}`,
        ).length,
    ).toBeGreaterThanOrEqual(2);
});

test("anonymous infinite Feed, live search, IME, history, and legacy URL normalization", async ({
    page,
}) => {
    const feedRequests: string[] = [];
    const failedFeedRequests: string[] = [];
    page.on("request", (request) => {
        const url = new URL(request.url());
        if (url.pathname === "/api/v1/posts/") {
            feedRequests.push(url.pathname + url.search);
        }
    });
    page.on("requestfailed", (request) => {
        const url = new URL(request.url());
        if (url.pathname === "/api/v1/posts/") {
            failedFeedRequests.push(url.pathname + url.search);
        }
    });

    await page.goto("/?tag=django&page=2&q=delivery");
    await expect(page).toHaveURL("/?q=delivery");
    await expect(
        page.getByRole("link", { name: "Django delivery notes" }),
    ).toBeVisible();
    await expect(page.locator(".feed-tag, .feed-pagination")).toHaveCount(0);
    await expect(page.getByText(/^Page \d+$/)).toHaveCount(0);
    await expect(
        page.getByRole("link", { name: "Subscribe", exact: true }),
    ).toHaveAttribute("href", "/subscriptions/");
    await expect(
        page.getByRole("textbox", { name: "Email address" }),
    ).toHaveCount(0);

    const search = page.getByRole("searchbox", { name: "Search posts" });
    await search.fill("");
    await expect(page).toHaveURL("/");
    await expect
        .poll(async () => {
            await page.evaluate(() => {
                window.scrollTo(0, document.body.scrollHeight);
            });
            return page.locator(".feed-entry").count();
        })
        .toBe(8);
    await expect(page.getByText("Beginning of the archive")).toBeVisible();
    const feedIds = await page
        .locator(".feed-entry h2 a")
        .evaluateAll((links) => links.map((link) => link.getAttribute("href")));
    expect(new Set(feedIds).size).toBe(8);
    const metrics = await backendMetrics(page);
    expect(metrics.max_concurrent_post_list_requests).toBe(1);

    await search.fill("delivery");
    await expect(page).toHaveURL("/?q=delivery");
    await expect(
        page.getByRole("link", { name: "Django delivery notes" }),
    ).toBeVisible();
    await expect(page.locator(".feed-entry")).toHaveCount(1);
    expect(
        feedRequests.filter(
            (request) => request === "/api/v1/posts/?q=delivery",
        ).length,
    ).toBeLessThanOrEqual(1);
    await expect(page.getByText("Clear search", { exact: true })).toHaveCount(
        0,
    );
    await expect(page.getByText("Clear filters", { exact: true })).toHaveCount(
        0,
    );

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
    await expect(compositionInput).toHaveValue("日本");
    await expect
        .poll(async () => {
            const href = await page
                .getByRole("link", { name: "Login", exact: true })
                .getAttribute("href");
            return new URL(
                href ?? "",
                "http://localhost:3100",
            ).searchParams.get("next");
        })
        .toBe("/?q=日本");

    await page.goBack();
    await expect(page).toHaveURL("/?q=delivery");
    await expect(compositionInput).toHaveValue("delivery");
    await page.goForward();
    await expect(page).toHaveURL("/?q=%E6%97%A5%E6%9C%AC");
    await expect(compositionInput).toHaveValue("日本");

    await compositionInput.fill("slow archive");
    await expect
        .poll(
            () =>
                feedRequests.filter(
                    (request) => request === "/api/v1/posts/?q=slow+archive",
                ).length,
        )
        .toBe(1);
    await compositionInput.fill("delivery");
    await expect(page).toHaveURL("/?q=delivery");
    await expect(
        page.getByRole("link", { name: "Django delivery notes" }),
    ).toBeVisible();
    await expect
        .poll(() =>
            failedFeedRequests.includes("/api/v1/posts/?q=slow+archive"),
        )
        .toBe(true);
    await page.waitForTimeout(850);
    await expect(page.getByText("No posts found")).toHaveCount(0);
    await expect(
        page.getByRole("link", { name: "Django delivery notes" }),
    ).toBeVisible();
    await expectAccessible(page);
});

test("manual infinite Feed fallback covers observer, data-saving, reduced-motion, and retry", async ({
    browser,
    page,
}, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-1440");

    const manualCases: Array<{
        prepare: (candidate: Page) => Promise<unknown>;
    }> = [
        {
            prepare: (candidate) =>
                candidate.addInitScript(() => {
                    Reflect.deleteProperty(window, "IntersectionObserver");
                }),
        },
        {
            prepare: (candidate) =>
                candidate.addInitScript(() => {
                    Object.defineProperty(navigator, "connection", {
                        configurable: true,
                        value: { saveData: true },
                    });
                }),
        },
        {
            prepare: (candidate) =>
                candidate.emulateMedia({ reducedMotion: "reduce" }),
        },
    ];

    for (const manualCase of manualCases) {
        const context = await browser.newContext({
            viewport: { height: 900, width: 1440 },
        });
        const candidate = await context.newPage();
        await manualCase.prepare(candidate);
        await candidate.goto("http://localhost:3100/");
        const loadOlder = candidate.locator(".feed-load-more button");
        await expect(loadOlder).toHaveText("Load older posts");
        await candidate.waitForTimeout(350);
        await expect(candidate.locator(".feed-entry")).toHaveCount(1);
        await loadOlder.click();
        await expect(candidate.locator(".feed-entry")).toHaveCount(2);
        await expect(loadOlder).toBeFocused();
        await context.close();
    }

    let failedPageOnce = false;
    await page.route(/\/api\/v1\/posts\/\?page=2$/, async (route) => {
        if (!failedPageOnce) {
            failedPageOnce = true;
            await route.fulfill({
                body: JSON.stringify({ detail: "Temporary Feed failure" }),
                contentType: "application/json",
                status: 503,
            });
            return;
        }
        await route.continue();
    });
    await page.goto("/");
    const retry = page.locator(".feed-load-more button");
    await expect(retry).toHaveText("Try loading older posts again");
    await retry.click();
    await expect(page.locator(".feed-entry")).toHaveCount(2);
    await expect(retry).toBeFocused();
    await expectAccessible(page);
});

test("public client navigation preserves the root shell, auth request, Feed pages, and scroll", async ({
    page,
}, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-1440");
    const documents: string[] = [];
    const meRequests: string[] = [];
    page.on("request", (request) => {
        const path = new URL(request.url()).pathname;
        if (request.resourceType() === "document") {
            documents.push(path);
        }
        if (path === "/api/me/") {
            meRequests.push(path);
        }
    });

    await page.goto("/");
    await expect(
        page.getByRole("link", { name: "Login", exact: true }),
    ).toBeVisible();
    await expect
        .poll(async () => {
            await page.evaluate(() => {
                window.scrollTo(0, document.body.scrollHeight);
            });
            return page.locator(".feed-entry").count();
        })
        .toBe(8);
    await page.evaluate(() => {
        const auditWindow = window as Window & {
            __stage19Shell?: {
                body: HTMLElement | null;
                footer: HTMLElement | null;
                header: HTMLElement | null;
            };
        };
        auditWindow.__stage19Shell = {
            body: document.body,
            footer: document.querySelector(".site-footer"),
            header: document.querySelector(".site-header"),
        };
    });
    const feedScroll = await page.evaluate(() => window.scrollY);
    expect(feedScroll).toBeGreaterThan(0);

    await page
        .getByRole("link", { name: "Bridge", exact: true })
        .evaluate((link: HTMLAnchorElement) => {
            link.click();
        });
    await expect(page).toHaveURL("/bridge");
    await expectBridgeContent(page);
    const bridgeDepartureScroll = Number(
        await page.evaluate(() =>
            window.sessionStorage.getItem("kirillwynn:feed-scroll:"),
        ),
    );
    expect(bridgeDepartureScroll).toBeGreaterThan(0);
    await page.getByRole("link", { name: "Feed", exact: true }).click();
    await expect(page).toHaveURL("/");
    await expect(page.locator(".feed-entry")).toHaveCount(8);
    await expect
        .poll(() =>
            page.evaluate(
                (saved) => Math.abs(window.scrollY - saved),
                bridgeDepartureScroll,
            ),
        )
        .toBeLessThanOrEqual(2);

    const visiblePost = page.getByRole("link", {
        name: "Archive entry 8",
        exact: true,
    });
    await expect(visiblePost).toBeVisible();
    await visiblePost.click();
    await expect(page).toHaveURL("/posts/archive-entry-8");
    await expect(
        page.getByRole("heading", {
            level: 1,
            name: "Archive entry 8",
        }),
    ).toBeVisible();
    const postDepartureScroll = Number(
        await page.evaluate(() =>
            window.sessionStorage.getItem("kirillwynn:feed-scroll:"),
        ),
    );
    expect(postDepartureScroll).toBeGreaterThan(0);
    await page.goBack();
    await expect(page).toHaveURL("/");
    await expect(page.locator(".feed-entry")).toHaveCount(8);
    await expect
        .poll(() =>
            page.evaluate(
                (saved) => Math.abs(window.scrollY - saved),
                postDepartureScroll,
            ),
        )
        .toBeLessThanOrEqual(2);

    expect(documents).toEqual(["/"]);
    expect(meRequests).toEqual(["/api/me/"]);
    expect(
        await page.evaluate(() => {
            const auditWindow = window as Window & {
                __stage19Shell?: {
                    body: HTMLElement | null;
                    footer: HTMLElement | null;
                    header: HTMLElement | null;
                };
            };
            const shell = auditWindow.__stage19Shell;
            if (!shell) {
                return false;
            }
            return (
                shell.body === document.body &&
                shell.footer === document.querySelector(".site-footer") &&
                shell.header === document.querySelector(".site-header")
            );
        }),
    ).toBe(true);
    await expect(
        page.locator('[class*="skeleton"], [aria-label="Loading feed"]'),
    ).toHaveCount(0);
});

test("the safe public Feed link consumes its completed full prefetch", async ({
    page,
}, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-1440");
    let delayLaterFeedRsc = false;
    let feedRscRequests = 0;

    await page.route("**/*", async (route) => {
        const request = route.request();
        const url = new URL(request.url());
        const isFeedRsc = url.pathname === "/" && request.headers().rsc === "1";
        if (isFeedRsc) {
            feedRscRequests += 1;
            if (delayLaterFeedRsc) {
                await new Promise((resolve) => setTimeout(resolve, 2_000));
            }
        }
        await route.continue();
    });

    await page.goto("/bridge");
    await expectBridgeContent(page);
    await expect
        .poll(() => feedRscRequests, { timeout: 10_000 })
        .toBeGreaterThan(0);
    await page.waitForLoadState("networkidle");
    const completedPrefetchRequests = feedRscRequests;
    delayLaterFeedRsc = true;

    const startedAt = Date.now();
    await page.getByRole("link", { name: "Feed", exact: true }).click();
    await expect(page).toHaveURL("/");
    await expect(page.locator(".feed-entry")).not.toHaveCount(0);

    expect(Date.now() - startedAt).toBeLessThan(1_000);
    expect(feedRscRequests).toBe(completedPrefetchRequests);
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
    await page.emulateMedia({ reducedMotion: "reduce" });
    const reactionRequests: string[] = [];
    page.on("request", (request) => {
        const path = new URL(request.url()).pathname;
        if (path.includes("/reactions/")) {
            reactionRequests.push(`${request.method()} ${path}`);
        }
    });

    await page.goto("/");
    await expect(page.locator(".feed-entry")).toHaveCount(1);
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
    await feedReactions.locator(".reaction-pill").first().hover();
    await page.waitForTimeout(50);
    expect(
        reactionRequests.filter((request) =>
            request.endsWith("/animation.gif"),
        ),
    ).toHaveLength(0);
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
    expect(participantRequests()).toHaveLength(1);

    await page.route(/\/api\/v1\/reactions\/posts\/\?ids=/, async (route) => {
        await route.fulfill({
            status: 503,
            contentType: "application/json",
            body: JSON.stringify({ detail: "Unavailable" }),
        });
    });
    await page.goto("/");
    await expect(page.locator(".feed-entry")).toHaveCount(1);
    await expect(page.locator(".feed-entry-reactions")).toHaveCount(0);
    await expect(page.locator('.feed-entry [role="alert"]')).toHaveCount(0);
    await expectNoHorizontalOverflow(page);
    await expectAccessible(page);
});

test("reaction surfaces expose only aggregates and one lazy picker trigger", async ({
    page,
}, testInfo) => {
    const requests: string[] = [];
    const imageRequests: string[] = [];
    let releaseCatalog: (() => void) | undefined;
    const catalogGate = new Promise<void>((resolve) => {
        releaseCatalog = resolve;
    });
    await page.route(/\/api\/v1\/reactions\/catalog\/$/, async (route) => {
        await catalogGate;
        await route.continue();
    });
    await page.route(/\/media\/reactions\//, async (route) => {
        imageRequests.push(new URL(route.request().url()).pathname);
        await route.fulfill({
            body: Buffer.from(
                "R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==",
                "base64",
            ),
            contentType: "image/gif",
            status: 200,
        });
    });
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
    await expect(commentGroup.locator(".reaction-pill")).toHaveCount(1);
    await expectSlackReactionGeometry(commentGroup.locator(".reaction-pill"));
    await expect(
        commentGroup.getByRole("button", { name: "Choose reaction" }),
    ).toHaveCount(1);
    await expect(
        page.getByRole("button", { name: /^React with / }),
    ).toHaveCount(0);
    expect(
        requests.filter((path) => path === "/api/v1/reactions/config/"),
    ).toHaveLength(0);
    expect(requests.some((path) => path.includes("/pepehmm/"))).toBe(false);
    expect(requests.some((path) => path.includes("/pepelove/"))).toBe(false);
    const initialAggregateImageRequestCount = imageRequests.length;
    expect(initialAggregateImageRequestCount).toBeGreaterThan(0);
    expect(
        imageRequests.filter((path) => path.endsWith("/animation.gif")),
    ).toHaveLength(0);
    await postGroup.locator(".reaction-pill").hover();
    await expect
        .poll(
            () =>
                imageRequests.filter((path) => path.endsWith("/animation.gif"))
                    .length,
        )
        .toBe(1);
    const prePickerImageRequestCount = imageRequests.length;

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

    const openedAt = Date.now();
    await postTrigger.press("Enter");
    const picker = page.getByRole("dialog", { name: "Choose a reaction" });
    await expect(picker).toBeVisible();
    expect(Date.now() - openedAt).toBeLessThan(500);
    await expect(postTrigger).toHaveAttribute("aria-expanded", "true");
    await expect(picker.getByText("Loading reactions…")).toBeVisible();
    expect(imageRequests).toHaveLength(prePickerImageRequestCount);
    releaseCatalog?.();
    await expect(
        picker.getByRole("button", { name: "React with Clapping" }),
    ).toBeVisible();
    await expect(
        picker.getByRole("button", { name: /^React with / }),
    ).toHaveCount(228);
    await expect.poll(() => picker.locator("img").count()).toBeGreaterThan(0);
    expect(await picker.locator("img").count()).toBeLessThan(228);
    expect(imageRequests.length - prePickerImageRequestCount).toBeLessThan(228);
    expect(
        requests.filter((path) => path === "/api/v1/reactions/catalog/"),
    ).toHaveLength(1);
    expect(
        requests.filter((path) => path === "/api/v1/reactions/config/"),
    ).toHaveLength(0);

    const pickerSearch = picker.getByRole("searchbox", {
        name: "Search reaction names",
    });
    const focusedSearchStyle = await pickerSearch.evaluate((element) => {
        const style = getComputedStyle(element);
        return {
            borderColor: style.borderColor,
            boxShadow: style.boxShadow,
            outlineColor: style.outlineColor,
            outlineStyle: style.outlineStyle,
            outlineWidth: style.outlineWidth,
        };
    });
    await pickerSearch.evaluate((element) => {
        element.blur();
    });
    const restingSearchBorder = await pickerSearch.evaluate(
        (element) => getComputedStyle(element).borderColor,
    );
    await pickerSearch.focus();
    expect(focusedSearchStyle.borderColor).toBe(restingSearchBorder);
    expect(focusedSearchStyle.boxShadow).toBe("none");
    expect(focusedSearchStyle.outlineStyle).toBe("none");
    expect(focusedSearchStyle.outlineWidth).toBe("0px");
    expect(focusedSearchStyle.outlineColor).not.toMatch(/rgb\(255, 165, 0\)/i);
    await pickerSearch.fill("catalog reaction 200");
    await expect(picker).toBeVisible();
    await expect(
        picker.getByRole("button", { name: "React with Catalog reaction 200" }),
    ).toBeVisible();
    await pickerSearch.fill("");

    if (testInfo.project.name.startsWith("mobile")) {
        await page.locator(".reaction-picker-layer").click({
            position: { x: 2, y: 2 },
        });
        await expect(picker).toBeHidden();
        await expect(postTrigger).toBeFocused();
        await postTrigger.click();
        await expect(picker).toBeVisible();
    } else {
        const triggerBox = await postTrigger.boundingBox();
        const pickerBox = await picker.boundingBox();
        expect(triggerBox).not.toBeNull();
        expect(pickerBox).not.toBeNull();
        if (triggerBox && pickerBox) {
            expect(pickerBox.x).toBeLessThanOrEqual(
                triggerBox.x + triggerBox.width,
            );
            expect(pickerBox.x + pickerBox.width).toBeGreaterThanOrEqual(
                triggerBox.x,
            );
            expect(pickerBox.y).toBeGreaterThanOrEqual(triggerBox.y + 43);
        }
    }
    await page.keyboard.press("Escape");
    await expect(picker).toBeHidden();
    await expect(postTrigger).toBeFocused();

    await postTrigger.press("Space");
    await expect(picker).toBeVisible();
    await picker.getByRole("button", { name: "Close reaction picker" }).click();
    await expect(postTrigger).toBeFocused();

    await postTrigger.click();
    await expect(picker).toBeVisible();
    if (testInfo.project.name.startsWith("mobile")) {
        await page.locator(".reaction-picker-layer").click({
            position: { x: 2, y: 2 },
        });
    } else {
        await postTrigger.click();
    }
    await expect(picker).toBeHidden();
    await expect(postTrigger).toHaveAttribute("aria-expanded", "false");
    await expect(postTrigger).toBeFocused();

    await postTrigger.click();
    await expect(picker).toBeVisible();
    const beforeBlockedClick = await postGroup
        .getByRole("button", { name: "Add Clapping reaction" })
        .getAttribute("aria-pressed");
    await postGroup
        .getByRole("button", { name: "Add Clapping reaction" })
        .click({ force: true });
    await expect(picker).toBeHidden();
    await expect(
        postGroup.getByRole("button", { name: "Add Clapping reaction" }),
    ).toHaveAttribute("aria-pressed", beforeBlockedClick ?? "false");

    await postTrigger.click();
    await expect(picker).toBeVisible();
    const bridgeLink = page.getByRole("link", {
        name: "Bridge",
        exact: true,
    });
    if (testInfo.project.name.startsWith("mobile")) {
        await bridgeLink.evaluate((link: HTMLAnchorElement) => {
            link.click();
        });
    } else {
        await bridgeLink.click();
    }
    await expect(page).toHaveURL("/bridge");
    await page.goBack();
    await expect(page).toHaveURL("/posts/testing-secure-systems");
    const warmTrigger = page
        .getByRole("group", { name: "Reactions" })
        .first()
        .getByRole("button", { name: "Choose reaction" });
    await warmTrigger.click();
    await expect(
        page
            .getByRole("dialog", { name: "Choose a reaction" })
            .getByRole("button", { name: "React with Clapping" }),
    ).toBeVisible();
    expect(
        requests.filter((path) => path === "/api/v1/reactions/catalog/"),
    ).toHaveLength(1);
    await page.keyboard.press("Escape");

    const restoredComment = page
        .locator('article[data-comment-id="10"]')
        .first();
    const threadTrigger = restoredComment
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
    await expect(thread.locator(".reaction-pill")).toHaveCount(2);
    for (const index of [0, 1]) {
        await expectSlackReactionGeometry(
            thread.locator(".reaction-pill").nth(index),
        );
    }
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

test("thread picker selection wins the focus trap after settlement", async ({
    page,
}) => {
    await login(page);

    const mainComment = page.locator('article[data-comment-id="10"]').first();
    const threadButton = mainComment.getByRole("button", {
        name: "Reply",
        exact: true,
    });
    await expect(threadButton).toHaveCount(1);
    await threadButton.click();

    const thread = page.getByRole("dialog", {
        name: "Thread for comment by Site Author",
    });
    await expect(thread).toBeVisible();
    const threadRoot = thread.locator('article[data-comment-id="10"]');
    await expect(threadRoot).toHaveCount(1);
    const trigger = threadRoot.getByRole("button", {
        name: "Choose reaction",
    });
    await expect(trigger).toHaveCount(1);

    let releaseToggle: (() => void) | undefined;
    await page.route(
        /\/api\/v1\/comments\/10\/reactions\/toggle\/$/,
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
    const picker = threadRoot.getByRole("dialog", {
        name: "Choose a reaction",
    });
    await expect(picker).toBeVisible();
    await picker
        .getByRole("button", { name: "React with Sending love" })
        .click();

    const optimistic = threadRoot.getByRole("button", {
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
        "/signup",
        "/account",
        "/account/profile",
        "/account/verify-email",
        "/account/password/reset",
        "/account/password/reset/confirm",
        "/account/password/set",
        "/account/password/change",
        "/subscriptions/",
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
        const header = await page
            .locator(".site-header__inner:visible")
            .boundingBox();
        const controls = await page
            .locator(".site-header__controls:visible")
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
            .locator(".site-header__inner:visible")
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
        "/signup",
        "/account",
        "/account/profile",
        "/account/verify-email",
        "/account/password/reset",
        "/account/password/reset/confirm",
        "/account/password/set",
        "/account/password/change",
        "/subscriptions/",
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

test("local signup, verification, login, nickname interaction, reset, and change", async ({
    page,
}) => {
    test.slow();
    const leakedRequests: string[] = [];
    page.on("request", (request) => leakedRequests.push(request.url()));

    await page.goto("/posts/testing-secure-systems");
    await expect(
        page.getByText("by Site Author", { exact: true }),
    ).toBeVisible();
    const postGroup = page.getByRole("group", { name: "Reactions" }).first();
    await postGroup.getByRole("button", { name: "Choose reaction" }).click();
    await page
        .getByRole("dialog", { name: "Choose a reaction" })
        .getByRole("button", { name: "React with Clapping" })
        .press("Enter");
    const pending = page.locator(".reaction-notice");
    await expect(pending).toContainText(
        "Sign in to add your Pepe clap reaction",
    );
    await pending.getByRole("link", { name: "Login" }).click();
    await page.getByRole("link", { name: "Create an account" }).click();

    const email = "stage17-reader@example.test";
    const firstPassword = "Stage17 browser passphrase 42!";
    const changedPassword = "Stage17 changed passphrase 84!";
    const resetPassword = "Stage17 reset passphrase 126!";
    const createAccount = page.getByRole("button", {
        name: "Create account",
    });
    await expect(createAccount).toBeVisible();
    const signupForm = createAccount.locator("xpath=ancestor::form");
    await signupForm.locator('input[name="email"]').fill(email);
    await signupForm.locator('input[name="nickname"]').fill("Stage Reader");
    await signupForm.locator('input[name="password"]').fill(firstPassword);
    await signupForm
        .locator('input[name="password_confirmation"]')
        .fill(firstPassword);
    await createAccount.click();
    await expect(
        page.getByText(/If the address can be registered/),
    ).toBeVisible();

    await page.goto("/account/verify-email#credential=e2e-verification");
    await expect(page).toHaveURL(/\/account\/verify-email$/);
    await expect(page.getByText(/Email verified/)).toBeVisible();
    expect(
        leakedRequests.some((request) => request.includes("e2e-verification")),
    ).toBe(false);

    await page.goto("/login?next=%2Fposts%2Ftesting-secure-systems");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(firstPassword);
    await page.getByRole("button", { name: "Login with email" }).click();
    await expect(page).toHaveURL(/\/posts\/testing-secure-systems$/);
    await expect(
        page.getByRole("button", { name: "Stage Reader" }),
    ).toBeVisible();
    await expect(page.locator(".reaction-notice")).toContainText(
        "Add your saved Pepe clap reaction?",
    );
    await expect(
        postGroup.getByRole("button", {
            name: "View 1 participant for Clapping",
        }),
    ).toBeVisible();
    await page
        .locator(".reaction-notice")
        .getByRole("button", { name: "Confirm" })
        .click();
    const participants = postGroup.getByRole("button", {
        name: "View 2 participants for Clapping",
    });
    await expect(participants).toBeVisible();
    await participants.click();
    await expect(
        page
            .getByRole("dialog", { name: "Clapping reaction participants" })
            .getByText("Stage Reader", { exact: true }),
    ).toBeVisible();
    await page.keyboard.press("Escape");

    await page
        .getByPlaceholder("Write a plain-text comment")
        .fill("Nickname-backed browser comment.");
    await page.getByRole("button", { name: "Comment", exact: true }).click();
    const createdComment = page
        .locator("article[data-comment-id]")
        .filter({ hasText: "Nickname-backed browser comment." });
    await expect(createdComment).toContainText("Stage Reader");

    await page.goto("/account");
    await expect(
        page.getByText("stage17-reader@example.test · Verified"),
    ).toBeVisible();
    await page.getByRole("button", { name: "Connect GitHub" }).click();
    await expect(page).toHaveURL(/\/account$/);
    await expect(page.getByText("GitHubConnected")).toBeVisible();

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
    await expect(
        page
            .getByRole("navigation", { name: "Primary navigation" })
            .getByRole("link", { name: "Login", exact: true }),
    ).toBeVisible();
    await page.goto("/account/password/reset");
    await page.getByLabel("Email").fill(email);
    await page.getByRole("button", { name: "Send reset email" }).click();
    await expect(page.getByText(/If the account is eligible/)).toBeVisible();

    await page.goto("/account/password/reset/confirm#credential=e2e-reset");
    await expect(page).toHaveURL(/\/account\/password\/reset\/confirm$/);
    await page.getByLabel("New password", { exact: true }).fill(resetPassword);
    await page.getByLabel("Confirm new password").fill(resetPassword);
    await page.getByRole("button", { name: "Reset password" }).click();
    await expect(page.getByText(/Password reset/)).toBeVisible();
    expect(
        leakedRequests.some((request) => request.includes("e2e-reset")),
    ).toBe(false);

    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(resetPassword);
    await page.getByRole("button", { name: "Login with email" }).click();
    await expect(page).toHaveURL("/");
    await expect(
        page.getByRole("button", { name: "Stage Reader" }),
    ).toBeVisible();
    expect(
        await page.evaluate(
            (secrets) => {
                const values: string[] = [];
                for (const storage of [localStorage, sessionStorage]) {
                    for (let index = 0; index < storage.length; index += 1) {
                        const value = storage.getItem(storage.key(index) ?? "");
                        if (value !== null) {
                            values.push(value);
                        }
                    }
                }
                return values.some((value) =>
                    secrets.some((secret) => value.includes(secret)),
                );
            },
            [
                firstPassword,
                changedPassword,
                resetPassword,
                "e2e-verification",
                "e2e-reset",
            ],
        ),
    ).toBe(false);
    await expectNoHorizontalOverflow(page);
    await expectAccessible(page);
});

test("OAuth profile completion and password set stay on one account", async ({
    page,
}) => {
    await page.request.post("http://127.0.0.1:3101/__oauth-incomplete");
    await page.goto("/login?next=%2Fposts%2Ftesting-secure-systems");
    await page.getByRole("button", { name: "Continue with Google" }).click();
    await expect(page).toHaveURL(/\/account\/profile\?next=/);
    await expect(page.getByText(/public profile is incomplete/i)).toHaveCount(
        0,
    );
    const nickname = page.getByLabel("Public nickname");
    await expect(nickname).toHaveValue("Suggested Reader");
    await nickname.fill("OAuth Public Reader");
    await page.getByRole("button", { name: "Finish profile" }).click();
    await expect(page).toHaveURL(/\/posts\/testing-secure-systems$/);
    await expect(
        page.getByRole("button", { name: "OAuth Public Reader" }),
    ).toBeVisible();

    await page.goto("/account");
    await expect(page.getByText("GoogleConnected")).toBeVisible();
    await page.getByRole("link", { name: "Set password" }).click();
    await page
        .getByLabel("New password", { exact: true })
        .fill("OAuth local passphrase 42!");
    await page
        .getByLabel("Confirm new password")
        .fill("OAuth local passphrase 42!");
    await page.getByRole("button", { name: "Set password" }).click();
    await expect(
        page.getByText("Password set.", { exact: false }),
    ).toBeVisible();
    await page.goto("/account");
    await expect(page.getByText("GoogleConnected")).toBeVisible();
    await expect(page.getByText("PasswordSet")).toBeVisible();
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
    const subscriptionMutations: string[] = [];
    page.on("request", (request) => {
        if (
            request.method() !== "GET" &&
            new URL(request.url()).pathname.startsWith("/api/v1/subscriptions/")
        ) {
            subscriptionMutations.push(
                `${request.method()} ${new URL(request.url()).pathname}`,
            );
        }
    });
    await page.goto("/");
    await expect(
        page.getByRole("textbox", { name: "Email address" }),
    ).toHaveCount(0);
    await page.getByRole("link", { name: "Subscribe", exact: true }).click();
    await expect(page).toHaveURL("/subscriptions/");
    expect(subscriptionMutations).toHaveLength(0);
    await page
        .getByRole("textbox", { name: "Email address" })
        .fill("reader@example.test");
    await page.getByRole("button", { name: "Subscribe" }).click();
    await expect(page.getByText("Check your inbox.")).toBeVisible();
    expect(subscriptionMutations).toEqual(["POST /api/v1/subscriptions/"]);

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
