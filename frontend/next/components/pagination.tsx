import { feedHref, type FeedState } from "@/lib/feed-state";

export function Pagination({
    state,
    hasPrevious,
    hasNext,
}: {
    state: FeedState;
    hasPrevious: boolean;
    hasNext: boolean;
}) {
    const previousHref = feedHref({ ...state, page: state.page - 1 });
    const nextHref = feedHref({ ...state, page: state.page + 1 });

    return (
        <nav className="feed-pagination" aria-label="Feed pagination">
            {hasPrevious ? (
                <a className="button-link" rel="prev" href={previousHref}>
                    ← Previous
                </a>
            ) : (
                <span aria-hidden="true" />
            )}
            <span className="feed-page-number">Page {state.page}</span>
            {hasNext ? (
                <a className="button-link" rel="next" href={nextHref}>
                    Next →
                </a>
            ) : (
                <span aria-hidden="true" />
            )}
        </nav>
    );
}
