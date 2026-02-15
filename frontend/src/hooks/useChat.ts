/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — Chat State Hook
   Manages streaming, sending, regeneration, and message state
   ═══════════════════════════════════════════════════════════ */

"use client";

import { useState, useCallback, useRef } from "react";
import { streamQuery } from "@/lib/api";
import type { Message, QueryOptions, RAGResponse } from "@/lib/types";

function generateMessageId(): string {
    return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

/** Generate simple follow-up suggestions based on the response */
function generateFollowUps(answer: string): string[] {
    const followUps: string[] = [];
    if (answer.length > 100) {
        followUps.push("Can you explain this in simpler terms?");
    }
    if (answer.includes("[1]") || answer.includes("[2]")) {
        followUps.push("What are the primary sources for this?");
    }
    followUps.push("What are the implications of this?");
    return followUps.slice(0, 3);
}

/** Parse API error responses into structured error types */
function parseAPIError(err: Error): NonNullable<Message["error"]> {
    const msg = err.message || "";
    if (msg.includes("429")) {
        const retryMatch = msg.match(/(\d+)/);
        return {
            type: "rate_limit",
            retryAfterSeconds: retryMatch ? parseInt(retryMatch[1]) : 60,
            message: "You've hit the rate limit. Please wait before sending another query.",
        };
    }
    if (msg.includes("404") || msg.includes("no results") || msg.includes("No results")) {
        return {
            type: "no_results",
            message: "No relevant documents found for your query.",
        };
    }
    return {
        type: "system_error",
        message: msg || "An unexpected error occurred.",
    };
}

interface UseChatOptions {
    onAddMessage: (conversationId: string, message: Message) => void;
    onUpdateMessage: (conversationId: string, messageId: string, updates: Partial<Message>) => void;
    conversations?: { id: string; messages: Message[] }[];
}

export function useChat({ onAddMessage, onUpdateMessage, conversations }: UseChatOptions) {
    const [isStreaming, setIsStreaming] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const abortRef = useRef<AbortController | null>(null);

    const send = useCallback(
        async (query: string, conversationId: string, options?: QueryOptions) => {
            if (!query.trim() || isStreaming) return;

            setError(null);
            setIsStreaming(true);

            // Add user message
            const userMsg: Message = {
                id: generateMessageId(),
                role: "user",
                content: query.trim(),
                timestamp: Date.now(),
            };
            onAddMessage(conversationId, userMsg);

            // Add placeholder AI message
            const aiMsgId = generateMessageId();
            const aiMsg: Message = {
                id: aiMsgId,
                role: "assistant",
                content: "",
                timestamp: Date.now(),
                isStreaming: true,
            };
            onAddMessage(conversationId, aiMsg);

            // Stream response
            const abort = new AbortController();
            abortRef.current = abort;

            try {
                await streamQuery(
                    query,
                    // onChunk — update message content progressively
                    (text: string) => {
                        onUpdateMessage(conversationId, aiMsgId, { content: text });
                    },
                    // onComplete — finalize with metadata + follow-ups
                    (response: RAGResponse) => {
                        const followUps = generateFollowUps(response.text);
                        const confidence = response.llm_response?.confidence;
                        onUpdateMessage(conversationId, aiMsgId, {
                            content: response.text,
                            citations: response.citations,
                            confidence,
                            latency_ms: response.total_latency_ms,
                            cost_usd: response.llm_response?.cost_usd,
                            model: response.llm_response?.tier,
                            isStreaming: false,
                            followUps,
                            error:
                                confidence !== undefined && confidence < 0.3
                                    ? { type: "low_confidence" }
                                    : undefined,
                        });
                    },
                    // onError — parse into structured error
                    (err: Error) => {
                        const parsedError = parseAPIError(err);
                        onUpdateMessage(conversationId, aiMsgId, {
                            content: parsedError.type === "rate_limit"
                                ? ""
                                : `⚠️ ${err.message}`,
                            isStreaming: false,
                            error: parsedError,
                        });
                        setError(err.message);
                    },
                    {
                        model: options?.model,
                        signal: abort.signal,
                    }
                );
            } catch (err) {
                setError(err instanceof Error ? err.message : "Unknown error");
            } finally {
                setIsStreaming(false);
                abortRef.current = null;
            }
        },
        [isStreaming, onAddMessage, onUpdateMessage]
    );

    const regenerate = useCallback(
        async (conversationId: string, messageId: string) => {
            // Find the conversation and the user message before this AI message
            const conv = conversations?.find((c) => c.id === conversationId);
            if (!conv) return;

            const aiIndex = conv.messages.findIndex((m) => m.id === messageId);
            if (aiIndex <= 0) return;

            const userMsg = conv.messages[aiIndex - 1];
            if (userMsg.role !== "user") return;

            // Clear the AI message content and re-stream
            onUpdateMessage(conversationId, messageId, {
                content: "",
                isStreaming: true,
                error: undefined,
                followUps: undefined,
            });

            setIsStreaming(true);
            const abort = new AbortController();
            abortRef.current = abort;

            try {
                await streamQuery(
                    userMsg.content,
                    (text: string) => {
                        onUpdateMessage(conversationId, messageId, { content: text });
                    },
                    (response: RAGResponse) => {
                        const followUps = generateFollowUps(response.text);
                        onUpdateMessage(conversationId, messageId, {
                            content: response.text,
                            citations: response.citations,
                            confidence: response.llm_response?.confidence,
                            latency_ms: response.total_latency_ms,
                            cost_usd: response.llm_response?.cost_usd,
                            model: response.llm_response?.tier,
                            isStreaming: false,
                            followUps,
                        });
                    },
                    (err: Error) => {
                        onUpdateMessage(conversationId, messageId, {
                            content: `⚠️ ${err.message}`,
                            isStreaming: false,
                            error: parseAPIError(err),
                        });
                    },
                    { signal: abort.signal }
                );
            } catch (err) {
                setError(err instanceof Error ? err.message : "Unknown error");
            } finally {
                setIsStreaming(false);
                abortRef.current = null;
            }
        },
        [conversations, onUpdateMessage]
    );

    const stop = useCallback(() => {
        abortRef.current?.abort();
        setIsStreaming(false);
    }, []);

    return { send, stop, regenerate, isStreaming, error };
}
