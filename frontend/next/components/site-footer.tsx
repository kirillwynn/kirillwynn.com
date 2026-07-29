import { teams } from "@/lib/bridge";

export function FooterContent() {
    return (
        <footer className="site-footer">
            <div className="site-container site-footer__inner">
                <dl className="site-team-context" aria-label="Team history">
                    {teams.map((team) => (
                        <div key={team.label}>
                            <dt>{team.label}</dt>
                            <dd>{team.name}</dd>
                        </div>
                    ))}
                </dl>
            </div>
        </footer>
    );
}

export function SiteFooter() {
    return <FooterContent />;
}
