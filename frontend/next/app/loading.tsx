export default function Loading() {
    return (
        <div className="mx-auto max-w-4xl" role="status" aria-live="polite">
            <span className="sr-only">Loading content</span>
            <div className="motion-safe:animate-pulse motion-reduce:animate-none">
                <div className="h-4 w-28 rounded bg-stone-200" />
                <div className="mt-5 h-12 max-w-2xl rounded bg-stone-200" />
                <div className="mt-4 h-6 max-w-xl rounded bg-stone-200" />
                <div className="mt-14 space-y-4">
                    <div className="h-8 max-w-lg rounded bg-stone-200" />
                    <div className="h-4 rounded bg-stone-200" />
                    <div className="h-4 w-4/5 rounded bg-stone-200" />
                </div>
            </div>
        </div>
    );
}
