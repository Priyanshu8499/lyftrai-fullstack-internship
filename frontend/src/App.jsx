import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Menu,
  MessageSquarePlus,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  Settings2,
  Sun,
  Trash2,
  X,
  Zap,
  Sparkles,
} from "lucide-react";
import ChatWindow from "./components/ChatWindow";
import MessageInput from "./components/MessageInput";
import SystemPrompt from "./components/SystemPrompt";
import { useChat } from "./hooks/useChat";
import { generateSessionId, isValidSessionId } from "./utils/session";
import { deleteChatSession, getSessionMessages } from "./utils/api";
import "./App.css";

const HISTORY_KEY = "jimmy.conversations";
const THEME_KEY = "jimmy.theme";
const PROMPT_KEY = "jimmy.systemPrompt";

function readHistory() {
  try {
    const history = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
    if (!Array.isArray(history)) return [];
    return history.filter(
      (item) =>
        item &&
        typeof item.id === "string" &&
        typeof item.title === "string" &&
        Number.isFinite(item.updatedAt),
    );
  } catch {
    return [];
  }
}

function IconButton({ label, onClick, children, className = "", ...props }) {
  return (
    <button
      type="button"
      className={`icon-button ${className}`}
      aria-label={label}
      title={label}
      onClick={onClick}
      {...props}
    >
      {children}
    </button>
  );
}

