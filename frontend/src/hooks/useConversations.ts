/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — Conversation State Hook
   Manages conversation history in localStorage
   ═══════════════════════════════════════════════════════════ */

"use client";

import { useState, useEffect, useCallback } from "react";
import type { Conversation, Message } from "@/lib/types";

const STORAGE_KEY = "kf_conversations";
const MAX_CONVERSATIONS = 50;

function generateId(): string {
    return `conv_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function loadConversations(): Conversation[] {
    if (typeof window === "undefined") return [];
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        return raw ? JSON.parse(raw) : [];
    } catch {
        return [];
    }
}

function saveConversations(conversations: Conversation[]) {
    if (typeof window === "undefined") return;
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations.slice(0, MAX_CONVERSATIONS)));
    } catch {
        // localStorage full
    }
}

export function useConversations() {
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [activeId, setActiveId] = useState<string | null>(null);

    // Load on mount
    useEffect(() => {
        const loaded = loadConversations();
        setConversations(loaded);
        if (loaded.length > 0) {
            setActiveId(loaded[0].id);
        }
    }, []);

    // Persist on change
    useEffect(() => {
        if (conversations.length > 0) {
            saveConversations(conversations);
        }
    }, [conversations]);

    const activeConversation = conversations.find((c) => c.id === activeId) || null;

    const createConversation = useCallback((): string => {
        const id = generateId();
        const conv: Conversation = {
            id,
            title: "New conversation",
            messages: [],
            createdAt: Date.now(),
            updatedAt: Date.now(),
        };
        setConversations((prev) => [conv, ...prev]);
        setActiveId(id);
        return id;
    }, []);

    const deleteConversation = useCallback(
        (id: string) => {
            setConversations((prev) => prev.filter((c) => c.id !== id));
            if (activeId === id) {
                setActiveId(null);
            }
        },
        [activeId]
    );

    const addMessage = useCallback(
        (conversationId: string, message: Message) => {
            setConversations((prev) =>
                prev.map((c) => {
                    if (c.id !== conversationId) return c;
                    const updated = {
                        ...c,
                        messages: [...c.messages, message],
                        updatedAt: Date.now(),
                    };
                    // Auto-title from first user message
                    if (
                        c.title === "New conversation" &&
                        message.role === "user"
                    ) {
                        updated.title = message.content.slice(0, 60) + (message.content.length > 60 ? "…" : "");
                    }
                    return updated;
                })
            );
        },
        []
    );

    const updateMessage = useCallback(
        (conversationId: string, messageId: string, updates: Partial<Message>) => {
            setConversations((prev) =>
                prev.map((c) => {
                    if (c.id !== conversationId) return c;
                    return {
                        ...c,
                        messages: c.messages.map((m) =>
                            m.id === messageId ? { ...m, ...updates } : m
                        ),
                        updatedAt: Date.now(),
                    };
                })
            );
        },
        []
    );

    // Group conversations by date
    const grouped = groupByDate(conversations);

    return {
        conversations,
        activeConversation,
        activeId,
        grouped,
        setActiveId,
        createConversation,
        deleteConversation,
        addMessage,
        updateMessage,
    };
}

// ─── Date grouping ───

interface GroupedConversations {
    today: Conversation[];
    yesterday: Conversation[];
    thisWeek: Conversation[];
    older: Conversation[];
}

function groupByDate(conversations: Conversation[]): GroupedConversations {
    const now = Date.now();
    const dayMs = 86400_000;
    const todayStart = new Date().setHours(0, 0, 0, 0);
    const yesterdayStart = todayStart - dayMs;
    const weekStart = todayStart - 7 * dayMs;

    return {
        today: conversations.filter((c) => c.updatedAt >= todayStart),
        yesterday: conversations.filter(
            (c) => c.updatedAt >= yesterdayStart && c.updatedAt < todayStart
        ),
        thisWeek: conversations.filter(
            (c) => c.updatedAt >= weekStart && c.updatedAt < yesterdayStart
        ),
        older: conversations.filter((c) => c.updatedAt < weekStart),
    };
}
