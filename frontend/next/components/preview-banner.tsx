export function PreviewBanner() {
    return (
        <aside className="preview-banner" aria-label="Draft preview">
            <p>
                <strong>Draft Mode.</strong> An immutable snapshot remains
                private, is not the public post, and may expire.
            </p>
            <a className="button-link shrink-0" href="/api/draft/disable">
                Exit preview
            </a>
        </aside>
    );
}
