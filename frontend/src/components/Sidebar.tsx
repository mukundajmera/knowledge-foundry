/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — Sidebar Component
   Conversation history grouped by date with search
   ═══════════════════════════════════════════════════════════ */

"use client";

import { useState, useMemo } from "react";
import type { Conversation } from "@/lib/types";

interface GroupedConversations {
    today: Conversation[];
    yesterday: Conversation[];
    thisWeek: Conversation[];
    older: Conversation[];
}

interface SidebarProps {
    grouped: GroupedConversations;
    activeId: string | null;
    isOpen: boolean;
    onSelect: (id: string) => void;
    onNew: () => void;
    onDelete: (id: string) => void;
    onClose: () => void;
}

function formatTime(ts: number): string {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function filterGroup(items: Conversation[], query: string): Conversation[] {
    if (!query) return items;
    const q = query.toLowerCase();
    return items.filter((c) => c.title.toLowerCase().includes(q));
}

function ConversationGroup({
    title,
    items,
    activeId,
    onSelect,
    onDelete,
}: {
    title: string;
    items: Conversation[];
    activeId: string | null;
    onSelect: (id: string) => void;
    onDelete: (id: string) => void;
}) {
    if (items.length === 0) return null;
    return (
        <div className="sidebar-section">
            <div className="sidebar-section-title">{title}</div>
            {items.map((conv) => (
                <div
                    key={conv.id}
                    className={`conversation-item ${conv.id === activeId ? "active" : ""}`}
                    onClick={() => onSelect(conv.id)}
                    role="button"
                    tabIndex={0}
                    aria-label={`Open conversation: ${conv.title}`}
                    onKeyDown={(e) => { if (e.key === "Enter") onSelect(conv.id); }}
                >
                    <span className="conversation-item-icon">💬</span>
                    <span className="conversation-item-text">{conv.title}</span>
                    <span className="conversation-item-time">{formatTime(conv.updatedAt)}</span>
                    <button
                        className="conversation-item-delete"
                        onClick={(e) => { e.stopPropagation(); onDelete(conv.id); }}
                        aria-label={`Delete conversation: ${conv.title}`}
                    >
                        ✕
                    </button>
                </div>
            ))}
        </div>
    );
}

export default function Sidebar({
    grouped,
    activeId,
    isOpen,
    onSelect,
    onNew,
    onDelete,
    onClose,
}: SidebarProps) {
    const [searchQuery, setSearchQuery] = useState("");

    const filtered = useMemo(
        () => ({
            today: filterGroup(grouped.today, searchQuery),
            yesterday: filterGroup(grouped.yesterday, searchQuery),
            thisWeek: filterGroup(grouped.thisWeek, searchQuery),
            older: filterGroup(grouped.older, searchQuery),
        }),
        [grouped, searchQuery]
    );

    const totalResults =
        filtered.today.length +
        filtered.yesterday.length +
        filtered.thisWeek.length +
        filtered.older.length;

    return (
        <>
            <div
                className={`sidebar-overlay ${isOpen ? "visible" : ""}`}
                onClick={onClose}
                aria-hidden="true"
            />
            <aside className={`sidebar ${isOpen ? "open" : ""}`} role="navigation" aria-label="Conversation history">
                <div className="sidebar-header">
                    <button className="new-chat-btn" onClick={onNew} id="new-chat-btn">
                        <span>＋</span>
                        <span>New conversation</span>
                    </button>
                </div>

                {/* Search */}
                <div className="sidebar-search">
                    <input
                        type="text"
                        className="sidebar-search-input"
                        placeholder="Search conversations…"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        aria-label="Search conversations"
                        id="sidebar-search"
                    />
                    {searchQuery && (
                        <button
                            className="sidebar-search-clear"
                            onClick={() => setSearchQuery("")}
                            aria-label="Clear search"
                        >
                            ✕
                        </button>
                    )}
                </div>

                <div className="sidebar-list">
                    {searchQuery && totalResults === 0 ? (
                        <div className="sidebar-empty">
                            No conversations match &ldquo;{searchQuery}&rdquo;
                        </div>
                    ) : (
                        <>
                            <ConversationGroup
                                title="Today"
                                items={filtered.today}
                                activeId={activeId}
                                onSelect={onSelect}
                                onDelete={onDelete}
                            />
                            <ConversationGroup
                                title="Yesterday"
                                items={filtered.yesterday}
                                activeId={activeId}
                                onSelect={onSelect}
                                onDelete={onDelete}
                            />
                            <ConversationGroup
                                title="This Week"
                                items={filtered.thisWeek}
                                activeId={activeId}
                                onSelect={onSelect}
                                onDelete={onDelete}
                            />
                            <ConversationGroup
                                title="Older"
                                items={filtered.older}
                                activeId={activeId}
                                onSelect={onSelect}
                                onDelete={onDelete}
                            />
                        </>
                    )}
                </div>
            </aside>
        </>
    );
}
