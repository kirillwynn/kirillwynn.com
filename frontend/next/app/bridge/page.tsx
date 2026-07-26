import type { Metadata } from "next";

import { bridgeLinks, teams } from "@/lib/bridge";

export const metadata: Metadata = {
    title: "Bridge",
    description: "Kirill Wynn across the web and the teams behind the work.",
    alternates: { canonical: "/bridge" },
    openGraph: {
        title: "Bridge · Kirill Wynn",
        description: "Profiles and places to find Kirill Wynn across the web.",
        url: "/bridge",
    },
};

export default function BridgePage() {
    return (
        <div className="mx-auto max-w-4xl">
            <header className="max-w-2xl">
                <p className="eyebrow">Bridge</p>
                <h1 className="mt-3 text-balance text-4xl font-semibold tracking-tight text-stone-950 sm:text-5xl">
                    Elsewhere on the internet.
                </h1>
                <p className="mt-5 text-lg leading-8 text-stone-600">
                    Eight places where I write, build, solve, and keep in touch.
                </p>
            </header>

            <ul className="mt-10 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                {bridgeLinks.map((link) => (
                    <li key={link.name}>
                        <a
                            className="group flex min-h-32 flex-col items-center justify-center gap-4 rounded-2xl border border-stone-200 bg-stone-900 p-5 text-center text-white shadow-sm transition motion-reduce:transition-none hover:-translate-y-0.5 hover:border-amber-400 hover:shadow-md motion-reduce:hover:translate-y-0"
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
                                className="size-10 object-contain"
                            />
                            <span className="font-medium">
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

            <dl className="mt-12 grid gap-4 border-t border-stone-200 pt-8 sm:grid-cols-2">
                {teams.map((team) => (
                    <div
                        key={team.label}
                        className="rounded-xl bg-white p-5 ring-1 ring-stone-200"
                    >
                        <dt className="text-sm text-stone-500">{team.label}</dt>
                        <dd className="mt-1 text-xl font-semibold text-stone-950">
                            {team.name}
                        </dd>
                    </div>
                ))}
            </dl>
        </div>
    );
}
