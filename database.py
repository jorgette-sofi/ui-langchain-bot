import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    """Helper function to establish a database connection."""
    return psycopg2.connect(DATABASE_URL)

def init_db():
    """Creates the database table if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

def save_message(session_id: str, role: str, content: str):
    """Saves a single message to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (session_id, role, content, timestamp) VALUES (%s, %s, %s, %s)",
        (session_id, role, content, datetime.now())
    )
    conn.commit()
    cursor.close()
    conn.close()

def get_chat_history(session_id: str, limit: int = 10):
    """Retrieves the last N messages for a specific user session."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        "SELECT role, content FROM messages WHERE session_id = %s ORDER BY id DESC LIMIT %s",
        (session_id, limit)
    )
    rows = cursor.fetchall()[::-1] 
    cursor.close()
    conn.close()
    return [{"role": row['role'], "content": row['content']} for row in rows]

def get_all_messages_for_admin():
    """Retrieves all messages for the Admin dashboard."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT session_id, role, content, timestamp FROM messages ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def clear_chat_history(session_id: str):
    """Deletes all messages for a specific session ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE session_id = %s", (session_id,))
    conn.commit()
    cursor.close()
    conn.close()