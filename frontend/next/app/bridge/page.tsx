import type { Metadata } from "next";

import { bridgeLinks } from "@/lib/bridge";

export const metadata: Metadata = {
    title: "Bridge",
    description: "Kirill Wynn across the web.",
    alternates: { canonical: "/bridge" },
    openGraph: {
        title: "Bridge · Kirill Wynn",
        description: "Profiles and places to find Kirill Wynn across the web.",
        url: "/bridge",
    },
};

export default function BridgePage() {
    return (
        <div className="page-shell-wide">
            <header className="bridge-header">
                <h1>Bridge</h1>
                <p>
                    Profiles and places where you can find me elsewhere on the
                    internet.
                </p>
            </header>

            <ul className="bridge-grid">
                {bridgeLinks.map((link) => (
                    <li key={link.name}>
                        <a
                            className="bridge-link"
                            href={link.url}
                            target="_blank"
                            rel="noopener noreferrer"
                        >
                            {/* Existing legacy assets are intentionally reused. */}
                            <img
                                src={link.icon}
                                alt=""
                                aria-hidden="true"
                                width="42"
                                height="42"
                            />
                            <span>
                                {link.name}
                                <span className="sr-only">
                                    {" "}
                                    (opens in a new tab)
                                </span>
                            </span>
                        </a>
                    </li>
                ))}
            </ul>
        </div>
    );
}
