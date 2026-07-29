"use client";

import { usePathname } from "next/navigation";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { ThemeToggle } from "@/components/theme-toggle";
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
        <header className="site-header">
            <div className="site-container site-header__inner">
                <nav
                    className="site-navigation"
                    aria-label="Primary navigation"
                >
                    <div className="site-header__controls">
                        <a
                            className="nav-link"
                            aria-current={pathname === "/" ? "page" : undefined}
                            href="/"
                        >
                            Feed
                        </a>
                        <a
                            className="nav-link"
                            aria-current={
                                pathname === "/bridge" ? "page" : undefined
                            }
                            href="/bridge"
                        >
                            Bridge
                        </a>
                        <ThemeToggle />
                        <div className="account-slot" ref={menuRef}>
                            {status === "loading" ? (
                                <span
                                    className="account-placeholder"
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
                                        className="account-trigger"
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
                                            className="account-menu"
                                            role="menu"
                                            aria-label="User menu"
                                        >
                                            <a
                                                className="nav-link"
                                                aria-current={
                                                    pathname === "/account"
                                                        ? "page"
                                                        : undefined
                                                }
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
                                    className="nav-link justify-center font-semibold"
                                    aria-current={
                                        pathname === "/login"
                                            ? "page"
                                            : undefined
                                    }
                                    href={`/login?next=${encodeURIComponent(returnTo)}`}
                                >
                                    Login
                                </a>
                            )}
                        </div>
                    </div>
                </nav>
            </div>
        </header>
    );
}
