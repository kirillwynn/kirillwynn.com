export default function Loading() {
    return (
        <div className="page-shell" role="status" aria-live="polite">
            <span className="sr-only">Loading content</span>
            <div className="skeleton-pulse" aria-hidden="true">
                <div className="feed-header">
                    <div className="skeleton-line w-16" />
                </div>
                <div className="feed-controls">
                    <div className="skeleton-block w-full" />
                    <div className="mt-3 flex gap-2">
                        <div className="skeleton-block w-16" />
                        <div className="skeleton-block w-24" />
                        <div className="skeleton-block w-20" />
                    </div>
                </div>
                <div className="feed-stream">
                    {[0, 1, 2].map((item) => (
                        <div className="feed-entry" key={item}>
                            <div className="skeleton-line w-40" />
                            <div className="mt-3 flex gap-4">
                                <div className="min-w-0 flex-1">
                                    <div className="skeleton-line w-3/5" />
                                    <div className="skeleton-line mt-3 w-full" />
                                    <div className="skeleton-line mt-2 w-4/5" />
                                </div>
                                <div className="skeleton-block feed-skeleton-image" />
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
