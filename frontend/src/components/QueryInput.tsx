/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — Query Input Component
   Input bar with advanced options, file upload, and keyboard shortcuts
   ═══════════════════════════════════════════════════════════ */

"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import FileUpload from "@/components/FileUpload";
import type { QueryOptions, FileAttachment } from "@/lib/types";

interface QueryInputProps {
    onSend: (query: string, options: QueryOptions) => void;
    isStreaming: boolean;
    onStop: () => void;
}

const SUGGESTIONS = [
    "What is our data retention policy?",
    "Explain the security architecture",
    "What compliance frameworks do we follow?",
];

export default function QueryInput({ onSend, isStreaming, onStop }: QueryInputProps) {
    const [query, setQuery] = useState("");
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [files, setFiles] = useState<FileAttachment[]>([]);
    const [options, setOptions] = useState<QueryOptions>({
        model: "auto",
        deepSearch: false,
        multiHop: false,
    });
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Auto-resize textarea
    useEffect(() => {
        const el = textareaRef.current;
        if (el) {
            el.style.height = "auto";
            el.style.height = Math.min(el.scrollHeight, 200) + "px";
        }
    }, [query]);

    // Focus on "/" key
    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if (e.key === "/" && document.activeElement === document.body) {
                e.preventDefault();
                textareaRef.current?.focus();
            }
        };
        window.addEventListener("keydown", handler);
        return () => window.removeEventListener("keydown", handler);
    }, []);

    const handleAddFile = useCallback((file: FileAttachment) => {
        setFiles((prev) => [...prev, file]);
    }, []);

    const handleRemoveFile = useCallback((index: number) => {
        setFiles((prev) => prev.filter((_, i) => i !== index));
    }, []);

    const handleSend = useCallback(() => {
        if (!query.trim() || isStreaming) return;
        const sendOptions = { ...options, files: files.length > 0 ? files : undefined };
        onSend(query.trim(), sendOptions);
        setQuery("");
        setFiles([]);
    }, [query, options, files, isStreaming, onSend]);

    const handleKeyDown = useCallback(
        (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                handleSend();
            }
        },
        [handleSend]
    );

    return (
        <div className="input-container">
            <div className="input-wrapper">
                {/* Suggestions (show when no messages) */}
                {!query && !isStreaming && (
                    <div className="suggestions">
                        {SUGGESTIONS.map((s) => (
                            <button
                                key={s}
                                className="suggestion-chip"
                                onClick={() => { setQuery(s); textareaRef.current?.focus(); }}
                            >
                                💡 {s}
                            </button>
                        ))}
                    </div>
                )}

                {/* Advanced options */}
                <button
                    className="advanced-toggle"
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    aria-expanded={showAdvanced}
                >
                    ⚙️ Advanced {showAdvanced ? "▲" : "▼"}
                </button>

                {showAdvanced && (
                    <div className="advanced-panel" role="region" aria-label="Advanced query options">
                        <div className="option-group">
                            <label className="option-label" htmlFor="model-select">Model</label>
                            <select
                                id="model-select"
                                className="option-select"
                                value={options.model}
                                onChange={(e) => setOptions({ ...options, model: e.target.value as QueryOptions["model"] })}
                            >
                                <option value="auto">Auto</option>
                                <option value="haiku">Haiku (Fast)</option>
                                <option value="sonnet">Sonnet (Balanced)</option>
                                <option value="opus">Opus (Best)</option>
                            </select>
                        </div>

                        <div className="option-group">
                            <span className="option-label">Deep Search</span>
                            <label className="toggle-switch">
                                <div
                                    className={`toggle-track ${options.deepSearch ? "active" : ""}`}
                                    onClick={() => setOptions({ ...options, deepSearch: !options.deepSearch })}
                                    role="switch"
                                    aria-checked={options.deepSearch}
                                    tabIndex={0}
                                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") setOptions({ ...options, deepSearch: !options.deepSearch }); }}
                                >
                                    <div className="toggle-thumb" />
                                </div>
                            </label>
                        </div>

                        <div className="option-group">
                            <span className="option-label">Multi-hop</span>
                            <label className="toggle-switch">
                                <div
                                    className={`toggle-track ${options.multiHop ? "active" : ""}`}
                                    onClick={() => setOptions({ ...options, multiHop: !options.multiHop })}
                                    role="switch"
                                    aria-checked={options.multiHop}
                                    tabIndex={0}
                                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") setOptions({ ...options, multiHop: !options.multiHop }); }}
                                >
                                    <div className="toggle-thumb" />
                                </div>
                            </label>
                        </div>
                    </div>
                )}

                {/* File upload area */}
                <FileUpload
                    files={files}
                    onAdd={handleAddFile}
                    onRemove={handleRemoveFile}
                    disabled={isStreaming}
                />

                {/* Input box */}
                <div
                    className="query-input-box"
                    onDragOver={(e) => { e.preventDefault(); }}
                    onDrop={(e) => {
                        e.preventDefault();
                        const dropped = e.dataTransfer.files;
                        for (let i = 0; i < dropped.length; i++) {
                            handleAddFile({
                                name: dropped[i].name,
                                size: dropped[i].size,
                                type: dropped[i].type,
                                file: dropped[i],
                            });
                        }
                    }}
                >
                    <textarea
                        ref={textareaRef}
                        className="query-input"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask a question… (Ctrl+Enter to send, / to focus)"
                        rows={1}
                        aria-label="Query input"
                        id="query-input"
                        disabled={isStreaming}
                    />
                    {isStreaming ? (
                        <button className="send-btn" onClick={onStop} aria-label="Stop generating">
                            ⬜
                        </button>
                    ) : (
                        <button
                            className="send-btn"
                            onClick={handleSend}
                            disabled={!query.trim()}
                            aria-label="Send query"
                            id="send-btn"
                        >
                            →
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}
