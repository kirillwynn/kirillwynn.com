import type { ProviderId } from "@/lib/auth";

const providerLabels: Record<ProviderId, string> = {
    google: "Google",
    github: "GitHub",
};

type ProviderFormProps = {
    available: boolean;
    csrfToken: string;
    next: string;
    process?: "login" | "connect";
    provider: ProviderId;
};

export function ProviderForm({
    available,
    csrfToken,
    next,
    process = "login",
    provider,
}: ProviderFormProps) {
    const label = providerLabels[provider];
    return (
        <form method="post" action={`/accounts/${provider}/login/`}>
            <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
            <input type="hidden" name="next" value={next} />
            <input type="hidden" name="process" value={process} />
            <button
                className="button-link w-full disabled:cursor-not-allowed disabled:text-stone-400"
                type="submit"
                disabled={!available || !csrfToken}
            >
                {available
                    ? `${process === "connect" ? "Connect" : "Continue with"} ${label}`
                    : `${label} unavailable`}
            </button>
        </form>
    );
}
