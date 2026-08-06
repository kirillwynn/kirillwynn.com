import fs from "node:fs";
import path from "node:path";

import AxeBuilder from "@axe-core/playwright";
import {
    expect,
    test,
    type Locator,
    type Page,
    type TestInfo,
} from "@playwright/test";

function observeBrowserFailures(page: Page) {
    const failures: string[] = [];
    page.on("console", (message) => {
        if (message.type() === "error" || message.type() === "warning") {
            failures.push(`${message.type()}:${message.text()}`);
        }
    });
    page.on("pageerror", (error) =>
        failures.push(`pageerror:${error.message}`),
    );
    return failures;
}

async function expectNoOverflow(page: Page) {
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

async function expectAccessible(page: Page) {
    const result = await new AxeBuilder({ page }).analyze();
    expect(result.violations).toEqual([]);
}

async function expectSlackReactionGeometry(pill: Locator) {
    await expect(pill).toBeVisible();
    const geometry = await pill.evaluate((element) => {
        const target = element.getBoundingClientRect();
        const visual = getComputedStyle(element, "::before");
        const asset = element.querySelector(".reaction-pill__asset");
        const count = element.querySelector(".reaction-pill__count");
        return {
            asset: asset ? Number.parseFloat(getComputedStyle(asset).width) : 0,
            count: count
                ? Number.parseFloat(getComputedStyle(count).fontSize)
                : 0,
            target: target.height,
            visual: Number.parseFloat(visual.height),
        };
    });
    expect(geometry.target).toBeGreaterThanOrEqual(44);
    expect(geometry.visual).toBeGreaterThanOrEqual(28);
    expect(geometry.visual).toBeLessThanOrEqual(32);
    expect(geometry.asset).toBeGreaterThanOrEqual(15);
    expect(geometry.asset).toBeLessThanOrEqual(16);
    expect(geometry.count).toBeGreaterThanOrEqual(12);
    expect(geometry.count).toBeLessThanOrEqual(13);
}

async function expectHydrated(page: Page) {
    await expect
        .poll(
            () =>
                page.evaluate(() =>
                    performance
                        .getEntriesByType("resource")
                        .some(
                            (entry) =>
                                new URL(entry.name).pathname === "/api/me/",
                        ),
                ),
            { timeout: 15_000 },
        )
        .toBe(true);
}

function writeMetrics(testInfo: TestInfo, payload: Record<string, unknown>) {
    const output = process.env.STAGING_AUDIT_OUTPUT_DIR;
    if (!output) {
        return;
    }
    fs.mkdirSync(output, { recursive: true, mode: 0o700 });
    const target = path.join(output, `browser-${testInfo.project.name}.json`);
    const existing = fs.existsSync(target)
        ? (JSON.parse(fs.readFileSync(target, "utf8")) as Record<
              string,
              unknown
          >)
        : {};
    fs.writeFileSync(
        target,
        `${JSON.stringify({ ...existing, ...payload }, null, 2)}\n`,
        { mode: 0o600 },
    );
}

test("public shell, security headers, focus, theme, and accessibility", async ({
    page,
}, testInfo) => {
    await page.addInitScript(() => {
        const auditWindow = window as Window & {
            __stage19LayoutShift?: number;
            __stage19LayoutShiftObserver?: PerformanceObserver;
            __stage19LayoutShiftSupported?: boolean;
        };
        auditWindow.__stage19LayoutShift = 0;
        auditWindow.__stage19LayoutShiftSupported =
            PerformanceObserver.supportedEntryTypes.includes("layout-shift");
        if (!auditWindow.__stage19LayoutShiftSupported) {
            return;
        }
        auditWindow.__stage19LayoutShiftObserver = new PerformanceObserver(
            (list) => {
                for (const entry of list.getEntries()) {
                    const shift = entry as PerformanceEntry & {
                        hadRecentInput?: boolean;
                        value?: number;
                    };
                    if (!shift.hadRecentInput) {
                        auditWindow.__stage19LayoutShift =
                            (auditWindow.__stage19LayoutShift ?? 0) +
                            (shift.value ?? 0);
                    }
                }
            },
        );
        auditWindow.__stage19LayoutShiftObserver.observe({
            type: "layout-shift",
            buffered: true,
        });
    });
    const failures = observeBrowserFailures(page);
    const requests: string[] = [];
    page.on("request", (request) =>
        requests.push(new URL(request.url()).pathname),
    );
    const response = await page.goto("/", { waitUntil: "domcontentloaded" });
    expect(response?.status()).toBe(200);
    await expectHydrated(page);
    const headers = response?.headers() ?? {};
    expect(headers["content-security-policy"]).toContain("default-src");
    expect(headers["strict-transport-security"]).toContain("max-age=");
    expect(headers["x-content-type-options"]).toBe("nosniff");
    expect(headers["referrer-policy"]).toBeTruthy();

    await expect(
        page.getByRole("link", { name: "Feed", exact: true }),
    ).toBeVisible();
    const controls = page.locator(".site-header__controls");
    const headerControls = controls.locator(":scope > *");
    await expect(headerControls).toHaveCount(4);
    await expect(headerControls.nth(0)).toHaveAccessibleName("Feed");
    await expect(headerControls.nth(1)).toHaveAccessibleName("Bridge");
    await expect(headerControls.nth(2)).toHaveAccessibleName(
        "Switch to light theme",
    );
    await expect(headerControls.nth(3)).toHaveClass(/account-slot/);
    await expect(
        headerControls.nth(3).getByRole("link", { name: "Login", exact: true }),
    ).toBeVisible();

    const footer = page.getByRole("contentinfo");
    await expect(footer.locator(".site-team-context > div")).toHaveCount(2);
    await expect(footer.locator("p, a")).toHaveCount(0);
    await expect(footer.getByText(/©|Kirill Wynn/)).toHaveCount(0);
    await expect
        .poll(() =>
            footer
                .locator("dt")
                .first()
                .evaluate((term) => getComputedStyle(term, "::after").content),
        )
        .toBe('":"');

    const search = page.getByRole("searchbox", { name: "Search posts" });
    const rest = await search.evaluate((element) => {
        const style = getComputedStyle(element);
        return {
            background: style.backgroundColor,
            border: style.borderColor,
            outline: style.outlineWidth,
            shadow: style.boxShadow,
        };
    });
    await search.focus();
    await expect(search).toBeFocused();
    const focused = await search.evaluate((element) => {
        const style = getComputedStyle(element);
        return {
            background: style.backgroundColor,
            border: style.borderColor,
            outline: style.outlineWidth,
            shadow: style.boxShadow,
        };
    });
    expect(focused.border).toBe(rest.border);
    expect(focused.outline).toBe("0px");
    expect(focused.shadow).toBe("none");
    expect(focused.background).not.toBe(rest.background);

    await expect(page.getByText("Clear search", { exact: true })).toHaveCount(
        0,
    );
    await expect(page.getByText("Clear filters", { exact: true })).toHaveCount(
        0,
    );
    await expectNoOverflow(page);
    await expectAccessible(page);
    expect(requests.filter((request) => request === "/api/me/")).toHaveLength(
        1,
    );

    await page.getByRole("button", { name: "Switch to light theme" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await expectHydrated(page);
    await expect(
        page.getByRole("link", { name: "Login", exact: true }),
    ).toBeVisible();

    const browserStorageKeys = await page.evaluate(() => [
        ...Object.keys(window.localStorage),
        ...Object.keys(window.sessionStorage),
    ]);
    expect(
        browserStorageKeys.some((key) =>
            /(?:access|refresh|session|jwt|auth).*token|socialtoken/i.test(key),
        ),
    ).toBe(false);

    const resources = await page.evaluate(() =>
        performance.getEntriesByType("resource").map((entry) => {
            const resource = entry as PerformanceResourceTiming;
            return {
                name: new URL(resource.name).pathname,
                transferSize: resource.transferSize,
                encodedBodySize: resource.encodedBodySize,
            };
        }),
    );
    const initialAssets = resources.filter((entry) =>
        entry.name.startsWith("/_next/static/"),
    );
    const layoutShift = await page.evaluate(() => {
        const auditWindow = window as Window & {
            __stage19LayoutShift?: number;
            __stage19LayoutShiftSupported?: boolean;
        };
        return {
            supported: auditWindow.__stage19LayoutShiftSupported ?? false,
            value: auditWindow.__stage19LayoutShift ?? 0,
        };
    });
    expect(layoutShift.supported).toBe(true);
    expect(
        resources.some(
            (entry) =>
                entry.name.includes("/reactions/catalog/") ||
                entry.name.includes("emoji-mart"),
        ),
    ).toBe(false);
    writeMetrics(testInfo, {
        viewport: page.viewportSize(),
        initial_next_assets: initialAssets.length,
        initial_next_transfer_bytes: initialAssets.reduce(
            (total, entry) => total + entry.transferSize,
            0,
        ),
        initial_next_encoded_bytes: initialAssets.reduce(
            (total, entry) => total + entry.encodedBodySize,
            0,
        ),
        cumulative_layout_shift: layoutShift.value,
        layout_shift_supported: layoutShift.supported,
        me_requests: requests.filter((request) => request === "/api/me/")
            .length,
        horizontal_overflow: false,
        axe_violations: 0,
        console_failures: failures.length,
    });
    expect(requests.filter((request) => request === "/api/me/")).toHaveLength(
        2,
    );
    expect(failures).toEqual([]);
});

test("client navigation, infinite Feed, Unicode history, legacy normalization, subscriptions, and 404", async ({
    page,
}, testInfo) => {
    const failures = observeBrowserFailures(page);
    const documents: string[] = [];
    const requests: string[] = [];
    page.on("request", (request) => {
        const url = new URL(request.url());
        requests.push(url.pathname + url.search);
        if (request.resourceType() === "document") {
            documents.push(url.pathname);
        }
    });

    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expectHydrated(page);
    const initialFeedCount = await page.locator(".feed-entry").count();
    expect(initialFeedCount).toBeGreaterThan(0);
    await expect(page.locator(".feed-tag, .feed-pagination")).toHaveCount(0);
    await expect(page.getByText(/^Page \d+$/)).toHaveCount(0);
    await expect(page.getByText("Next", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Previous", { exact: true })).toHaveCount(0);
    await expect(
        page.getByRole("textbox", { name: "Email address" }),
    ).toHaveCount(0);
    await page.evaluate(() => {
        window.scrollTo(0, document.body.scrollHeight);
    });
    await page.waitForTimeout(750);
    const appendedFeedCount = await page.locator(".feed-entry").count();
    expect(appendedFeedCount).toBeGreaterThanOrEqual(initialFeedCount);

    await page.locator("header").evaluate((element) => {
        element.setAttribute("data-stage19-shell", "persistent");
    });
    await page.locator("footer").evaluate((element) => {
        element.setAttribute("data-stage19-shell", "persistent");
    });
    const postLink = page.locator(".feed-entry-title a").last();
    await postLink.scrollIntoViewIfNeeded();
    const feedScrollBeforePost = await page.evaluate(() => window.scrollY);
    const postNavigationStartedAt = Date.now();
    await postLink.click();
    await expect(page.locator("article")).toBeVisible();
    const postClientNavigationMs = Date.now() - postNavigationStartedAt;
    const postBackStartedAt = Date.now();
    await page.goBack();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.locator(".feed-entry")).toHaveCount(appendedFeedCount);
    await expect
        .poll(async () => {
            const restored = await page.evaluate(() => window.scrollY);
            return Math.abs(restored - feedScrollBeforePost) <= 3;
        })
        .toBe(true);
    const postBackMs = Date.now() - postBackStartedAt;
    await expect(page.locator("header")).toHaveAttribute(
        "data-stage19-shell",
        "persistent",
    );
    await expect(page.locator("footer")).toHaveAttribute(
        "data-stage19-shell",
        "persistent",
    );
    await expect(page.getByLabel("Loading account")).toHaveCount(0);

    const search = page.getByRole("searchbox", { name: "Search posts" });
    await search.fill("東京");
    await expect(page).toHaveURL(/\?q=%E6%9D%B1%E4%BA%AC$/);
    await expect
        .poll(async () => {
            const href = await page
                .getByRole("link", { name: "Login", exact: true })
                .getAttribute("href");
            return new URL(
                href ?? "",
                "https://staging.kirillwynn.com",
            ).searchParams.get("next");
        })
        .toBe("/?q=東京");

    const meBeforeNavigation = requests.filter(
        (request) => request === "/api/me/",
    ).length;
    const bridgeNavigationStartedAt = Date.now();
    await page.getByRole("link", { name: "Bridge", exact: true }).click();
    await expect(page).toHaveURL(/\/bridge$/);
    const bridgeClientNavigationMs = Date.now() - bridgeNavigationStartedAt;
    const bridgeBackStartedAt = Date.now();
    await page.goBack();
    await expect(page).toHaveURL(/\?q=%E6%9D%B1%E4%BA%AC$/);
    await expect(search).toHaveValue("東京");
    const bridgeBackMs = Date.now() - bridgeBackStartedAt;
    await page.goForward();
    await expect(page).toHaveURL(/\/bridge$/);
    await page.goBack();
    expect(documents).toEqual(["/"]);
    expect(requests.filter((request) => request === "/api/me/").length).toBe(
        meBeforeNavigation,
    );
    await expect(
        page.locator('[class*="skeleton"], [aria-label="Loading feed"]'),
    ).toHaveCount(0);

    await search.fill("stage19-no-result-7f3e");
    await expect(page).toHaveURL(/stage19-no-result-7f3e$/);
    await expect(page.getByText(/No posts/i)).toBeVisible();
    await expect(page.getByText("Clear search", { exact: true })).toHaveCount(
        0,
    );

    await page.goto("/?tag=django&page=2&q=東京", {
        waitUntil: "domcontentloaded",
    });
    await expect(page).toHaveURL(/\?q=%E6%9D%B1%E4%BA%AC$/);
    await expect(page.locator(".feed-tag, .feed-pagination")).toHaveCount(0);
    await page.getByRole("link", { name: "Subscribe", exact: true }).click();
    await expect(page).toHaveURL(/\/subscriptions\/$/);
    await expect(
        page.getByRole("heading", { name: "Get new posts by email" }),
    ).toBeVisible();
    await expect(
        page.getByRole("textbox", { name: "Email address" }),
    ).toBeVisible();
    await expectNoOverflow(page);

    await page.goto("/stage19-read-only-missing-route");
    await expect(
        page.getByRole("heading", { name: /not found/i }),
    ).toBeVisible();
    await expectNoOverflow(page);
    await expectAccessible(page);
    writeMetrics(testInfo, {
        appended_feed_count: appendedFeedCount,
        bridge_back_ms: bridgeBackMs,
        bridge_client_navigation_ms: bridgeClientNavigationMs,
        document_requests_before_direct_404: documents.length - 1,
        feed_scroll_before_post: feedScrollBeforePost,
        initial_feed_count: initialFeedCount,
        me_requests_before_client_navigation: meBeforeNavigation,
        post_back_ms: postBackMs,
        post_client_navigation_ms: postClientNavigationMs,
        public_list_requests: requests.filter((request) =>
            request.startsWith("/api/v1/posts/"),
        ).length,
    });
    expect(
        failures.filter(
            (failure) =>
                !failure.includes("server responded with a status of 404"),
        ),
    ).toEqual([]);
});

test("detail and reaction surfaces stay lazy, explicit, and reduced-motion safe", async ({
    page,
}, testInfo) => {
    const failures = observeBrowserFailures(page);
    const reactionRequests: string[] = [];
    page.on("request", (request) => {
        const pathname = new URL(request.url()).pathname;
        if (pathname.includes("/reactions/")) {
            reactionRequests.push(pathname);
        }
    });
    await page.emulateMedia({ reducedMotion: "reduce", colorScheme: "dark" });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expectHydrated(page);

    const feedParticipant = page
        .getByRole("button", { name: /participant/i })
        .first();
    await expect(feedParticipant).toBeVisible();
    const participantRequestsBefore = reactionRequests.filter((request) =>
        request.includes("/participants/"),
    ).length;
    await feedParticipant.hover();
    await feedParticipant.focus();
    await page.waitForTimeout(100);
    await expect(
        page.getByRole("dialog", { name: /participants/i }),
    ).toHaveCount(0);
    expect(
        reactionRequests.filter((request) =>
            request.includes("/participants/"),
        ),
    ).toHaveLength(participantRequestsBefore);
    await feedParticipant.press("Space");
    await expect(
        page.getByRole("dialog", { name: /participants/i }),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(feedParticipant).toBeFocused();

    const postLink = page.locator(".feed-entry h2 a").first();
    await expect(postLink).toBeVisible();
    await postLink.click();
    await expect(page.locator("article")).toBeVisible();
    await expect(page.locator("article time").first()).toBeVisible();
    await expect(
        page.getByRole("textbox", { name: "Email address" }),
    ).toHaveCount(0);
    await expect(page.locator(".post-tags, .feed-entry-tags")).toHaveCount(0);

    const postGroup = page.getByRole("group", { name: "Reactions" }).first();
    const trigger = postGroup.getByRole("button", { name: "Choose reaction" });
    await expect(trigger).toHaveCount(1);
    await expect(
        page.getByRole("button", { name: /^React with / }),
    ).toHaveCount(0);
    const surfacePills = page.locator(".reaction-pill:visible");
    const surfacePillCount = await surfacePills.count();
    expect(surfacePillCount).toBeGreaterThan(0);
    for (let index = 0; index < surfacePillCount; index += 1) {
        await expectSlackReactionGeometry(surfacePills.nth(index));
    }
    const catalogBeforeOpen = reactionRequests.filter((request) =>
        request.endsWith("/reactions/catalog/"),
    ).length;
    expect(catalogBeforeOpen).toBeLessThanOrEqual(1);

    const coldStartedAt = Date.now();
    await trigger.press("Enter");
    const picker = page.getByRole("dialog", { name: "Choose a reaction" });
    await expect(picker).toBeVisible();
    const coldShellMs = Date.now() - coldStartedAt;
    expect(coldShellMs).toBeLessThan(500);
    await expect(
        picker.getByRole("button", { name: /^React with / }),
    ).toHaveCount(228);
    expect(
        reactionRequests.filter((request) =>
            request.endsWith("/reactions/catalog/"),
        ),
    ).toHaveLength(1);
    await expect(
        picker.locator('.reaction-image[data-animated="true"]'),
    ).toHaveCount(0);
    const pickerSearch = picker.getByRole("searchbox", {
        name: "Search reaction names",
    });
    await pickerSearch.focus();
    const searchFocus = await pickerSearch.evaluate((element) => {
        const style = getComputedStyle(element);
        return {
            border: style.borderColor,
            outline: style.outlineWidth,
            shadow: style.boxShadow,
        };
    });
    await pickerSearch.evaluate((element) => {
        element.blur();
    });
    const restingBorder = await pickerSearch.evaluate(
        (element) => getComputedStyle(element).borderColor,
    );
    expect(searchFocus.border).toBe(restingBorder);
    expect(searchFocus.outline).toBe("0px");
    expect(searchFocus.shadow).toBe("none");
    const pickerImages = await picker.locator("img").count();
    const loadedImages = await page.evaluate(
        () =>
            performance
                .getEntriesByType("resource")
                .filter(
                    (entry) =>
                        (entry as PerformanceResourceTiming).initiatorType ===
                        "img",
                ).length,
    );
    writeMetrics(testInfo, {
        catalog_items: 228,
        catalog_dom_images_after_open: pickerImages,
        image_resources_after_picker_open: loadedImages,
        catalog_requests_after_open: 1,
        animated_assets_started_with_reduced_motion: 0,
        cold_picker_shell_ms: coldShellMs,
    });
    await page.keyboard.press("Escape");
    await expect(trigger).toBeFocused();

    await page.getByRole("link", { name: "Bridge", exact: true }).click();
    await expect(page).toHaveURL(/\/bridge$/);
    await page.goBack();
    const warmTrigger = page
        .getByRole("group", { name: "Reactions" })
        .first()
        .getByRole("button", { name: "Choose reaction" });
    const warmStartedAt = Date.now();
    await warmTrigger.click();
    const warmPicker = page.getByRole("dialog", {
        name: "Choose a reaction",
    });
    await expect(
        warmPicker.getByRole("button", { name: /^React with / }),
    ).toHaveCount(228);
    const warmPickerMs = Date.now() - warmStartedAt;
    expect(
        reactionRequests.filter((request) =>
            request.endsWith("/reactions/catalog/"),
        ),
    ).toHaveLength(1);
    writeMetrics(testInfo, { warm_picker_ms: warmPickerMs });
    await page.keyboard.press("Escape");

    await expectNoOverflow(page);
    await expectAccessible(page);
    expect(failures).toEqual([]);
});

test("repeatable public API and media cache baseline", async ({
    page,
}, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-1440");
    await page.goto("/", { waitUntil: "domcontentloaded" });
    const endpoints = ["/api/v1/posts/?page=1", "/api/v1/posts/?q=東京"];
    const samples: Record<string, number[]> = {};
    const listings: Partial<Record<string, Record<string, unknown>>> = {};

    for (const endpoint of endpoints) {
        samples[endpoint] = [];
        for (let attempt = 0; attempt < 3; attempt += 1) {
            const started = Date.now();
            const response = await page.request.get(endpoint);
            samples[endpoint].push(Date.now() - started);
            expect(response.status()).toBe(200);
            if (attempt === 0) {
                listings[endpoint] = (await response.json()) as Record<
                    string,
                    unknown
                >;
            }
        }
    }

    const median = (values: number[]) =>
        [...values].sort((left, right) => left - right)[
            Math.floor(values.length / 2)
        ];
    const feedListing = listings["/api/v1/posts/?page=1"];
    const results = Array.isArray(feedListing?.results)
        ? (feedListing.results as Array<Record<string, unknown>>)
        : [];
    expect(results.length).toBeGreaterThan(0);
    const first = results[0];
    if (typeof first.slug !== "string" || !first.slug) {
        throw new Error("public post list did not expose a safe slug");
    }
    const slug = first.slug;
    const detailEndpoint = `/api/v1/posts/${encodeURIComponent(slug)}/`;
    const detailSamples: number[] = [];
    for (let attempt = 0; attempt < 3; attempt += 1) {
        const started = Date.now();
        const response = await page.request.get(detailEndpoint);
        detailSamples.push(Date.now() - started);
        expect(response.status()).toBe(200);
    }

    const unicodeListing = listings["/api/v1/posts/?q=東京"];
    const unicodeResults = Array.isArray(unicodeListing?.results)
        ? (unicodeListing.results as Array<Record<string, unknown>>)
        : [];
    const imagePost = unicodeResults.find((result) => result.lead_image);
    if (!imagePost) {
        throw new Error(
            "Unicode staging fixture did not expose a responsive lead image",
        );
    }
    const leadImage = imagePost.lead_image as
        | { renditions?: Record<string, { url?: string }> }
        | null
        | undefined;
    const renditionHeaders: Record<
        string,
        { cache_control: string; content_type: string }
    > = {};
    for (const key of ["480w", "960w", "1440w"] as const) {
        const rendition = leadImage?.renditions?.[key];
        if (!rendition?.url) {
            throw new Error(`Lead image did not expose its ${key} rendition`);
        }
        const media = await page.request.head(rendition.url);
        expect(media.status()).toBeLessThan(400);
        expect(media.headers()["content-type"] ?? "").toMatch(/^image\//);
        expect(media.headers()["cache-control"] ?? "").toMatch(
            /(?:immutable|max-age=31536000)/,
        );
        renditionHeaders[key] = {
            cache_control: media.headers()["cache-control"] ?? "",
            content_type: media.headers()["content-type"] ?? "",
        };
    }

    await page.goto("/?q=東京", { waitUntil: "domcontentloaded" });
    await expectHydrated(page);
    const renderedLeadImage = page.locator(".feed-entry-image img").first();
    await expect(renderedLeadImage).toBeVisible();
    await expect
        .poll(() =>
            renderedLeadImage.evaluate(
                (image) =>
                    image instanceof HTMLImageElement &&
                    image.complete &&
                    image.naturalWidth > 0,
            ),
        )
        .toBe(true);
    const responsiveImage = await renderedLeadImage.evaluate((image) => {
        if (!(image instanceof HTMLImageElement)) {
            throw new Error("Lead image locator returned a non-image element");
        }
        return {
            has_sizes: image.hasAttribute("sizes"),
            has_srcset: image.hasAttribute("srcset"),
            natural_width: image.naturalWidth,
            rendered_width: image.getBoundingClientRect().width,
        };
    });
    expect(responsiveImage.has_sizes).toBe(true);
    expect(responsiveImage.has_srcset).toBe(true);
    expect(responsiveImage.natural_width).toBeGreaterThan(0);
    expect(responsiveImage.rendered_width).toBeGreaterThan(0);
    writeMetrics(testInfo, {
        api_median_ms: {
            feed: median(samples["/api/v1/posts/?page=1"]),
            unicode_search: median(samples["/api/v1/posts/?q=東京"]),
            detail: median(detailSamples),
        },
        api_samples_ms: { ...samples, [detailEndpoint]: detailSamples },
        media_headers: renditionHeaders,
        responsive_images: [responsiveImage],
    });
});

test("personalized APIs are private and Bridge remains icon-only", async ({
    page,
}) => {
    const failures = observeBrowserFailures(page);
    await page.goto("/", { waitUntil: "domcontentloaded" });
    const meResponse = await page.request.get("/api/me/");
    expect(meResponse.status()).toBe(200);
    const cacheControl = meResponse.headers()["cache-control"] ?? "";
    expect(cacheControl).toContain("no-store");
    expect(meResponse.headers().vary).toMatch(/Cookie/i);

    const catalog = await page.request.get("/api/v1/reactions/catalog/");
    expect(catalog.status()).toBe(200);
    expect(catalog.headers()["cache-control"] ?? "").toMatch(
        /public.*max-age=.*stale-while-revalidate/,
    );
    expect(catalog.headers().etag).toBeTruthy();

    const listing = await page.request.get("/api/v1/posts/?page=1");
    expect(listing.status()).toBe(200);
    const listingPayload = (await listing.json()) as {
        results?: Array<{ slug?: string }>;
    };
    const slug = listingPayload.results?.[0]?.slug;
    if (!slug) {
        throw new Error("Staging Feed did not expose a post slug");
    }
    for (const endpoint of [
        `/api/v1/posts/${encodeURIComponent(slug)}/reactions/`,
        `/api/v1/posts/${encodeURIComponent(slug)}/comments/`,
    ]) {
        const personalized = await page.request.get(endpoint);
        expect(personalized.status()).toBe(200);
        expect(personalized.headers()["cache-control"] ?? "").toContain(
            "no-store",
        );
    }

    await page.getByRole("link", { name: "Bridge", exact: true }).click();
    await expect(page).toHaveURL(/\/bridge$/);
    const main = page.locator("#main-content");
    await expect(main.locator("h1")).toHaveClass(/sr-only/);
    await expect(main.locator("p")).toHaveCount(0);
    await expect(main.locator(".bridge-link")).toHaveCount(8);
    for (const link of await main.locator(".bridge-link").all()) {
        await expect(link).toHaveText("");
    }
    await expectNoOverflow(page);
    await expectAccessible(page);
    expect(failures).toEqual([]);
});
