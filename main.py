from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import uuid

# NEW: Import your database functions
from database import init_db, save_message, get_all_messages_for_admin
from retrieval import ask_agent 

# NEW: Initialize the Supabase tables when the server starts
init_db()

app = FastAPI(title="RAG Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# UPDATED: Added session_id
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None 

# UPDATED: Added session_id
class ChatResponse(BaseModel):
    reply: str
    session_id: str

ChatRequest.model_rebuild()
ChatResponse.model_rebuild()

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # If the web user doesn't have a session ID yet, generate a unique one
        current_session = request.session_id if request.session_id else f"web_{uuid.uuid4().hex[:8]}"
        
        # 1. Save the User's message to Supabase
        save_message(current_session, "user", request.message)

        # 2. Get the agent's reply (passing the session_id so LangChain knows who is talking)
        agent_reply = ask_agent(request.message, current_session) 
        
        # 3. Save the Agent's reply to Supabase
        save_message(current_session, "assistant", agent_reply)
        
        return ChatResponse(reply=agent_reply, session_id=current_session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

#Admin dashboard calls to get the inbox data
@app.get("/api/admin/logs")
async def get_admin_logs():
    try:
        logs = get_all_messages_for_admin()
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))