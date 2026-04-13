import os
import re
import yaml
import logging
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

logging.basicConfig(
    level=logging.ERROR,
    format="[%(levelname)s]: %(message)s",
)
logger = logging.getLogger(__name__)

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

        # 4. Load Prompts
        self.all_prompts = self.load_prompts()
        self.translator_prompt = self.all_prompts.get("translator_prompt", "")
        self.system_prompt = self.all_prompts.get("system_prompt", "")
        self.input_checker_prompt = self.all_prompts.get("input_checker_prompt", "")
        self.greetings_message = self.all_prompts.get("greetings_message", "")
        self.no_access_message = self.all_prompts.get("no_access_message", "")
        self.invalid_input_message = self.all_prompts.get("invalid_input_message", "")

        # 5. Setup Chains
        self._setup_chains()

    def load_prompts(self):
        try:
            with open("prompts.yaml", "r", encoding="utf-8") as file:
                return yaml.safe_load(file)
        except Exception as e:
            logger.error("Error loading prompts.yaml: %s", e)
            return {}

    def _setup_chains(self):
        if not self.system_prompt:
            logger.error("system_prompt is empty or missing from prompts.yaml")
        if not self.translator_prompt:
            logger.error("translator_prompt is empty or missing from prompts.yaml")

        translate_prompt = ChatPromptTemplate.from_messages([
            ("system", self.translator_prompt),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
        ])
        self.rewrite_chain = translate_prompt | self.llm | StrOutputParser()

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
        ])
        self.generation_chain = prompt | self.llm | StrOutputParser()

        if self.input_checker_prompt:
            checker_prompt = ChatPromptTemplate.from_messages([
                ("system", self.input_checker_prompt),
                ("human", "{input}"),
            ])
            self.input_checker_chain = checker_prompt | self.llm | StrOutputParser()
        else:
            self.input_checker_chain = None
            logger.error("input_checker_prompt is missing from prompts.yaml")

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
            return (self.greetings_message) if self.greetings_message else "Hello! How can I assist you today?"
        
        # Handle Clear History
        if clean_input in ["/clear", "#clear"]:
            return self.clear_history(session_id)
            
        # Handle Help
        if clean_input in ["/help", "#help"]:
            return self.all_prompts.get("help_prompt", "Help guide is currently unavailable. Please contact the administrator.")
        
        # Validate input before hitting the full pipeline
        if self.input_checker_chain:
            validation = await self.input_checker_chain.ainvoke({"input": user_input})
            if validation.strip().upper() == "INVALID":
                return self.invalid_input_message or "I'm sorry, I couldn't understand your message. Could you please rephrase it?"

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
            logger.error("Error in get_response for session_id=%s: %s", session_id, e, exc_info=True)
            return f"An error occurred: {str(e)}"