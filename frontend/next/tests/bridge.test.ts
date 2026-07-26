import { describe, expect, it } from "vitest";

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
});
