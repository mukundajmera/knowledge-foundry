/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — File Upload Component
   Drag-and-drop + attach button for document upload
   ═══════════════════════════════════════════════════════════ */

"use client";

import { useState, useRef, useCallback } from "react";
import type { FileAttachment } from "@/lib/types";

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB
const ACCEPTED_TYPES = [
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
];

function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface FileUploadProps {
    files: FileAttachment[];
    onAdd: (file: FileAttachment) => void;
    onRemove: (index: number) => void;
    disabled?: boolean;
}

export default function FileUpload({ files, onAdd, onRemove, disabled }: FileUploadProps) {
    const [isDragging, setIsDragging] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const validateAndAdd = useCallback(
        (file: File) => {
            setError(null);
            if (file.size > MAX_FILE_SIZE) {
                setError(`File too large (max ${formatFileSize(MAX_FILE_SIZE)})`);
                return;
            }
            if (files.length >= 5) {
                setError("Maximum 5 files allowed");
                return;
            }
            onAdd({ name: file.name, size: file.size, type: file.type, file });
        },
        [files, onAdd]
    );

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
    }, []);

    const handleDrop = useCallback(
        (e: React.DragEvent) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDragging(false);
            const dropped = e.dataTransfer.files;
            for (let i = 0; i < dropped.length; i++) {
                validateAndAdd(dropped[i]);
            }
        },
        [validateAndAdd]
    );

    const handleFileSelect = useCallback(
        (e: React.ChangeEvent<HTMLInputElement>) => {
            const selected = e.target.files;
            if (!selected) return;
            for (let i = 0; i < selected.length; i++) {
                validateAndAdd(selected[i]);
            }
            // Reset input so same file can be re-selected
            e.target.value = "";
        },
        [validateAndAdd]
    );

    return (
        <div className="file-upload-area">
            {/* Drag zone (only visible when dragging or if there are files) */}
            {(isDragging || files.length > 0) && (
                <div
                    className={`file-drop-zone ${isDragging ? "active" : ""}`}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    role="region"
                    aria-label="File drop zone"
                >
                    {isDragging ? (
                        <span className="drop-zone-label">Drop files here…</span>
                    ) : (
                        <div className="file-list">
                            {files.map((f, i) => (
                                <div key={`${f.name}-${i}`} className="file-chip">
                                    <span className="file-chip-icon">📄</span>
                                    <span className="file-chip-name">{f.name}</span>
                                    <span className="file-chip-size">{formatFileSize(f.size)}</span>
                                    <button
                                        className="file-chip-remove"
                                        onClick={() => onRemove(i)}
                                        aria-label={`Remove ${f.name}`}
                                        disabled={disabled}
                                    >
                                        ✕
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Hidden file input */}
            <input
                ref={fileInputRef}
                type="file"
                className="file-input-hidden"
                accept={ACCEPTED_TYPES.join(",")}
                multiple
                onChange={handleFileSelect}
                aria-hidden="true"
                tabIndex={-1}
            />

            {/* Attach button */}
            <button
                className="attach-btn"
                onClick={() => fileInputRef.current?.click()}
                aria-label="Attach file"
                title="Attach file (PDF, TXT, DOCX)"
                disabled={disabled}
                id="attach-btn"
            >
                📎
            </button>

            {/* Error */}
            {error && (
                <div className="file-upload-error" role="alert">
                    {error}
                </div>
            )}
        </div>
    );
}
