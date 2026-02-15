/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — Theme Toggle Component
   Switches between dark (default) and light themes.
   Persists to localStorage, respects prefers-color-scheme.
   ═══════════════════════════════════════════════════════════ */

"use client";

import { useState, useEffect, useCallback } from "react";

type Theme = "dark" | "light";

const STORAGE_KEY = "kf-theme";

function getInitialTheme(): Theme {
    if (typeof window === "undefined") return "dark";

    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;

    // Respect OS preference on first visit
    if (window.matchMedia?.("(prefers-color-scheme: light)").matches) {
        return "light";
    }
    return "dark";
}

export default function ThemeToggle() {
    const [theme, setTheme] = useState<Theme>("dark");
    const [mounted, setMounted] = useState(false);

    // Hydrate from localStorage only on mount (avoid SSR mismatch)
    useEffect(() => {
        setTheme(getInitialTheme());
        setMounted(true);
    }, []);

    // Apply theme to DOM
    useEffect(() => {
        if (!mounted) return;
        document.documentElement.setAttribute("data-theme", theme);
        localStorage.setItem(STORAGE_KEY, theme);
    }, [theme, mounted]);

    const toggle = useCallback(() => {
        setTheme((prev) => (prev === "dark" ? "light" : "dark"));
    }, []);

    // Don't render icon until mounted to prevent flash
    if (!mounted) {
        return (
            <button className="icon-btn" aria-label="Toggle theme" style={{ opacity: 0 }}>
                🌙
            </button>
        );
    }

    return (
        <button
            className="icon-btn theme-toggle"
            onClick={toggle}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            title={`${theme === "dark" ? "Light" : "Dark"} mode`}
            id="theme-toggle-btn"
        >
            <span
                className="theme-toggle-icon"
                key={theme}
                style={{
                    display: "inline-block",
                    animation: "themeFlip var(--duration-normal) var(--ease-out)",
                }}
            >
                {theme === "dark" ? "🌙" : "☀️"}
            </span>
        </button>
    );
}
