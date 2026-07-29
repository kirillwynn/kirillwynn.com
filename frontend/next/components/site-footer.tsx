"use client";

import { usePathname } from "next/navigation";

import { teams } from "@/lib/bridge";

export function FooterContent({
    showBridgeTeams,
}: {
    showBridgeTeams: boolean;
}) {
    return (
        <footer className="site-footer">
            <div className="site-container site-footer__inner">
                <div className="site-footer__primary">
                    {showBridgeTeams ? (
                        <dl
                            className="bridge-team-context"
                            aria-label="Team history"
                        >
                            {teams.map((team) => (
                                <div key={team.label}>
                                    <dt>{team.label}</dt>
                                    <dd>{team.name}</dd>
                                </div>
                            ))}
                        </dl>
                    ) : (
                        <p>© {new Date().getUTCFullYear()} Kirill Wynn</p>
                    )}
                </div>
            </div>
        </footer>
    );
}

export function SiteFooter() {
    const pathname = usePathname();

    return <FooterContent showBridgeTeams={pathname === "/bridge"} />;
}
