/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — Routing Trace Component
   Visualises how a query was routed through the multi-agent
   system (tier selection, escalation, complexity)
   ═══════════════════════════════════════════════════════════ */

"use client";

import { useState } from "react";
import type { RoutingDecision } from "@/lib/types";

interface RoutingTraceProps {
    routing: RoutingDecision;
}

const TIER_LABELS: Record<string, { label: string; icon: string; color: string }> = {
    haiku: { label: "Haiku", icon: "⚡", color: "var(--color-success)" },
    sonnet: { label: "Sonnet", icon: "🎯", color: "var(--color-warning)" },
    opus: { label: "Opus", icon: "🧠", color: "var(--color-accent)" },
};

function tierInfo(tier: string) {
    return TIER_LABELS[tier.toLowerCase()] ?? { label: tier, icon: "🔷", color: "var(--color-text-secondary)" };
}

export default function RoutingTrace({ routing }: RoutingTraceProps) {
    const [expanded, setExpanded] = useState(false);

    const initial = tierInfo(routing.initial_tier);
    const final_ = tierInfo(routing.final_tier);
    const complexityPct = Math.min(routing.complexity_score * 100, 100);

    return (
        <div className="routing-trace">
            <button
                className="routing-trace-toggle"
                onClick={() => setExpanded(!expanded)}
                aria-expanded={expanded}
                aria-controls="routing-detail"
            >
                <span className="routing-trace-icon">🔀</span>
                <span className="routing-trace-summary">
                    {initial.icon} {initial.label}
                    {routing.escalated && (
                        <>
                            <span className="routing-arrow">→</span>
                            {final_.icon} {final_.label}
                            <span className="routing-escalated-badge">escalated</span>
                        </>
                    )}
                </span>
                <span className="routing-task-type">{routing.task_type_detected}</span>
                <span className="routing-chevron">{expanded ? "▲" : "▼"}</span>
            </button>

            {expanded && (
                <div className="routing-detail" id="routing-detail" role="region" aria-label="Routing details">
                    {/* Flow diagram */}
                    <div className="routing-flow">
                        <div className="routing-node" style={{ borderColor: initial.color }}>
                            <span className="routing-node-icon">{initial.icon}</span>
                            <span className="routing-node-label">{initial.label}</span>
                            <span className="routing-node-role">Initial</span>
                        </div>

                        <div className="routing-connector">
                            <div className="routing-connector-line" />
                            {routing.escalated ? (
                                <span className="routing-connector-label" style={{ color: "var(--color-warning)" }}>
                                    escalated
                                </span>
                            ) : (
                                <span className="routing-connector-label" style={{ color: "var(--color-success)" }}>
                                    direct
                                </span>
                            )}
                        </div>

                        <div className="routing-node" style={{ borderColor: final_.color }}>
                            <span className="routing-node-icon">{final_.icon}</span>
                            <span className="routing-node-label">{final_.label}</span>
                            <span className="routing-node-role">Final</span>
                        </div>
                    </div>

                    {/* Complexity bar */}
                    <div className="routing-complexity">
                        <div className="routing-complexity-header">
                            <span>Complexity</span>
                            <span className="routing-complexity-value">{routing.complexity_score.toFixed(2)}</span>
                        </div>
                        <div className="routing-complexity-bar">
                            <div
                                className="routing-complexity-fill"
                                style={{
                                    width: `${complexityPct}%`,
                                    background: complexityPct > 70
                                        ? "var(--color-error)"
                                        : complexityPct > 40
                                            ? "var(--color-warning)"
                                            : "var(--color-success)",
                                }}
                            />
                        </div>
                    </div>

                    {/* Task type */}
                    <div className="routing-meta">
                        <span className="routing-meta-label">Task type</span>
                        <span className="routing-meta-value">{routing.task_type_detected}</span>
                    </div>
                </div>
            )}
        </div>
    );
}
