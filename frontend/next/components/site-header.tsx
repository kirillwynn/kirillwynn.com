"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { ThemeToggle } from "@/components/theme-toggle";
import { authApiPaths, safeReturnTo } from "@/lib/auth";
import { PUBLIC_URL_CHANGE_EVENT, queryFromLocation } from "@/lib/feed-browser";
import { scheduleFeedScrollRestoration } from "@/lib/feed-scroll-cache";

export function SiteHeaderFallback() {
    return (
        <header className="site-header">
            <div className="site-container site-header__inner">
                <nav
                    className="site-navigation"
                    aria-label="Primary navigation"
                >
                    <div className="site-header__controls">
                        <Link
                            className="nav-link"
                            href="/"
                            onClick={() => {
                                scheduleFeedScrollRestoration("");
                            }}
                            prefetch
                            scroll={false}
                        >
                            Feed
                        </Link>
                        <Link className="nav-link" href="/bridge" prefetch>
                            Bridge
                        </Link>
                        <ThemeToggle />
                        <div className="account-slot">
                            <span
                                aria-label="Loading account"
                                className="account-placeholder"
                                role="status"
                            >
                                Account
                            </span>
                        </div>
                    </div>
                </nav>
            </div>
        </header>
    );
}

export function SiteHeader() {
    const { clearSessionCache, me, refresh, status } = useAuth();
    const pathname = usePathname();
    const [menuOpen, setMenuOpen] = useState(false);
    const [loggingOut, setLoggingOut] = useState(false);
    const [returnTo, setReturnTo] = useState("/");
    const menuRef = useRef<HTMLDivElement>(null);
    const triggerRef = useRef<HTMLButtonElement>(null);

    useEffect(() => {
        setMenuOpen(false);
        const updateReturnTo = () => {
            setReturnTo(
                safeReturnTo(
                    `${window.location.pathname}${window.location.search}`,
                ),
            );
        };
        const restoreFeedOnHistory = () => {
            updateReturnTo();
            if (window.location.pathname === "/") {
                scheduleFeedScrollRestoration(
                    queryFromLocation(window.location),
                );
            }
        };
        updateReturnTo();
        if (window.location.pathname === "/") {
            scheduleFeedScrollRestoration(queryFromLocation(window.location));
        }
        window.addEventListener("popstate", restoreFeedOnHistory);
        window.addEventListener(PUBLIC_URL_CHANGE_EVENT, updateReturnTo);
        return () => {
            window.removeEventListener("popstate", restoreFeedOnHistory);
            window.removeEventListener(PUBLIC_URL_CHANGE_EVENT, updateReturnTo);
        };
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
            const response = await fetch(authApiPaths.logout, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "X-CSRFToken": me.csrf_token,
                    Accept: "application/json",
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({}),
            });
            if (response.ok) {
                clearSessionCache();
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
                        <Link
                            className="nav-link"
                            aria-current={pathname === "/" ? "page" : undefined}
                            href="/"
                            onClick={() => {
                                scheduleFeedScrollRestoration("");
                            }}
                            prefetch
                            scroll={false}
                        >
                            Feed
                        </Link>
                        <Link
                            className="nav-link"
                            aria-current={
                                pathname === "/bridge" ? "page" : undefined
                            }
                            href="/bridge"
                            prefetch
                        >
                            Bridge
                        </Link>
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
                                            <Link
                                                className="nav-link"
                                                aria-current={
                                                    pathname === "/account"
                                                        ? "page"
                                                        : undefined
                                                }
                                                href="/account"
                                                prefetch={false}
                                                role="menuitem"
                                            >
                                                Account
                                            </Link>
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
                                <Link
                                    className="nav-link justify-center font-semibold"
                                    aria-current={
                                        pathname === "/login"
                                            ? "page"
                                            : undefined
                                    }
                                    href={`/login?next=${encodeURIComponent(returnTo)}`}
                                    prefetch={false}
                                >
                                    Login
                                </Link>
                            )}
                        </div>
                    </div>
                </nav>
            </div>
        </header>
    );
}
