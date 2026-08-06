"use client";

import { useSearchParams } from "next/navigation";

import { AccountPanel } from "@/components/account-panel";
import { ProfileForm, SignupForm } from "@/components/local-auth-forms";
import { LoginPanel } from "@/components/login-panel";

function parameter(
    searchParameters: ReturnType<typeof useSearchParams>,
    name: string,
): string | undefined {
    const values = searchParameters.getAll(name);
    return values.length === 1 ? values[0] : undefined;
}

export function AccountRoutePanel() {
    const searchParameters = useSearchParams();
    return (
        <AccountPanel
            error={parameter(searchParameters, "error")}
            status={parameter(searchParameters, "status")}
        />
    );
}

export function LoginRoutePanel() {
    const searchParameters = useSearchParams();
    return (
        <LoginPanel
            error={parameter(searchParameters, "error")}
            next={parameter(searchParameters, "next")}
        />
    );
}

export function ProfileRouteForm() {
    const searchParameters = useSearchParams();
    return <ProfileForm next={parameter(searchParameters, "next")} />;
}

export function SignupRouteForm() {
    const searchParameters = useSearchParams();
    return <SignupForm next={parameter(searchParameters, "next")} />;
}
