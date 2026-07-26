export function SiteFooter() {
    return (
        <footer className="mt-auto border-t border-stone-200">
            <div className="site-container flex flex-col gap-2 py-8 text-sm text-stone-500 sm:flex-row sm:items-center sm:justify-between">
                <p>© {new Date().getUTCFullYear()} Kirill Wynn</p>
                <p>Writing about software, systems, and the work between.</p>
            </div>
        </footer>
    );
}
