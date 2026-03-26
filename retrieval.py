import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from datetime import datetime
import time
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()

MAX_CONTEXT_CHARS = 10000 # Limits Tokens

client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)
embeddings = OpenAIEmbeddings(model="text-embedding-3-large", openai_api_key=os.getenv("OPENAI_API_KEY"))

collection_name = "HomeAlong OCR Run 3" 

vector_store = QdrantVectorStore(
    client=client,
    collection_name=collection_name,
    embedding=embeddings,
    content_payload_key="content",
    metadata_payload_key="metadata"
)

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, openai_api_key=os.getenv("OPENAI_API_KEY"))

# Load system prompt
with open("system_prompt.txt", "r", encoding="utf-8") as file:
    system_prompt = file.read()

# History placeholder
prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
])

# Answer Format
def format_docs(docs):
    seen = set()
    formatted_chunks = []
    for doc in docs:
        file_name = doc.metadata.get("original_file_name")
        if file_name in seen:
            continue
        seen.add(file_name)
        url = doc.metadata.get("webUrl", "No URL provided")
        # Sanitize content — remove null bytes and control characters
        content = doc.page_content.replace("\x00", "").encode("utf-8", errors="ignore").decode("utf-8")
        formatted_chunks.append(f"Source File: {file_name}\nLink: {url}\nContent: {content}\n---")
    result = "\n".join(formatted_chunks)
    return result[:MAX_CONTEXT_CHARS]

# Initialize the separate components
generation_chain = prompt | llm | StrOutputParser()

rewrite_prompt = ChatPromptTemplate.from_messages([
    ("system", "Today's date is {current_date}. Rewrite the user's question to be fully standalone. IMPORTANT: Replace ALL relative time references (this month, this week, today, etc.) with the actual month name and year based on today's date. Return only the rewritten question."),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
])

rewrite_chain = rewrite_prompt | llm | StrOutputParser()

# The retriever
# retriever = vector_store.as_retriever(
#     search_type="similarity",
#     search_kwargs={"k": 5} 
# )
retriever = vector_store.as_retriever(
    search_type="mmr",
    search_kwargs={"k": 5, "fetch_k": 20, "lambda_mult": 0.7}
)

# CHAT LOOP ----------------------------
def start_chat():
    chat_history = []
    print("====================================================")
    print("\t\tLangChain Chatbot")
    print("====================================================\n")

    while True:
        user_input = input("\nYou: ")

        if user_input.lower() in ['exit', 'quit', 'q']:
            print("Shutting down chatbot. Goodbye!")
            break
        
        if not user_input.strip():
            continue

        try:
            print("Bot is thinking...\n")
            now = datetime.now().strftime('%B %Y')

            # Rewrite query if there's history, then retrieve
            query_for_retrieval = rewrite_chain.invoke({
                "input": user_input,
                "chat_history": chat_history,
                "current_date": now
            })

            search_query = f"{query_for_retrieval} {datetime.now().strftime('%B %Y')}"
            retrieved_docs = retriever.invoke(search_query)

            # Format the retrieved documents
            formatted_context = format_docs(retrieved_docs)

            # Pass the clean dictionary for output
            answer = generation_chain.invoke({
                "context": formatted_context,
                "input": query_for_retrieval,
                "current_date": now,
                "chat_history": chat_history
            })

            # # Print the context the LLM actually received
            # print("\n--- WHAT THE LLM SEES ---")
            # if not retrieved_docs:
            #     print("Retriever found no documents.")
            # else:
            #     for i, doc in enumerate(retrieved_docs):
            #         print(f"\n--- Chunk {i+1} ---")
            #         print(f"Content: '{doc.page_content[:150]}...'") 
            #         file_name = doc.metadata.get('original_file_name')
            #         file_type = doc.metadata.get('filetype')
            #         webUrl = doc.metadata.get('webUrl')
            #         print(f"Filename: {file_name}\nFile Type: {file_type}\nwebUrl: {webUrl}")
            # print("-------------------------\n")
            
            # Output the final answer
            print(f"Bot: {answer}")

            chat_history.append(HumanMessage(content=user_input))
            chat_history.append(AIMessage(content=answer))
            chat_history = chat_history[-10:] 

        except Exception as e:
            print(f"\n[Error]: {e}")

if __name__ == "__main__":
    start_chat()