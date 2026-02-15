/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — Main Page
   Composes all components into the app shell
   ═══════════════════════════════════════════════════════════ */

"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import MessageBubble from "@/components/MessageBubble";
import QueryInput from "@/components/QueryInput";
import KeyboardShortcuts from "@/components/KeyboardShortcuts";
import ThemeToggle from "@/components/ThemeToggle";
import DocumentManager from "@/components/DocumentManager";
import ExportModal from "@/components/ExportModal";
import { useConversations } from "@/hooks/useConversations";
import { useChat } from "@/hooks/useChat";
import type { QueryOptions } from "@/lib/types";

export default function Home() {
  const {
    conversations,
    activeConversation,
    activeId,
    grouped,
    setActiveId,
    createConversation,
    deleteConversation,
    addMessage,
    updateMessage,
  } = useConversations();

  const { send, stop, regenerate, isStreaming } = useChat({
    onAddMessage: addMessage,
    onUpdateMessage: updateMessage,
    conversations,
  });

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [view, setView] = useState<"chat" | "documents">("chat");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeConversation?.messages]);

  // Global keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Don't trigger shortcuts when typing in inputs
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      if (e.key === "?") {
        e.preventDefault();
        setShortcutsOpen(true);
      }
      if (e.key === "n" || e.key === "N") {
        e.preventDefault();
        handleNewChat();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSend = (query: string, options: QueryOptions) => {
    let convId = activeId;
    if (!convId) {
      convId = createConversation();
    }
    send(query, convId, options);
  };

  const handleNewChat = () => {
    createConversation();
    setSidebarOpen(false);
  };

  const handleSelectConversation = (id: string) => {
    setActiveId(id);
    setSidebarOpen(false);
  };

  const handleFollowUp = useCallback(
    (query: string) => {
      if (!activeId) return;
      send(query, activeId);
    },
    [activeId, send]
  );

  const handleRegenerate = useCallback(
    (messageId: string) => {
      if (!activeId) return;
      regenerate(activeId, messageId);
    },
    [activeId, regenerate]
  );

  const messages = activeConversation?.messages || [];
  const hasMessages = messages.length > 0;

  return (
    <div className="app-shell">
      {/* Sidebar */}
      <Sidebar
        grouped={grouped}
        activeId={activeId}
        isOpen={sidebarOpen}
        onSelect={handleSelectConversation}
        onNew={handleNewChat}
        onDelete={deleteConversation}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Main content */}
      <main className="app-main">
        {/* Header */}
        <header className="header" role="banner">
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
            <button
              className="icon-btn mobile-menu-btn"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open menu"
              id="mobile-menu-btn"
            >
              ☰
            </button>
            <div className="header-logo">
              <div className="header-logo-icon">✦</div>
              Knowledge Foundry
            </div>
          </div>
          <div className="header-actions">
            <div className="header-view-tabs">
              <button
                className={`view-tab ${view === "chat" ? "active" : ""}`}
                onClick={() => setView("chat")}
                aria-label="Chat view"
              >
                💬 Chat
              </button>
              <button
                className={`view-tab ${view === "documents" ? "active" : ""}`}
                onClick={() => setView("documents")}
                aria-label="Documents view"
                id="docs-tab"
              >
                📚 Docs
              </button>
            </div>
            <ThemeToggle />
            <button
              className="icon-btn"
              aria-label="Keyboard shortcuts"
              title="Keyboard shortcuts (?)"
              onClick={() => setShortcutsOpen(true)}
              id="shortcuts-btn"
            >
              ⌨️
            </button>
            <button className="icon-btn" aria-label="Help" title="Help">
              ❓
            </button>
            <button className="icon-btn" aria-label="User profile" title="Profile">
              👤
            </button>
          </div>
        </header>

        {/* Content area */}
        {view === "documents" ? (
          <div className="chat-area">
            <DocumentManager onClose={() => setView("chat")} />
          </div>
        ) : (
          <div className="chat-area">
            {!hasMessages ? (
              /* Welcome screen */
              <div className="welcome">
                <div className="welcome-icon">✦</div>
                <h1 className="welcome-title">Knowledge Foundry</h1>
                <p className="welcome-subtitle">
                  Your enterprise AI knowledge assistant. Ask questions about your documents and get cited, accurate answers.
                </p>
              </div>
            ) : (
              /* Messages */
              <div className="messages-container" role="log" aria-label="Conversation messages">
                {/* Export conversation button */}
                {activeConversation && messages.length > 0 && (
                  <div className="conversation-actions">
                    <button
                      className="export-conversation-btn"
                      onClick={() => setExportOpen(true)}
                      aria-label="Export conversation"
                      id="export-conversation-btn"
                    >
                      📥 Export Conversation
                    </button>
                  </div>
                )}
                <div className="messages-list">
                  {messages.map((msg) => (
                    <MessageBubble
                      key={msg.id}
                      message={msg}
                      onFollowUp={handleFollowUp}
                      onRegenerate={handleRegenerate}
                    />
                  ))}
                  <div ref={messagesEndRef} />
                </div>
              </div>
            )}

            {/* Query input */}
            <QueryInput
              onSend={handleSend}
              isStreaming={isStreaming}
              onStop={stop}
            />
          </div>
        )}
      </main>

      {/* Keyboard shortcuts modal */}
      <KeyboardShortcuts
        isOpen={shortcutsOpen}
        onClose={() => setShortcutsOpen(false)}
      />

      {/* Export conversation modal */}
      {activeConversation && (
        <ExportModal
          isOpen={exportOpen}
          onClose={() => setExportOpen(false)}
          entityType="conversation"
          entityName={activeConversation.title}
          entityData={{
            id: activeConversation.id,
            title: activeConversation.title,
            messages: activeConversation.messages,
            createdAt: activeConversation.createdAt,
            updatedAt: activeConversation.updatedAt,
          }}
        />
      )}
    </div>
  );
}
