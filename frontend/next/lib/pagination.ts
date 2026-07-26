export function parsePageParam(
    value: string | string[] | undefined,
): number | null {
    if (value === undefined) {
        return 1;
    }
    if (Array.isArray(value) || !/^[1-9]\d*$/.test(value)) {
        return null;
    }
    const page = Number(value);
    return Number.isSafeInteger(page) ? page : null;
}
