/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — Keyboard Shortcuts Modal
   Shows available keyboard shortcuts in a dismissible overlay
   ═══════════════════════════════════════════════════════════ */

"use client";

import { useEffect, useCallback } from "react";

interface Shortcut {
    keys: string[];
    description: string;
}

const SHORTCUTS: Shortcut[] = [
    { keys: ["/"], description: "Focus search input" },
    { keys: ["Ctrl", "Enter"], description: "Send query" },
    { keys: ["?"], description: "Open keyboard shortcuts" },
    { keys: ["Esc"], description: "Close modal / cancel" },
    { keys: ["N"], description: "New conversation" },
];

interface KeyboardShortcutsProps {
    isOpen: boolean;
    onClose: () => void;
}

export default function KeyboardShortcuts({ isOpen, onClose }: KeyboardShortcutsProps) {
    const handleKeyDown = useCallback(
        (e: KeyboardEvent) => {
            if (e.key === "Escape") {
                onClose();
            }
        },
        [onClose]
    );

    useEffect(() => {
        if (isOpen) {
            document.addEventListener("keydown", handleKeyDown);
            return () => document.removeEventListener("keydown", handleKeyDown);
        }
    }, [isOpen, handleKeyDown]);

    if (!isOpen) return null;

    return (
        <div
            className="shortcuts-overlay"
            onClick={onClose}
            role="dialog"
            aria-modal="true"
            aria-label="Keyboard shortcuts"
        >
            <div
                className="shortcuts-modal"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="shortcuts-header">
                    <h2 className="shortcuts-title">⌨️ Keyboard Shortcuts</h2>
                    <button
                        className="shortcuts-close"
                        onClick={onClose}
                        aria-label="Close shortcuts"
                    >
                        ✕
                    </button>
                </div>
                <div className="shortcuts-list">
                    {SHORTCUTS.map((s) => (
                        <div key={s.description} className="shortcut-row">
                            <div className="shortcut-keys">
                                {s.keys.map((k, i) => (
                                    <span key={k}>
                                        <kbd className="shortcut-key">{k}</kbd>
                                        {i < s.keys.length - 1 && (
                                            <span className="shortcut-plus">+</span>
                                        )}
                                    </span>
                                ))}
                            </div>
                            <span className="shortcut-desc">{s.description}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
