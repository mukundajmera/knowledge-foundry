/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — Document Manager Component
   Full document CRUD: list, upload, delete, search/filter
   ═══════════════════════════════════════════════════════════ */

"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import FileUpload from "@/components/FileUpload";
import type { FileAttachment } from "@/lib/types";

/* ─── Types ─── */
export interface DocumentItem {
    id: string;
    title: string;
    filename: string;
    status: "indexed" | "processing" | "error" | "pending";
    size_bytes: number;
    chunk_count: number;
    created_at: string;
    updated_at: string;
    source_type: string;
}

interface DocumentManagerProps {
    onClose?: () => void;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const STATUS_STYLES: Record<DocumentItem["status"], { label: string; icon: string; className: string }> = {
    indexed: { label: "Indexed", icon: "✅", className: "status-indexed" },
    processing: { label: "Processing", icon: "⏳", className: "status-processing" },
    error: { label: "Error", icon: "❌", className: "status-error" },
    pending: { label: "Pending", icon: "🕐", className: "status-pending" },
};

function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

/* ─── Component ─── */
export default function DocumentManager({ onClose }: DocumentManagerProps) {
    const [documents, setDocuments] = useState<DocumentItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState("");
    const [filterStatus, setFilterStatus] = useState<DocumentItem["status"] | "all">("all");
    const [uploading, setUploading] = useState(false);
    const [uploadFiles, setUploadFiles] = useState<FileAttachment[]>([]);
    const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
    const [sortField, setSortField] = useState<"title" | "created_at" | "size_bytes">("created_at");
    const [sortAsc, setSortAsc] = useState(false);

    /* ─── Fetch Documents ─── */
    const fetchDocuments = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE}/v1/documents`);
            if (!res.ok) throw new Error(`Failed to fetch: ${res.status}`);
            const data = await res.json();
            setDocuments(Array.isArray(data) ? data : data.documents || []);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load documents");
            // Demo data when API is unavailable
            setDocuments([
                { id: "doc-1", title: "Security Architecture", filename: "security-arch.pdf", status: "indexed", size_bytes: 2_450_000, chunk_count: 42, created_at: "2026-02-14T10:00:00Z", updated_at: "2026-02-14T10:05:00Z", source_type: "pdf" },
                { id: "doc-2", title: "Compliance Policy", filename: "compliance-policy.docx", status: "indexed", size_bytes: 1_230_000, chunk_count: 28, created_at: "2026-02-13T14:00:00Z", updated_at: "2026-02-13T14:02:00Z", source_type: "docx" },
                { id: "doc-3", title: "API Documentation", filename: "api-docs.md", status: "processing", size_bytes: 560_000, chunk_count: 0, created_at: "2026-02-14T12:00:00Z", updated_at: "2026-02-14T12:00:00Z", source_type: "markdown" },
                { id: "doc-4", title: "Employee Handbook", filename: "handbook-2026.pdf", status: "indexed", size_bytes: 4_100_000, chunk_count: 87, created_at: "2026-02-10T09:00:00Z", updated_at: "2026-02-10T09:15:00Z", source_type: "pdf" },
                { id: "doc-5", title: "Data Retention Policy", filename: "data-retention.pdf", status: "error", size_bytes: 890_000, chunk_count: 0, created_at: "2026-02-14T11:00:00Z", updated_at: "2026-02-14T11:01:00Z", source_type: "pdf" },
            ]);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchDocuments(); }, [fetchDocuments]);

    /* ─── Upload ─── */
    const handleUpload = useCallback(async () => {
        if (uploadFiles.length === 0) return;
        setUploading(true);
        try {
            for (const f of uploadFiles) {
                const formData = new FormData();
                formData.append("file", f.file);
                await fetch(`${API_BASE}/v1/documents`, { method: "POST", body: formData });
            }
            setUploadFiles([]);
            await fetchDocuments();
        } catch {
            setError("Upload failed");
        } finally {
            setUploading(false);
        }
    }, [uploadFiles, fetchDocuments]);

    /* ─── Delete ─── */
    const handleDelete = useCallback(async (id: string) => {
        try {
            await fetch(`${API_BASE}/v1/documents/${id}`, { method: "DELETE" });
            setDocuments((prev) => prev.filter((d) => d.id !== id));
        } catch {
            setError("Delete failed");
        }
        setDeleteConfirm(null);
    }, []);

    /* ─── Filter + Sort ─── */
    const filtered = useMemo(() => {
        let docs = [...documents];

        // Filter by status
        if (filterStatus !== "all") {
            docs = docs.filter((d) => d.status === filterStatus);
        }

        // Search
        if (searchQuery.trim()) {
            const q = searchQuery.toLowerCase();
            docs = docs.filter(
                (d) => d.title.toLowerCase().includes(q) || d.filename.toLowerCase().includes(q)
            );
        }

        // Sort
        docs.sort((a, b) => {
            let cmp = 0;
            if (sortField === "title") cmp = a.title.localeCompare(b.title);
            else if (sortField === "size_bytes") cmp = a.size_bytes - b.size_bytes;
            else cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
            return sortAsc ? cmp : -cmp;
        });

        return docs;
    }, [documents, filterStatus, searchQuery, sortField, sortAsc]);

    const handleSort = (field: typeof sortField) => {
        if (sortField === field) {
            setSortAsc(!sortAsc);
        } else {
            setSortField(field);
            setSortAsc(true);
        }
    };

    /* ─── Stats ─── */
    const stats = useMemo(() => ({
        total: documents.length,
        indexed: documents.filter((d) => d.status === "indexed").length,
        processing: documents.filter((d) => d.status === "processing").length,
        errors: documents.filter((d) => d.status === "error").length,
        totalSize: documents.reduce((s, d) => s + d.size_bytes, 0),
        totalChunks: documents.reduce((s, d) => s + d.chunk_count, 0),
    }), [documents]);

    return (
        <div className="doc-manager">
            {/* Header */}
            <div className="doc-manager-header">
                <div className="doc-manager-title-row">
                    <h2 className="doc-manager-title">📚 Documents</h2>
                    {onClose && (
                        <button className="icon-btn" onClick={onClose} aria-label="Back to chat">
                            ✕
                        </button>
                    )}
                </div>

                {/* Stats bar */}
                <div className="doc-stats">
                    <div className="doc-stat">
                        <span className="doc-stat-value">{stats.total}</span>
                        <span className="doc-stat-label">Documents</span>
                    </div>
                    <div className="doc-stat">
                        <span className="doc-stat-value">{stats.indexed}</span>
                        <span className="doc-stat-label">Indexed</span>
                    </div>
                    <div className="doc-stat">
                        <span className="doc-stat-value">{stats.totalChunks.toLocaleString()}</span>
                        <span className="doc-stat-label">Chunks</span>
                    </div>
                    <div className="doc-stat">
                        <span className="doc-stat-value">{formatBytes(stats.totalSize)}</span>
                        <span className="doc-stat-label">Total Size</span>
                    </div>
                </div>
            </div>

            {/* Toolbar */}
            <div className="doc-toolbar">
                <div className="doc-search">
                    <span className="doc-search-icon">🔍</span>
                    <input
                        type="text"
                        className="doc-search-input"
                        placeholder="Search documents…"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        aria-label="Search documents"
                        id="doc-search-input"
                    />
                </div>

                <select
                    className="doc-filter-select"
                    value={filterStatus}
                    onChange={(e) => setFilterStatus(e.target.value as typeof filterStatus)}
                    aria-label="Filter by status"
                >
                    <option value="all">All statuses</option>
                    <option value="indexed">Indexed</option>
                    <option value="processing">Processing</option>
                    <option value="error">Error</option>
                    <option value="pending">Pending</option>
                </select>

                <button className="doc-refresh-btn" onClick={fetchDocuments} aria-label="Refresh">
                    🔄 Refresh
                </button>
            </div>

            {/* Upload zone */}
            <div className="doc-upload-zone">
                <FileUpload
                    files={uploadFiles}
                    onAdd={(file) => setUploadFiles((prev) => [...prev, file])}
                    onRemove={(idx) => setUploadFiles((prev) => prev.filter((_, i) => i !== idx))}
                    disabled={uploading}
                />
                {uploadFiles.length > 0 && (
                    <button
                        className="doc-upload-btn"
                        onClick={handleUpload}
                        disabled={uploading}
                    >
                        {uploading ? "⏳ Uploading…" : `📤 Upload ${uploadFiles.length} file${uploadFiles.length > 1 ? "s" : ""}`}
                    </button>
                )}
            </div>

            {/* Error */}
            {error && (
                <div className="doc-error" role="alert">
                    ⚠️ {error}
                    <button className="doc-error-dismiss" onClick={() => setError(null)}>✕</button>
                </div>
            )}

            {/* Table */}
            {loading ? (
                <div className="doc-loading">
                    <div className="doc-spinner" />
                    Loading documents…
                </div>
            ) : (
                <div className="doc-table-wrap">
                    <table className="doc-table" role="table">
                        <thead>
                            <tr>
                                <th className="doc-th sortable" onClick={() => handleSort("title")}>
                                    Name {sortField === "title" && (sortAsc ? "↑" : "↓")}
                                </th>
                                <th className="doc-th">Status</th>
                                <th className="doc-th">Chunks</th>
                                <th className="doc-th sortable" onClick={() => handleSort("size_bytes")}>
                                    Size {sortField === "size_bytes" && (sortAsc ? "↑" : "↓")}
                                </th>
                                <th className="doc-th sortable" onClick={() => handleSort("created_at")}>
                                    Added {sortField === "created_at" && (sortAsc ? "↑" : "↓")}
                                </th>
                                <th className="doc-th">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.length === 0 ? (
                                <tr>
                                    <td className="doc-td doc-empty" colSpan={6}>
                                        {searchQuery ? "No documents match your search" : "No documents uploaded yet"}
                                    </td>
                                </tr>
                            ) : (
                                filtered.map((doc) => {
                                    const st = STATUS_STYLES[doc.status];
                                    return (
                                        <tr key={doc.id} className="doc-row">
                                            <td className="doc-td doc-name-cell">
                                                <div className="doc-name">{doc.title}</div>
                                                <div className="doc-filename">{doc.filename}</div>
                                            </td>
                                            <td className="doc-td">
                                                <span className={`doc-status-badge ${st.className}`}>
                                                    {st.icon} {st.label}
                                                </span>
                                            </td>
                                            <td className="doc-td doc-number">{doc.chunk_count}</td>
                                            <td className="doc-td doc-number">{formatBytes(doc.size_bytes)}</td>
                                            <td className="doc-td doc-date">{formatDate(doc.created_at)}</td>
                                            <td className="doc-td">
                                                {deleteConfirm === doc.id ? (
                                                    <div className="doc-delete-confirm">
                                                        <button
                                                            className="doc-delete-yes"
                                                            onClick={() => handleDelete(doc.id)}
                                                        >
                                                            Delete
                                                        </button>
                                                        <button
                                                            className="doc-delete-no"
                                                            onClick={() => setDeleteConfirm(null)}
                                                        >
                                                            Cancel
                                                        </button>
                                                    </div>
                                                ) : (
                                                    <button
                                                        className="doc-action-btn"
                                                        onClick={() => setDeleteConfirm(doc.id)}
                                                        aria-label={`Delete ${doc.title}`}
                                                    >
                                                        🗑️
                                                    </button>
                                                )}
                                            </td>
                                        </tr>
                                    );
                                })
                            )}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
