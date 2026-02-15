/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — Message Bubble Component
   Renders user/AI messages with markdown, citations,
   follow-ups, error banners, and regenerate
   ═══════════════════════════════════════════════════════════ */

"use client";

import { useState } from "react";
import ErrorBanner from "@/components/ErrorBanner";
import RoutingTrace from "@/components/RoutingTrace";
import type { Message, Citation } from "@/lib/types";

interface MessageBubbleProps {
    message: Message;
    onFollowUp?: (query: string) => void;
    onRegenerate?: (messageId: string) => void;
}

function formatTimestamp(ts: number): string {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/** Replace [n] citation markers with interactive badges */
function renderWithCitations(text: string, citations?: Citation[]): React.ReactNode[] {
    if (!citations || citations.length === 0) {
        return text.split("\n").map((line, i) => (
            <span key={i}>
                {renderMarkdownLine(line)}
                {i < text.split("\n").length - 1 && <br />}
            </span>
        ));
    }

    const parts = text.split(/(\[\d+\])/g);
    return parts.map((part, i) => {
        const match = part.match(/^\[(\d+)\]$/);
        if (match) {
            const idx = parseInt(match[1]) - 1;
            const citation = citations[idx];
            return (
                <span
                    key={i}
                    className="citation-marker"
                    title={citation?.title || `Source ${idx + 1}`}
                    role="button"
                    tabIndex={0}
                >
                    {match[1]}
                </span>
            );
        }
        // Handle newlines
        return part.split("\n").map((line, j) => (
            <span key={`${i}-${j}`}>
                {renderMarkdownLine(line)}
                {j < part.split("\n").length - 1 && <br />}
            </span>
        ));
    });
}

/** Simple markdown rendering for bold, italic, code, lists */
function renderMarkdownLine(text: string): React.ReactNode[] {
    const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g);
    return parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
            return <strong key={i}>{part.slice(2, -2)}</strong>;
        }
        if (part.startsWith("`") && part.endsWith("`")) {
            return <code key={i}>{part.slice(1, -1)}</code>;
        }
        if (part.startsWith("*") && part.endsWith("*")) {
            return <em key={i}>{part.slice(1, -1)}</em>;
        }
        return <span key={i}>{part}</span>;
    });
}

function confidenceLevel(c: number): "high" | "medium" | "low" {
    if (c >= 0.8) return "high";
    if (c >= 0.5) return "medium";
    return "low";
}

