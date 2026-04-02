import os
import re
from dotenv import load_dotenv
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage

# LangChain & Qdrant Imports
from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Database functions for persistent history
from database import get_chat_history, clear_chat_history

load_dotenv()

class chatbotEngine:
    def __init__(self):
        self.MAX_CONTEXT_CHARS = 10000
        
        # 1. Initialize Qdrant Vector Store
        self.client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY")
        )
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-large", 
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        self.vector_store = QdrantVectorStore(
            client=self.client,
            collection_name="HomeAlong OCR Run 3",
            embedding=self.embeddings,
            content_payload_key="content",
            metadata_payload_key="metadata"
        )
        
        # 2. Initialize Retriever
        self.retriever = self.vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 6, "fetch_k": 30, "lambda_mult": 0.6}
        )

        # 3. Initialize LLM
        self.llm = ChatOpenAI(
            model="gpt-4o-mini", 
            temperature=0.1, 
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )

        # 4. Setup Chains
        self._setup_chains()

    def _setup_chains(self):
        # System Prompt
        try:
            with open("system_prompt.txt", "r", encoding="utf-8") as file:
                system_prompt = file.read()
        except FileNotFoundError:
            system_prompt = "You are a helpful assistant."

        # Generation Chain
        citation_instruction = (
            "After each specific piece of information you provide, immediately append a markdown "
            "link to the document it came from — format: [📄 filename](url). "
            "Use the exact filename and URL from the context. "
            "Only cite a source right next to the content it supports. "
            "Do NOT add a separate Sources or References section at the end."
        )

        gen_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("system", citation_instruction),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
        ])
        self.generation_chain = gen_prompt | self.llm | StrOutputParser()

        # Rewrite Chain
        rewrite_prompt = ChatPromptTemplate.from_messages([
            ("system", "Today's date is {current_date}. Rewrite the user's question to be fully standalone. IMPORTANT: Replace ALL relative time references (this month, this week, today, etc.) with the actual month name and year based on today's date. Return only the rewritten question."),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
        ])
        self.rewrite_chain = rewrite_prompt | self.llm | StrOutputParser()

    def _format_docs(self, docs):
        seen = set()
        formatted_chunks = []
        for doc in docs:
            file_name = doc.metadata.get("original_file_name")
            if file_name in seen:
                continue
            seen.add(file_name)
            url = doc.metadata.get("webUrl", "No URL provided")
            content = doc.page_content.replace("\x00", "").encode("utf-8", errors="ignore").decode("utf-8")
            formatted_chunks.append(f"Source File: {file_name}\nLink: {url}\nContent: {content}\n---")
        return "\n".join(formatted_chunks)[:self.MAX_CONTEXT_CHARS]

    def _clean_markdown(self, text):
        # Only strip headers — bold/italic are preserved so ReactMarkdown renders them properly
        text = re.sub(r'#{1,6}\s+', '', text)
        return text.strip()

    def get_history(self, session_id: str):
        """Load chat history from Postgres and convert to LangChain message objects."""
        rows = get_chat_history(session_id, limit=10)
        history = []
        for row in rows:
            if row["role"] == "user":
                history.append(HumanMessage(content=row["message"]))
            elif row["role"] == "assistant":
                history.append(AIMessage(content=row["message"]))
        return history

    def clear_history(self, session_id: str):
        """Delete this session's messages from Postgres."""
        clear_chat_history(session_id)
        return "Chat history cleared."

    async def get_response(self, session_id: str, user_input: str) -> str:
        """
        Main function to be called by your web platform.
        """
        clean_input = user_input.strip().lower()
        
        # Handle Start/Greetings
        if clean_input in ["/start", "hi", "hello"]:
            return (
                "Hello! I'm your Home Along assistant. I can help you with verifying documents, "
                "checking product prices, and providing details about installment requirements. "
                "What do you need assistance with today?"
            )
        
        # Handle Clear History
        if clean_input in ["/clear", "#clear"]:
            return self.clear_history(session_id)
            
        # Handle Help
        if clean_input in ["/help", "#help"]:
            try:
                with open("helpPrompt.txt", "r", encoding="utf-8") as file:
                    return file.read()
            except FileNotFoundError:
                return "Help guide is currently unavailable. Please contact the administrator."
        
        chat_history = self.get_history(session_id)
        now = datetime.now().strftime('%B %Y')

        try:
            # 1. Rewrite Query
            query_for_retrieval = await self.rewrite_chain.ainvoke({
                "input": user_input,
                "chat_history": chat_history,
                "current_date": now
            })

            # 2. Retrieve Documents
            search_query = f"{query_for_retrieval} {now}"
            retrieved_docs = await self.retriever.ainvoke(search_query)

            if not retrieved_docs:
                return (
                    "Wala akong nahanap na dokumentong may kaugnayan sa iyong tanong. "
                    "Subukan mong i-rephrase ang tanong, o makipag-ugnayan sa inyong admin para sa tulong."
                )

            formatted_context = self._format_docs(retrieved_docs)

            # 3. Generate Answer
            answer = await self.generation_chain.ainvoke({
                "context": formatted_context,
                "input": query_for_retrieval, 
                "current_date": now,
                "chat_history": chat_history
            })

            clean_answer = self._clean_markdown(answer)

            # History is saved to Postgres by main.py — no in-memory update needed
            return clean_answer

        except Exception as e:
            return f"An error occurred: {str(e)}"