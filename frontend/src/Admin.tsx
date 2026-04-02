import { useState, useEffect, useMemo, useRef } from 'react';
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
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/admin/logs');
        if (!response.ok) throw new Error('Failed to fetch logs');
        const data = await response.json();
        setLogs(data.logs);
      } catch (error) {
        console.error("Error fetching logs:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchLogs();
    // Optional: Set up a polling interval here to auto-refresh logs every X seconds
  }, []);

  // Group logs by session_id and sort messages chronologically
  const groupedSessions = useMemo(() => {
    const groups: Record<string, Log[]> = {};
    
    // The backend sends them DESC, so we process them and reverse the individual arrays later
    logs.forEach(log => {
      if (!groups[log.session_id]) {
        groups[log.session_id] = [];
      }
      groups[log.session_id].push(log);
    });

    // Sort the sessions so the one with the newest message is at the top of the sidebar
    const sortedSessionIds = Object.keys(groups).sort((a, b) => {
      const latestA = new Date(groups[a][0].timestamp).getTime();
      const latestB = new Date(groups[b][0].timestamp).getTime();
      return latestB - latestA;
    });

    // Reverse the message arrays so they read top-to-bottom (oldest to newest) in the chat pane
    sortedSessionIds.forEach(id => {
      groups[id] = groups[id].reverse();
    });

    // Auto-select the most recent session if none is selected
    if (!selectedSessionId && sortedSessionIds.length > 0) {
      setSelectedSessionId(sortedSessionIds[0]);
    }

    return { groups, sortedSessionIds };
  }, [logs, selectedSessionId]);

  // Auto-scroll to bottom of the chat pane when selecting a new session
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "instant" });
  }, [selectedSessionId]);

  const currentMessages = selectedSessionId ? groupedSessions.groups[selectedSessionId] : [];

  return (
    <div className="inbox-layout">
      {/* Sidebar: List of Sessions */}
      <aside className="inbox-sidebar">
        <div className="sidebar-header">
          <h2>Inbox</h2>
          <Link to="/" className="nav-link">Exit</Link>
        </div>
        
        {loading ? (
          <div className="sidebar-loading">Loading...</div>
        ) : (
          <div className="session-list">
            {groupedSessions.sortedSessionIds.map(sessionId => {
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
                    <span className="session-id-short">{sessionId.substring(0, 8)}</span>
                    <span className="session-time">
                      {new Date(lastMessage.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <div className="session-preview">
                    {lastMessage.role === 'user' ? 'User: ' : 'Agent: '}
                    {lastMessage.content.length > 40 ? lastMessage.content.substring(0, 40) + '...' : lastMessage.content}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </aside>

      {/* Main View: Chat History */}
      <main className="inbox-main">
        <header className="inbox-main-header">
          <h3>Session Details</h3>
          {selectedSessionId && <span className="full-session-id">{selectedSessionId}</span>}
        </header>

        <div className="chat-window admin-chat-window">
          {currentMessages.length > 0 ? (
            currentMessages.map((msg, index) => (
              <div key={index} className={`message-row ${msg.role}`}>
                <div className={`message-bubble ${msg.role}`}>
                  {msg.role === 'user' ? (
                    msg.content
                  ) : (
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  )}
                  <div className="message-timestamp">
                    {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
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