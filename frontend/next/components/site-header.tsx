"use client";

import { usePathname } from "next/navigation";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { safeReturnTo } from "@/lib/auth";

export function SiteHeader() {
    const { me, refresh, status } = useAuth();
    const pathname = usePathname();
    const [menuOpen, setMenuOpen] = useState(false);
    const [loggingOut, setLoggingOut] = useState(false);
    const [returnTo, setReturnTo] = useState("/");
    const menuRef = useRef<HTMLDivElement>(null);
    const triggerRef = useRef<HTMLButtonElement>(null);

    useEffect(() => {
        setMenuOpen(false);
        const current = `${pathname}${window.location.search}`;
        setReturnTo(safeReturnTo(current));
    }, [pathname]);

    useEffect(() => {
        if (!menuOpen) {
            return;
        }
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Escape") {
                setMenuOpen(false);
                triggerRef.current?.focus();
            }
        };
        const onPointerDown = (event: PointerEvent) => {
            if (
                menuRef.current &&
                !menuRef.current.contains(event.target as Node)
            ) {
                setMenuOpen(false);
            }
        };
        document.addEventListener("keydown", onKeyDown);
        document.addEventListener("pointerdown", onPointerDown);
        return () => {
            document.removeEventListener("keydown", onKeyDown);
            document.removeEventListener("pointerdown", onPointerDown);
        };
    }, [menuOpen]);

    async function submitLogout(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!me?.csrf_token || loggingOut) {
            return;
        }
        setLoggingOut(true);
        try {
            const response = await fetch("/api/auth/logout/", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "X-CSRFToken": me.csrf_token,
                    Accept: "application/json",
                },
            });
            if (response.ok) {
                window.location.assign(returnTo);
                return;
            }
            await refresh();
            setMenuOpen(false);
        } catch {
            await refresh();
            setMenuOpen(false);
        } finally {
            setLoggingOut(false);
        }
    }

    const authenticated = Boolean(me?.authenticated && me.user);

    return (
        <header className="border-b border-stone-200 bg-white/95">
            <div className="site-container flex min-h-16 items-center justify-between gap-3">
                <a
                    href="/"
                    className="rounded-sm text-base font-semibold tracking-tight text-stone-950"
                    aria-label="Kirill Wynn home"
                >
                    kirillwynn.com
                </a>
                <nav
                    className="flex items-center gap-0 sm:gap-3"
                    aria-label="Primary navigation"
                >
                    <a className="nav-link" href="/">
                        Feed
                    </a>
                    <a className="nav-link" href="/bridge">
                        Bridge
                    </a>
                    <div
                        className="relative flex min-w-20 justify-end"
                        ref={menuRef}
                    >
                        {status === "loading" ? (
                            <span
                                className="inline-flex min-h-11 min-w-20 items-center justify-center text-sm text-stone-500"
                                role="status"
                                aria-label="Loading account"
                            >
                                Account
                            </span>
                        ) : authenticated && me?.user ? (
                            <>
                                <button
                                    ref={triggerRef}
                                    type="button"
                                    className="inline-flex min-h-11 max-w-36 items-center rounded-lg px-3 text-sm font-semibold text-stone-800 hover:bg-stone-100"
                                    aria-expanded={menuOpen}
                                    aria-haspopup="menu"
                                    onClick={() => {
                                        setMenuOpen((open) => !open);
                                    }}
                                >
                                    <span className="truncate">
                                        {me.user.display_name}
                                    </span>
                                </button>
                                {menuOpen ? (
                                    <div
                                        className="absolute right-0 top-12 z-40 grid min-w-48 gap-1 rounded-xl border border-stone-200 bg-white p-2 shadow-lg"
                                        role="menu"
                                        aria-label="User menu"
                                    >
                                        <a
                                            className="nav-link"
                                            href="/account"
                                            role="menuitem"
                                        >
                                            Account
                                        </a>
                                        <form
                                            onSubmit={(event) => {
                                                void submitLogout(event);
                                            }}
                                        >
                                            <button
                                                className="nav-link w-full justify-start"
                                                type="submit"
                                                role="menuitem"
                                                disabled={loggingOut}
                                            >
                                                {loggingOut
                                                    ? "Logging out…"
                                                    : "Logout"}
                                            </button>
                                        </form>
                                    </div>
                                ) : null}
                            </>
                        ) : (
                            <a
                                className="nav-link min-w-20 justify-center font-semibold"
                                href={`/login?next=${encodeURIComponent(returnTo)}`}
                            >
                                Login
                            </a>
                        )}
                    </div>
                </nav>
            </div>
        </header>
    );
}
