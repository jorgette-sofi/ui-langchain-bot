import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import './App.css';

interface Log {
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export default function Admin() {
  const [logs, setLogs] = useState<Log[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const fetchLogs = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    try {
      const response = await fetch('http://localhost:8000/api/admin/logs');
      if (!response.ok) throw new Error('Failed to fetch logs');
      const data = await response.json();
      setLogs(data.logs);
    } catch (error) {
      console.error("Error fetching logs:", error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const groupedSessions = useMemo(() => {
    const groups: Record<string, Log[]> = {};

    logs.forEach(log => {
      if (!groups[log.session_id]) groups[log.session_id] = [];
      groups[log.session_id].push(log);
    });

    const sortedSessionIds = Object.keys(groups).sort((a, b) => {
      const latestA = new Date(groups[a][0].timestamp).getTime();
      const latestB = new Date(groups[b][0].timestamp).getTime();
      return latestB - latestA;
    });

    sortedSessionIds.forEach(id => {
      groups[id] = groups[id].reverse();
    });

    if (!selectedSessionId && sortedSessionIds.length > 0) {
      setSelectedSessionId(sortedSessionIds[0]);
    }

    return { groups, sortedSessionIds };
  }, [logs, selectedSessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "instant" });
  }, [selectedSessionId]);

  const currentMessages = selectedSessionId ? groupedSessions.groups[selectedSessionId] : [];

  const isHtml = (content: string) => /<[a-z][\s\S]*>/i.test(content);

  const formatDate = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  const formatTime = (timestamp: string) =>
    new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <div className="inbox-layout">
      {/* Sidebar */}
      <aside className="inbox-sidebar">
        <div className="sidebar-header">
          <div className="sidebar-header-left">
            <h2>Inbox</h2>
            {!loading && (
              <span className="session-count">{groupedSessions.sortedSessionIds.length}</span>
            )}
          </div>
          <div className="sidebar-header-right">
            <button
              className={`refresh-btn ${refreshing ? 'spinning' : ''}`}
              onClick={() => fetchLogs(true)}
              disabled={refreshing}
              title="Refresh"
            >
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
            <Link to="/" className="nav-link">Exit</Link>
          </div>
        </div>

        {loading ? (
          <div className="sidebar-loading">Loading...</div>
        ) : (
          <div className="session-list">
            {groupedSessions.sortedSessionIds.length === 0 ? (
              <div className="sidebar-loading">No conversations yet.</div>
            ) : (
              groupedSessions.sortedSessionIds.map(sessionId => {
                const sessionLogs = groupedSessions.groups[sessionId];
                const lastMessage = sessionLogs[sessionLogs.length - 1];
                const isActive = sessionId === selectedSessionId;

                return (
                  <div
                    key={sessionId}
                    className={`session-item ${isActive ? 'active' : ''}`}
                    onClick={() => setSelectedSessionId(sessionId)}
                  >
                    <div className="session-meta">
                      <span className="session-id-short">{sessionId.substring(0, 10)}</span>
                      <span className="session-time">
                        {formatDate(lastMessage.timestamp)} · {formatTime(lastMessage.timestamp)}
                      </span>
                    </div>
                    <div className="session-preview">
                      <span className={`preview-role ${lastMessage.role}`}>
                        {lastMessage.role === 'user' ? 'User' : 'Agent'}:
                      </span>{' '}
                      {lastMessage.content.length > 38
                        ? lastMessage.content.substring(0, 38) + '...'
                        : lastMessage.content}
                    </div>
                    <div className="session-msg-count">{sessionLogs.length} messages</div>
                  </div>
                );
              })
            )}
          </div>
        )}
      </aside>

      {/* Main View */}
      <main className="inbox-main">
        <header className="inbox-main-header">
          <div>
            <h3>Session Details</h3>
            {selectedSessionId && (
              <span className="full-session-id">{selectedSessionId}</span>
            )}
          </div>
          {currentMessages.length > 0 && (
            <span className="message-count-badge">{currentMessages.length} messages</span>
          )}
        </header>

        <div className="chat-window admin-chat-window">
          {currentMessages.length > 0 ? (
            currentMessages.map((msg, index) => (
              <div key={index} className={`message-row ${msg.role}`}>
                {msg.role === 'assistant' && (
                  <div className="msg-avatar assistant-avatar">HA</div>
                )}
                <div className={`message-bubble ${msg.role}`}>
                  {msg.role === 'user' ? (
                    msg.content
                  ) : isHtml(msg.content) ? (
                    <div className="help-content" dangerouslySetInnerHTML={{ __html: msg.content }} />
                  ) : (
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  )}
                  <div className="message-timestamp">{formatTime(msg.timestamp)}</div>
                </div>
                {msg.role === 'user' && (
                  <div className="msg-avatar user-avatar">U</div>
                )}
              </div>
            ))
          ) : (
            <div className="empty-state">Select a conversation to view history.</div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </main>
    </div>
  );
}