export default function MessageBubble({ message, onFollowUp, onRegenerate }: MessageBubbleProps) {
    const [showSources, setShowSources] = useState(false);
    const [feedback, setFeedback] = useState<"up" | "down" | null>(null);

    const isAI = message.role === "assistant";

    return (
        <div className="message" role="article" aria-label={`${isAI ? "AI" : "You"}: ${message.content.slice(0, 50)}`}>
            <div className={`message-avatar ${isAI ? "ai" : "user"}`}>
                {isAI ? "✦" : "U"}
            </div>
            <div className="message-content">
                <div className="message-header">
                    <span className="message-sender">{isAI ? "Knowledge Foundry" : "You"}</span>
                    <span className="message-time">{formatTimestamp(message.timestamp)}</span>
                    {isAI && message.model && (
                        <span className="message-badge">{message.model}</span>
                    )}
                </div>

                {/* Error banner (if present) */}
                {isAI && message.error && !message.isStreaming && (
                    <ErrorBanner
                        type={message.error.type}
                        retryAfterSeconds={message.error.retryAfterSeconds}
                        message={message.error.message}
                        onRetry={onRegenerate ? () => onRegenerate(message.id) : undefined}
                    />
                )}

                <div className="message-body">
                    {message.isStreaming ? (
                        <>
                            {renderWithCitations(message.content)}
                            <span className="typing-indicator">
                                <span className="typing-dot" />
                                <span className="typing-dot" />
                                <span className="typing-dot" />
                            </span>
                        </>
                    ) : (
                        renderWithCitations(message.content, message.citations)
                    )}
                </div>

                {/* Metadata bar + actions (AI only, after streaming) */}
                {isAI && !message.isStreaming && message.content && (
                    <>
                        <div className="answer-meta">
                            {message.confidence !== undefined && (
                                <div className="meta-item">
                                    <span className="meta-icon">📊</span>
                                    <span className={`confidence-badge ${confidenceLevel(message.confidence)}`}>
                                        {(message.confidence * 100).toFixed(0)}% confidence
                                    </span>
                                </div>
                            )}
                            {message.latency_ms !== undefined && (
                                <div className="meta-item">
                                    <span className="meta-icon">⚡</span>
                                    <span>{(message.latency_ms / 1000).toFixed(1)}s</span>
                                </div>
                            )}
                            {message.cost_usd !== undefined && (
                                <div className="meta-item">
                                    <span className="meta-icon">💰</span>
                                    <span>${message.cost_usd.toFixed(4)}</span>
                                </div>
                            )}
                        </div>

                        {/* Routing trace */}
                        {message.routing && (
                            <RoutingTrace routing={message.routing} />
                        )}

                        {/* Low confidence warning */}
                        {message.confidence !== undefined && message.confidence < 0.5 && !message.error && (
                            <div className="low-confidence-warning" role="alert">
                                ⚠️ Low confidence — please verify this response independently.
                            </div>
                        )}

                        {/* Action buttons */}
                        <div className="message-actions">
                            <button
                                className={`action-btn ${feedback === "up" ? "active" : ""}`}
                                onClick={() => setFeedback(feedback === "up" ? null : "up")}
                                aria-label="Thumbs up"
                            >
                                👍
                            </button>
                            <button
                                className={`action-btn ${feedback === "down" ? "active" : ""}`}
                                onClick={() => setFeedback(feedback === "down" ? null : "down")}
                                aria-label="Thumbs down"
                            >
                                👎
                            </button>
                            <button
                                className="action-btn"
                                onClick={() => navigator.clipboard?.writeText(message.content)}
                                aria-label="Copy response"
                            >
                                📋 Copy
                            </button>

                            {/* Regenerate */}
                            {onRegenerate && (
                                <button
                                    className="action-btn"
                                    onClick={() => onRegenerate(message.id)}
                                    aria-label="Regenerate response"
                                    id="regenerate-btn"
                                >
                                    🔄 Regenerate
                                </button>
                            )}

                            {/* Sources toggle */}
                            {message.citations && message.citations.length > 0 && (
                                <button
                                    className="sources-toggle"
                                    onClick={() => setShowSources(!showSources)}
                                    aria-expanded={showSources}
                                    aria-controls="sources-panel"
                                >
                                    📚 Sources ({message.citations.length}) {showSources ? "▲" : "▼"}
                                </button>
                            )}
                        </div>

                        {/* Sources panel */}
                        {showSources && message.citations && (
                            <div className="sources-panel" id="sources-panel" role="region" aria-label="Source citations">
                                {message.citations.map((cite, idx) => (
                                    <div key={idx} className="source-card">
                                        <div className="source-header">
                                            <span className="source-title">
                                                <span className="citation-marker">{idx + 1}</span>
                                                {cite.title}
                                            </span>
                                            <span className="source-relevance">
                                                {(cite.relevance_score * 100).toFixed(0)}%
                                            </span>
                                        </div>
                                        {cite.section && (
                                            <div className="source-excerpt">{cite.section}</div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}

                        {/* Follow-up suggestions */}
                        {message.followUps && message.followUps.length > 0 && (
                            <div className="follow-ups">
                                <div className="follow-ups-label">Follow-up questions:</div>
                                <div className="follow-ups-list">
                                    {message.followUps.map((q) => (
                                        <button
                                            key={q}
                                            className="follow-up-chip"
                                            onClick={() => onFollowUp?.(q)}
                                        >
                                            💬 {q}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}
