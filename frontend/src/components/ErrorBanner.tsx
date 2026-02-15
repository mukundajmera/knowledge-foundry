/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — Error Banner Component
   Contextual error/warning banners for AI responses
   ═══════════════════════════════════════════════════════════ */

"use client";

interface ErrorBannerProps {
    type: "no_results" | "low_confidence" | "rate_limit" | "system_error";
    retryAfterSeconds?: number;
    message?: string;
    onRetry?: () => void;
    onDismiss?: () => void;
}

const ERROR_CONFIG: Record<
    ErrorBannerProps["type"],
    { icon: string; title: string; className: string }
> = {
    no_results: {
        icon: "🔍",
        title: "No results found",
        className: "error-banner--warning",
    },
    low_confidence: {
        icon: "⚠️",
        title: "Low confidence response",
        className: "error-banner--warning",
    },
    rate_limit: {
        icon: "⏸️",
        title: "Rate limit reached",
        className: "error-banner--info",
    },
    system_error: {
        icon: "❌",
        title: "Something went wrong",
        className: "error-banner--error",
    },
};

const DEFAULT_MESSAGES: Record<ErrorBannerProps["type"], string> = {
    no_results:
        "We couldn't find relevant information. Try rephrasing your question or broadening your search.",
    low_confidence:
        "This response may not be fully accurate. Please verify independently before relying on it.",
    rate_limit: "You've exceeded the request limit.",
    system_error:
        "An unexpected error occurred. Our team has been notified.",
};

function formatRetryTime(seconds: number): string {
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.ceil(seconds / 60);
    return `${mins} min`;
}

export default function ErrorBanner({
    type,
    retryAfterSeconds,
    message,
    onRetry,
    onDismiss,
}: ErrorBannerProps) {
    const config = ERROR_CONFIG[type];
    const displayMessage = message || DEFAULT_MESSAGES[type];

    return (
        <div
            className={`error-banner ${config.className}`}
            role="alert"
            aria-live="polite"
        >
            <div className="error-banner-content">
                <span className="error-banner-icon">{config.icon}</span>
                <div className="error-banner-text">
                    <strong className="error-banner-title">{config.title}</strong>
                    <p className="error-banner-message">{displayMessage}</p>
                    {type === "rate_limit" && retryAfterSeconds && (
                        <p className="error-banner-retry-info">
                            Try again in {formatRetryTime(retryAfterSeconds)}
                        </p>
                    )}
                </div>
            </div>
            <div className="error-banner-actions">
                {(type === "system_error" || type === "no_results") && onRetry && (
                    <button className="error-banner-btn primary" onClick={onRetry}>
                        🔄 Retry
                    </button>
                )}
                {type === "no_results" && (
                    <button className="error-banner-btn" onClick={onDismiss}>
                        Rephrase
                    </button>
                )}
                {type === "low_confidence" && (
                    <button className="error-banner-btn" onClick={onDismiss}>
                        Acknowledged
                    </button>
                )}
            </div>
        </div>
    );
}
