export function PreviewBanner() {
    return (
        <aside
            className="mb-8 flex flex-col gap-3 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950 sm:flex-row sm:items-center sm:justify-between"
            aria-label="Draft preview"
        >
            <p>
                <strong>Draft preview.</strong> This immutable snapshot is
                private and is not the public post.
            </p>
            <a className="button-link shrink-0" href="/api/draft/disable">
                Exit preview
            </a>
        </aside>
    );
}
