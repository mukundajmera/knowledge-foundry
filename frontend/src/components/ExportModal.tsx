/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — Export Modal Component
   Allows users to export conversations and messages to various formats
   ═══════════════════════════════════════════════════════════ */

"use client";

import { useState, useEffect, useCallback } from "react";
import { apiClient } from "@/lib/api";
import type {
    ExportFormatInfo,
    ExportEntityType,
    ExportFormatId,
    ExportOptions,
    Conversation,
    Message,
} from "@/lib/types";

interface ExportModalProps {
    isOpen: boolean;
    onClose: () => void;
    entityType: ExportEntityType;
    entityName: string;
    entityData: Conversation | Message | Record<string, unknown>;
}

const DEFAULT_OPTIONS: ExportOptions = {
    include_metadata: true,
    include_citations: true,
    anonymize_user: false,
    include_raw_json_appendix: false,
    locale: "en-US",
};

export default function ExportModal({
    isOpen,
    onClose,
    entityType,
    entityName,
    entityData,
}: ExportModalProps) {
    const [formats, setFormats] = useState<ExportFormatInfo[]>([]);
    const [selectedFormat, setSelectedFormat] = useState<ExportFormatId>("markdown");
    const [options, setOptions] = useState<ExportOptions>(DEFAULT_OPTIONS);
    const [isLoading, setIsLoading] = useState(false);
    const [isGenerating, setIsGenerating] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const loadFormats = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const response = await apiClient.listExportFormats(entityType);
            setFormats(response.formats);
            // Select first available format
            if (response.formats.length > 0) {
                setSelectedFormat(response.formats[0].format_id);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load formats");
        } finally {
            setIsLoading(false);
        }
    }, [entityType]);

    // Load available formats when modal opens
    useEffect(() => {
        if (isOpen) {
            loadFormats();
        }
    }, [isOpen, loadFormats]);

    const handleExport = useCallback(async () => {
        setIsGenerating(true);
        setError(null);

        try {
            const { blob, filename } = await apiClient.generateExportWithFilename({
                entity_type: entityType,
                entity_id: (entityData as { id?: string }).id || "export",
                format_id: selectedFormat,
                options,
                entity_data: entityData as Record<string, unknown>,
            });

            // Create download link
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);

            // Close modal on success
            onClose();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Export failed");
        } finally {
            setIsGenerating(false);
        }
    }, [entityType, entityData, selectedFormat, options, onClose]);

    const handleOptionChange = (key: keyof ExportOptions, value: boolean | string) => {
        setOptions((prev) => ({ ...prev, [key]: value }));
    };

    if (!isOpen) return null;

    const selectedFormatInfo = formats.find((f) => f.format_id === selectedFormat);

    return (
        <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="export-modal-title">
            <div className="export-modal" onClick={(e) => e.stopPropagation()}>
                {/* Header */}
                <div className="export-modal-header">
                    <h2 id="export-modal-title">Export {entityType === "conversation" ? "Conversation" : "Message"}</h2>
                    <button className="modal-close-btn" onClick={onClose} aria-label="Close">
                        ✕
                    </button>
                </div>

                {/* Content */}
                <div className="export-modal-content">
                    {/* Entity info */}
                    <div className="export-entity-info">
                        <span className="export-entity-label">Exporting:</span>
                        <span className="export-entity-name">{entityName}</span>
                    </div>

                    {/* Loading state */}
                    {isLoading && (
                        <div className="export-loading">
                            <span className="spinner" />
                            Loading formats...
                        </div>
                    )}

                    {/* Error state */}
                    {error && (
                        <div className="export-error" role="alert">
                            <span className="error-icon">⚠️</span>
                            {error}
                            <button className="retry-btn" onClick={loadFormats}>
                                Retry
                            </button>
                        </div>
                    )}

                    {/* Format selection */}
                    {!isLoading && formats.length > 0 && (
                        <>
                            <div className="export-section">
                                <label className="export-label">Format</label>
                                <div className="export-formats">
                                    {formats.map((format) => (
                                        <button
                                            key={format.format_id}
                                            className={`format-btn ${selectedFormat === format.format_id ? "selected" : ""}`}
                                            onClick={() => setSelectedFormat(format.format_id)}
                                            title={format.description}
                                        >
                                            <span className="format-icon">
                                                {getFormatIcon(format.format_id)}
                                            </span>
                                            <span className="format-label">{format.label}</span>
                                            <span className="format-ext">{format.extension}</span>
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Format description */}
                            {selectedFormatInfo && (
                                <div className="export-format-desc">
                                    {selectedFormatInfo.description}
                                </div>
                            )}

                            {/* Options */}
                            <div className="export-section">
                                <label className="export-label">Options</label>
                                <div className="export-options">
                                    <label className="option-item">
                                        <input
                                            type="checkbox"
                                            checked={options.include_metadata}
                                            onChange={(e) => handleOptionChange("include_metadata", e.target.checked)}
                                        />
                                        <span>Include metadata (timestamps, IDs)</span>
                                    </label>
                                    <label className="option-item">
                                        <input
                                            type="checkbox"
                                            checked={options.include_citations}
                                            onChange={(e) => handleOptionChange("include_citations", e.target.checked)}
                                        />
                                        <span>Include source citations</span>
                                    </label>
                                    <label className="option-item">
                                        <input
                                            type="checkbox"
                                            checked={options.anonymize_user}
                                            onChange={(e) => handleOptionChange("anonymize_user", e.target.checked)}
                                        />
                                        <span>Anonymize user identifiers</span>
                                    </label>
                                    {selectedFormat === "markdown" && (
                                        <label className="option-item">
                                            <input
                                                type="checkbox"
                                                checked={options.include_raw_json_appendix}
                                                onChange={(e) => handleOptionChange("include_raw_json_appendix", e.target.checked)}
                                            />
                                            <span>Include raw JSON appendix</span>
                                        </label>
                                    )}
                                </div>
                            </div>
                        </>
                    )}
                </div>

                {/* Footer */}
                <div className="export-modal-footer">
                    <button className="btn-secondary" onClick={onClose} disabled={isGenerating}>
                        Cancel
                    </button>
                    <button
                        className="btn-primary"
                        onClick={handleExport}
                        disabled={isLoading || isGenerating || formats.length === 0}
                        id="export-generate-btn"
                    >
                        {isGenerating ? (
                            <>
                                <span className="spinner" />
                                Generating...
                            </>
                        ) : (
                            <>
                                📥 Export
                            </>
                        )}
                    </button>
                </div>
            </div>

            <style jsx>{`
                .modal-overlay {
                    position: fixed;
                    inset: 0;
                    background: rgba(0, 0, 0, 0.5);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 1000;
                    padding: 1rem;
                }

                .export-modal {
                    background: var(--bg, #ffffff);
                    border-radius: 12px;
                    width: 100%;
                    max-width: 500px;
                    max-height: 90vh;
                    display: flex;
                    flex-direction: column;
                    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
                }

                .export-modal-header {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    padding: 1.25rem 1.5rem;
                    border-bottom: 1px solid var(--border, #e5e7eb);
                }

                .export-modal-header h2 {
                    font-size: 1.25rem;
                    font-weight: 600;
                    margin: 0;
                    color: var(--text, #1f2937);
                }

                .modal-close-btn {
                    background: none;
                    border: none;
                    font-size: 1.25rem;
                    cursor: pointer;
                    color: var(--text-light, #6b7280);
                    padding: 0.25rem;
                    border-radius: 4px;
                    transition: background 0.15s;
                }

                .modal-close-btn:hover {
                    background: var(--bg-alt, #f9fafb);
                }

                .export-modal-content {
                    padding: 1.5rem;
                    overflow-y: auto;
                }

                .export-entity-info {
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                    padding: 0.75rem 1rem;
                    background: var(--bg-alt, #f9fafb);
                    border-radius: 8px;
                    margin-bottom: 1.5rem;
                }

                .export-entity-label {
                    color: var(--text-light, #6b7280);
                    font-size: 0.875rem;
                }

                .export-entity-name {
                    font-weight: 500;
                    color: var(--text, #1f2937);
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }

                .export-loading {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 0.75rem;
                    padding: 2rem;
                    color: var(--text-light, #6b7280);
                }

                .export-error {
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                    padding: 1rem;
                    background: #fef2f2;
                    border: 1px solid #fecaca;
                    border-radius: 8px;
                    color: #dc2626;
                    margin-bottom: 1rem;
                }

                .retry-btn {
                    margin-left: auto;
                    background: none;
                    border: 1px solid currentColor;
                    border-radius: 4px;
                    padding: 0.25rem 0.75rem;
                    cursor: pointer;
                    font-size: 0.875rem;
                }

                .export-section {
                    margin-bottom: 1.5rem;
                }

                .export-label {
                    display: block;
                    font-weight: 500;
                    margin-bottom: 0.75rem;
                    color: var(--text, #1f2937);
                }

                .export-formats {
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 0.5rem;
                }

                .format-btn {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    padding: 0.75rem 0.5rem;
                    background: var(--bg, #ffffff);
                    border: 2px solid var(--border, #e5e7eb);
                    border-radius: 8px;
                    cursor: pointer;
                    transition: all 0.15s;
                }

                .format-btn:hover {
                    border-color: var(--primary, #2563eb);
                    background: var(--bg-alt, #f9fafb);
                }

                .format-btn.selected {
                    border-color: var(--primary, #2563eb);
                    background: #dbeafe;
                }

                .format-icon {
                    font-size: 1.5rem;
                    margin-bottom: 0.25rem;
                }

                .format-label {
                    font-size: 0.75rem;
                    font-weight: 500;
                    color: var(--text, #1f2937);
                }

                .format-ext {
                    font-size: 0.625rem;
                    color: var(--text-light, #6b7280);
                }

                .export-format-desc {
                    font-size: 0.875rem;
                    color: var(--text-light, #6b7280);
                    margin-bottom: 1.5rem;
                    padding: 0.5rem 0;
                }

                .export-options {
                    display: flex;
                    flex-direction: column;
                    gap: 0.75rem;
                }

                .option-item {
                    display: flex;
                    align-items: center;
                    gap: 0.75rem;
                    cursor: pointer;
                    font-size: 0.875rem;
                    color: var(--text, #1f2937);
                }

                .option-item input[type="checkbox"] {
                    width: 1rem;
                    height: 1rem;
                    accent-color: var(--primary, #2563eb);
                }

                .export-modal-footer {
                    display: flex;
                    justify-content: flex-end;
                    gap: 0.75rem;
                    padding: 1rem 1.5rem;
                    border-top: 1px solid var(--border, #e5e7eb);
                }

                .btn-secondary {
                    padding: 0.625rem 1.25rem;
                    background: var(--bg, #ffffff);
                    border: 1px solid var(--border, #e5e7eb);
                    border-radius: 8px;
                    cursor: pointer;
                    font-weight: 500;
                    color: var(--text, #1f2937);
                    transition: background 0.15s;
                }

                .btn-secondary:hover:not(:disabled) {
                    background: var(--bg-alt, #f9fafb);
                }

                .btn-primary {
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                    padding: 0.625rem 1.25rem;
                    background: var(--primary, #2563eb);
                    border: none;
                    border-radius: 8px;
                    cursor: pointer;
                    font-weight: 500;
                    color: white;
                    transition: background 0.15s;
                }

                .btn-primary:hover:not(:disabled) {
                    background: #1d4ed8;
                }

                .btn-primary:disabled,
                .btn-secondary:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                }

                .spinner {
                    display: inline-block;
                    width: 1rem;
                    height: 1rem;
                    border: 2px solid currentColor;
                    border-right-color: transparent;
                    border-radius: 50%;
                    animation: spin 0.75s linear infinite;
                }

                @keyframes spin {
                    to {
                        transform: rotate(360deg);
                    }
                }

                @media (max-width: 480px) {
                    .export-formats {
                        grid-template-columns: repeat(2, 1fr);
                    }
                }
            `}</style>
        </div>
    );
}

function getFormatIcon(formatId: string): string {
    switch (formatId) {
        case "markdown":
            return "📝";
        case "html":
            return "🌐";
        case "pdf":
            return "📄";
        case "docx":
            return "📘";
        case "json":
            return "📋";
        case "text":
            return "📃";
        default:
            return "📁";
    }
}
