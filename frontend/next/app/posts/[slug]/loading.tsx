export default function PostLoading() {
    return (
        <div
            className="mx-auto max-w-3xl skeleton-pulse"
            role="status"
            aria-live="polite"
        >
            <span className="sr-only">Loading post</span>
            <div aria-hidden="true">
                <div className="skeleton-line w-14" />
                <div className="skeleton-block mt-4 h-12 w-4/5" />
                <div className="skeleton-line mt-5 w-full" />
                <div className="skeleton-line mt-2 w-3/4" />
                <div className="mt-12 space-y-3">
                    <div className="skeleton-line w-full" />
                    <div className="skeleton-line w-full" />
                    <div className="skeleton-line w-5/6" />
                    <div className="skeleton-line w-full" />
                </div>
            </div>
        </div>
    );
}
