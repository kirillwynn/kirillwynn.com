import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import BridgePage from "@/app/bridge/page";
import { bridgeLinks, teams } from "@/lib/bridge";

describe("Bridge configuration", () => {
    it("contains exactly the eight approved profile URLs in order", () => {
        expect(bridgeLinks).toHaveLength(8);
        expect(bridgeLinks.map(({ name, url }) => ({ name, url }))).toEqual([
            { name: "GitHub", url: "https://github.com/kirillwynn" },
            {
                name: "LeetCode",
                url: "https://leetcode.com/u/kirillwynn/",
            },
            {
                name: "Reddit",
                url: "https://reddit.com/user/kirillwynn",
            },
            { name: "Telegram", url: "https://t.me/kirillwynn" },
            {
                name: "Instagram",
                url: "https://instagram.com/kirillwynn",
            },
            { name: "X", url: "https://x.com/kirillwynn" },
            {
                name: "Steam",
                url: "https://steamcommunity.com/id/kirillwynn",
            },
            {
                name: "Pulse",
                url: "https://www.tbank.ru/invest/social/profile/kirillwynn/",
            },
        ]);
    });

    it("keeps team labels as plain configuration without invented URLs", () => {
        expect(teams).toEqual([
            { label: "Current Team", name: "Yandex" },
            { label: "Previous Team", name: "Deeplay" },
        ]);
        expect(JSON.stringify(teams)).not.toContain("http");
    });

    it("renders an icon-only grid with unique accessible link names", () => {
        const html = renderToStaticMarkup(createElement(BridgePage));

        expect(html).toContain('class="bridge-grid"');
        expect(html).toContain('<h1 class="sr-only">Bridge</h1>');
        expect(html).not.toContain(
            "Profiles and places where you can find me elsewhere on the internet.",
        );
        for (const link of bridgeLinks) {
            expect(html).toContain(
                `aria-label="${link.name} (opens in a new tab)"`,
            );
            expect(html).not.toContain(`>${link.name}<`);
        }
        expect(html.match(/target="_blank"/g)).toHaveLength(8);
        expect(html.match(/rel="noopener noreferrer"/g)).toHaveLength(8);
        expect(html.match(/alt="" aria-hidden="true"/g)).toHaveLength(8);
        expect(
            html.match(/aria-label="[^"]+ \(opens in a new tab\)"/g),
        ).toHaveLength(8);
        expect(html).not.toContain("Current Team");
        expect(html).not.toContain("Previous Team");
        expect(html).not.toContain("Yandex");
        expect(html).not.toContain("Deeplay");
    });
});