export default function App() {
  const [history, setHistory] = useState(readHistory);
  const [activeId, setActiveId] = useState(() => generateSessionId());
  const [theme, setTheme] = useState(
    () => localStorage.getItem(THEME_KEY) || "light",
  );
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [search, setSearch] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const [clearTarget, setClearTarget] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyCursor, setHistoryCursor] = useState(null);
  const [olderLoading, setOlderLoading] = useState(false);
  const [olderError, setOlderError] = useState(false);
  const {
    messages,
    isLoading,
    systemPrompt,
    setSystemPrompt,
    sendMessage,
    replaceMessages,
  } = useChat(activeId, localStorage.getItem(PROMPT_KEY) || "");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);
  useEffect(() => {
    localStorage.setItem(PROMPT_KEY, systemPrompt);
  }, [systemPrompt]);
  useEffect(() => {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
  }, [history]);

  useEffect(() => {
    const firstUser = messages.find((item) => item.role === "user");
    if (!firstUser) return;
    setHistory((items) => {
      const existing = items.find((item) => item.id === activeId);
      const updated = {
        id: activeId,
        title: existing?.title || firstUser.content.slice(0, 54),
        updatedAt: Date.now(),
      };
      return [updated, ...items.filter((item) => item.id !== activeId)];
    });
  }, [messages, activeId]);

  const filteredHistory = useMemo(
    () =>
      history.filter((item) =>
        item.title.toLowerCase().includes(search.toLowerCase()),
      ),
    [history, search],
  );
  const legacyHistoryCount = history.filter((item) => !isValidSessionId(item.id)).length;

  const newChat = useCallback(() => {
    if (isLoading || historyLoading || olderLoading) return;
    const id = generateSessionId();
    setActiveId(id);
    setHistoryCursor(null);
    setOlderError(false);
    replaceMessages([], id);
    setSidebarOpen(false);
  }, [historyLoading, isLoading, olderLoading, replaceMessages]);

  const openChat = async (id) => {
    if (id === activeId || historyLoading || isLoading || olderLoading) return;
    if (!isValidSessionId(id)) {
      setHistory((items) => items.filter((item) => item.id !== id));
      return;
    }
    setHistoryLoading(true);
    setActiveId(id);
    setHistoryCursor(null);
    setOlderError(false);
    try {
      const data = await getSessionMessages(id);
      replaceMessages(data.messages || [], id);
      setHistoryCursor(data.next_before_id || null);
    } catch (error) {
      if (error.message === "SESSION_NOT_FOUND") {
        setHistory((items) => items.filter((item) => item.id !== id));
      }
      replaceMessages(
        [
          {
            role: "system",
            content:
              error.message === "SESSION_NOT_FOUND"
                ? "This conversation is no longer available."
                : "Could not load this conversation. Check your connection and try again.",
          },
        ],
        id,
      );
      setHistoryCursor(null);
    } finally {
      setHistoryLoading(false);
      setSidebarOpen(false);
    }
  };

  const loadEarlier = async () => {
    if (!historyCursor || historyLoading || olderLoading || isLoading) return;
    const requestedSessionId = activeId;
    setOlderLoading(true);
    setOlderError(false);
    try {
      const data = await getSessionMessages(requestedSessionId, historyCursor);
      if (requestedSessionId !== activeId) return;
      replaceMessages(
        [...(data.messages || []), ...messages],
        requestedSessionId,
      );
      setHistoryCursor(data.next_before_id || null);
    } catch {
      setOlderError(true);
    } finally {
      setOlderLoading(false);
    }
  };

  useEffect(() => {
    const handleShortcut = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        newChat();
      }
    };
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, [newChat]);

  const clearChat = async () => {
    if (isLoading || historyLoading || olderLoading) return;
    const targetId = clearTarget || activeId;
    setConfirmClear(false);
    setClearTarget(null);
    if (history.some((item) => item.id === targetId)) {
      try {
        await deleteChatSession(targetId);
      } catch (error) {
        if (error.message !== "SESSION_NOT_FOUND") {
          if (targetId === activeId) {
            replaceMessages([
              {
                role: "system",
                content:
                  "Could not clear this conversation. Check your connection and try again.",
              },
            ]);
          }
          return;
        }
      }
    }
    setHistory((items) => items.filter((item) => item.id !== targetId));
    if (targetId === activeId) newChat();
  };

  return (
    <div className={`app-shell ${collapsed ? "sidebar-collapsed" : ""}`}>
      <aside className={`sidebar ${sidebarOpen ? "sidebar--open" : ""}`}>
        <div className="brand-row">
          <a
            className="brand"
            href="#"
            onClick={(e) => e.preventDefault()}
            aria-label="Jimmy home"
          >
            <span className="brand-mark">
              <Zap size={17} fill="currentColor" strokeWidth={1.5} />
            </span>
            {!collapsed && (
              <span className="brand-name">
                jimmy<span className="brand-dot">.</span>
              </span>
            )}
          </a>
          <IconButton
            label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="sidebar-toggle"
            onClick={() => setCollapsed(!collapsed)}
          >
            {collapsed ? (
              <PanelLeftOpen size={18} />
            ) : (
              <PanelLeftClose size={18} />
            )}
          </IconButton>
        </div>

        <button
          className="new-chat"
          onClick={newChat}
          disabled={isLoading || historyLoading || olderLoading}
          title="New chat"
        >
          <span className="new-chat-icon">
            <Plus size={18} />
          </span>
          {!collapsed && (
            <>
              <span>New chat</span>
              <kbd>⌘ K</kbd>
            </>
          )}
        </button>

        {!collapsed && (
          <>
            <div className="sidebar-section-head">
              <span>Your chats</span>
              <span className="history-count">{history.length}</span>
            </div>
            {legacyHistoryCount > 0 && (
              <div className="legacy-history-notice" role="status">
                <span>{legacyHistoryCount} older chat{legacyHistoryCount === 1 ? "" : "s"} can’t be opened after a security update.</span>
                <button
                  type="button"
                  onClick={() => setHistory((items) => items.filter((item) => isValidSessionId(item.id)))}
                >
                  Remove from list
                </button>
              </div>
            )}
            <label className="search-box">
              <Search size={15} />
              <input
                aria-label="Search conversations"
                placeholder="Search conversations"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </label>
            <div className="history-list">
              {filteredHistory.map((item) => (
                <div
                  key={item.id}
                  className={`history-item ${item.id === activeId ? "history-item--active" : ""}`}
                >
                  <button
                    className="history-open"
                    onClick={() => openChat(item.id)}
                    disabled={isLoading || historyLoading || olderLoading}
                    title={item.title}
                  >
                    <MessageSquarePlus size={15} />
                    <span>{item.title}</span>
                  </button>
                  <IconButton
                    label={`Delete ${item.title}`}
                    className="history-delete"
                    onClick={() => {
                      setClearTarget(item.id);
                      setConfirmClear(true);
                    }}
                    disabled={isLoading || historyLoading || olderLoading}
                  >
                    <Trash2 size={14} />
                  </IconButton>
                </div>
              ))}
              {filteredHistory.length === 0 && (
                <div className="history-empty">
                  {search ? "No matching chats" : "Your chats will appear here"}
                </div>
              )}
            </div>
          </>
        )}

        <div className="sidebar-bottom">
          <button
            className="sidebar-action"
            onClick={() => setSettingsOpen(true)}
            title="Settings"
          >
            <Settings2 size={18} />
            {!collapsed && <span>Settings</span>}
          </button>
          <button
            className="profile-row"
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}
            title={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
          >
            <span className="avatar">J</span>
            {!collapsed && (
              <>
                <span className="profile-name">Jimmy</span>
                <span className="theme-toggle">
                  {theme === "light" ? <Moon size={16} /> : <Sun size={16} />}
                </span>
              </>
            )}
          </button>
        </div>
      </aside>

      {sidebarOpen && (
        <button
          className="mobile-scrim"
          aria-label="Close menu"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <main className="main-panel">
        <header className="topbar">
          <IconButton
            label="Open menu"
            className="mobile-menu"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu size={20} />
          </IconButton>
          <div className="model-selector">
            <Sparkles size={15} /> Jimmy
          </div>
          <div className="topbar-right">
            <span className="model-note">Thoughtful AI, made simple</span>
          </div>
        </header>

        <ChatWindow
          messages={messages}
          isLoading={isLoading || historyLoading}
          onSuggestion={sendMessage}
          onLoadEarlier={loadEarlier}
          hasEarlier={Boolean(historyCursor)}
          loadingEarlier={olderLoading}
          historyError={olderError}
        />
        <footer className="composer-area">
          <MessageInput
            onSend={sendMessage}
            isLoading={isLoading || historyLoading || olderLoading}
          />
          <p className="composer-note">
            Jimmy can make mistakes. Check important information.
          </p>
        </footer>
      </main>

      {settingsOpen && (
        <div
          className="dialog-backdrop"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setSettingsOpen(false);
          }}
        >
          <section
            className="settings-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="settings-title"
          >
            <header>
              <div>
                <span className="eyebrow">PERSONALIZE</span>
                <h2 id="settings-title">Settings</h2>
              </div>
              <IconButton
                label="Close settings"
                onClick={() => setSettingsOpen(false)}
              >
                <X size={19} />
              </IconButton>
            </header>
            <div className="setting-block">
              <div>
                <h3>Appearance</h3>
                <p>Choose the look that feels right.</p>
              </div>
              <div className="theme-options">
                <button
                  className={theme === "light" ? "selected" : ""}
                  onClick={() => setTheme("light")}
                >
                  <Sun size={17} /> Light
                </button>
                <button
                  className={theme === "dark" ? "selected" : ""}
                  onClick={() => setTheme("dark")}
                >
                  <Moon size={17} /> Dark
                </button>
              </div>
            </div>
            <div className="setting-block prompt-setting">
              <div>
                <h3>Custom instructions</h3>
                <p>Set a preference for how Jimmy responds.</p>
              </div>
              <SystemPrompt value={systemPrompt} onChange={setSystemPrompt} />
            </div>
            <div className="setting-danger">
              <div>
                <h3>Clear this conversation</h3>
                <p>Remove its messages and start fresh.</p>
              </div>
              <button
                className="danger-button"
                disabled={isLoading || historyLoading || olderLoading}
                onClick={() => {
                  setClearTarget(activeId);
                  setConfirmClear(true);
                }}
              >
                <Trash2 size={15} /> Clear chat
              </button>
            </div>
            <a className="privacy-link" href="/privacy.html" target="_blank" rel="noreferrer">
              Privacy information
            </a>
          </section>
        </div>
      )}

      {confirmClear && (
        <div className="dialog-backdrop">
          <section
            className="confirm-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="clear-title"
          >
            <div className="confirm-icon">
              <Trash2 size={20} />
            </div>
            <h2 id="clear-title">Clear this conversation?</h2>
            <p>
              This removes the conversation from Jimmy and cannot be undone.
            </p>
            <div className="dialog-actions">
              <button
                className="cancel-button"
                onClick={() => {
                  setConfirmClear(false);
                  setClearTarget(null);
                }}
              >
                Cancel
              </button>
              <button className="danger-button" onClick={clearChat} disabled={isLoading || historyLoading || olderLoading}>
                Clear conversation
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
