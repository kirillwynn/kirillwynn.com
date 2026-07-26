export function SiteHeader() {
    return (
        <header className="border-b border-stone-200 bg-white/95">
            <div className="site-container flex min-h-16 items-center justify-between gap-5">
                <a
                    href="/"
                    className="rounded-sm text-base font-semibold tracking-tight text-stone-950"
                    aria-label="Kirill Wynn home"
                >
                    kirillwynn.com
                </a>
                <nav
                    className="flex items-center gap-1 sm:gap-3"
                    aria-label="Primary navigation"
                >
                    <a className="nav-link" href="/">
                        Feed
                    </a>
                    <a className="nav-link" href="/bridge">
                        Bridge
                    </a>
                    <button
                        type="button"
                        disabled
                        aria-disabled="true"
                        title="Login will be available in Milestone 5"
                        className="min-h-11 rounded-lg px-3 text-sm font-medium text-stone-400"
                    >
                        Login
                    </button>
                </nav>
            </div>
        </header>
    );
}
