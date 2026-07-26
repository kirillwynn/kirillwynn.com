export type BridgeLink = {
    name: string;
    url: string;
    icon: string;
};

export const bridgeLinks = [
    {
        name: "GitHub",
        url: "https://github.com/kirillwynn",
        icon: "/socials/github.svg",
    },
    {
        name: "LeetCode",
        url: "https://leetcode.com/u/kirillwynn/",
        icon: "/socials/leetcode.svg",
    },
    {
        name: "Reddit",
        url: "https://reddit.com/user/kirillwynn",
        icon: "/socials/reddit.svg",
    },
    {
        name: "Telegram",
        url: "https://t.me/kirillwynn",
        icon: "/socials/telegram.svg",
    },
    {
        name: "Instagram",
        url: "https://instagram.com/kirillwynn",
        icon: "/socials/instagram.svg",
    },
    {
        name: "X",
        url: "https://x.com/kirillwynn",
        icon: "/socials/x.svg",
    },
    {
        name: "Steam",
        url: "https://steamcommunity.com/id/kirillwynn",
        icon: "/socials/steam.svg",
    },
    {
        name: "Pulse",
        url: "https://www.tbank.ru/invest/social/profile/kirillwynn/",
        icon: "/socials/pulse.svg",
    },
] as const satisfies readonly BridgeLink[];

export const teams = [
    { label: "Current Team", name: "Yandex" },
    { label: "Previous Team", name: "Deeplay" },
] as const;
