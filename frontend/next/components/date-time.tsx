const dateFormatter = new Intl.DateTimeFormat("en", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
});

export function DateTime({ value, label }: { value: string; label?: string }) {
    return (
        <time dateTime={value}>
            {label}
            {dateFormatter.format(new Date(value))}
        </time>
    );
}
