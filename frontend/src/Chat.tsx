import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import './App.css';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  format?: 'markdown' | 'html';
}

const FALLBACK_GREETING =
  "Hello! I'm your Home Along assistant. I can help you with verifying documents, " +
  "checking product prices, and providing details about installment requirements. " +
  "What do you need assistance with today?";

const FALLBACK_HELP =
  `<p><strong>Available commands:</strong></p>
  <ul>
    <li><code>/start</code>, <code>hi</code>, <code>hello</code> — Start a conversation</li>
    <li><code>#clear</code> or <code>/clear</code> — Clear your chat history</li>
    <li><code>#help</code> or <code>/help</code> — Show this help message</li>
  </ul>`;

function Chat() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: "Hi! I'm the Home Along assistant. How can I help you today?", timestamp: new Date() }
  ]);
  const [input, setInput] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [sessionId, setSessionId] = useState<string | null>(() =>
    localStorage.getItem('ha_session_id')
  );

  useEffect(() => {
    if (sessionId) {
      localStorage.setItem('ha_session_id', sessionId);
    } else {
      localStorage.removeItem('ha_session_id');
    }
  }, [sessionId]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const callApi = async (message: string, sid: string | null) => {
    const response = await fetch('http://localhost:8000/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, session_id: sid }),
    });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json();
  };

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage: Message = { role: 'user', content: input, timestamp: new Date() };
    const updatedMessages = [...messages, userMessage];
    const clean = input.trim().toLowerCase();
    setInput('');

    // For preset keywords: show user message, call API silently (no loading indicator),
    // so messages are still saved to DB and visible in admin.
    if (['/start', 'hi', 'hello', '#help', '/help'].includes(clean)) {
      const isHelp = clean === '#help' || clean === '/help';
      setMessages(updatedMessages);
      try {
        const data = await callApi(input, sessionId);
        if (!sessionId) setSessionId(data.session_id);
        setMessages([...updatedMessages, {
          role: 'assistant',
          content: data.reply,
          timestamp: new Date(),
          format: isHelp ? 'html' : 'markdown',
        }]);
      } catch {
        const fallback = isHelp ? FALLBACK_HELP : FALLBACK_GREETING;
        setMessages([...updatedMessages, {
          role: 'assistant',
          content: fallback,
          timestamp: new Date(),
          format: isHelp ? 'html' : 'markdown',
        }]);
      }
      return;
    }

    if (['#clear', '/clear'].includes(clean)) {
      setMessages(updatedMessages);
      try {
        const data = await callApi(input, sessionId);
        if (!sessionId) setSessionId(data.session_id);
        setMessages([...updatedMessages, { role: 'assistant', content: data.reply, timestamp: new Date() }]);
      } catch {
        setMessages([...updatedMessages, { role: 'assistant', content: "Chat memory cleared.", timestamp: new Date() }]);
      }
      return;
    }

    setMessages(updatedMessages);
    setIsLoading(true);

    try {
      const data = await callApi(input, sessionId);
      if (!sessionId) setSessionId(data.session_id);
      setMessages([...updatedMessages, { role: 'assistant', content: data.reply, timestamp: new Date() }]);
    } catch (error) {
      console.error("Failed to fetch response:", error);
      setMessages([...updatedMessages, { role: 'assistant', content: "Sorry, I couldn't connect to the server.", timestamp: new Date() }]);
    } finally {
      setIsLoading(false);
    }
  };

  const formatTime = (date: Date) =>
    date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <div className="app-container">
      <header className="chat-header">
        <div className="chat-header-content">
          <div className="chat-header-avatar">HA</div>
          <div className="chat-header-text">
            <h1>Home Along</h1>
            <span className="chat-header-status">
              <span className="status-dot" />
              Online
            </span>
          </div>
        </div>
      </header>

      <main className="chat-window">
        {messages.map((msg, index) => (
          <div key={index} className={`message-row ${msg.role}`}>
            {msg.role === 'assistant' && (
              <div className="msg-avatar assistant-avatar">HA</div>
            )}
            <div className={`message-bubble ${msg.role}`}>
              {msg.role === 'user' ? (
                msg.content
              ) : msg.format === 'html' ? (
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
        ))}
        {isLoading && (
          <div className="message-row assistant">
            <div className="msg-avatar assistant-avatar">HA</div>
            <div className="message-bubble assistant loading-indicator">
              Thinking<span>.</span><span>.</span><span>.</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </main>

      <footer className="input-container">
        <div className="input-box">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Message"
            disabled={isLoading}
            autoFocus
          />
          <button onClick={handleSend} disabled={isLoading || !input.trim()}>
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M22 2L11 13M22 2L15 22L11 13M11 13L2 9L22 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>
        <div className="input-hint">Type /help for available commands</div>
      </footer>
    </div>
  );
}

export default Chat;
