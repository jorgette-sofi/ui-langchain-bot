import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.runnables import RunnablePassthrough
from operator import itemgetter
from langchain_core.output_parsers import StrOutputParser
from datetime import datetime

# 1. Load Environment Variables
load_dotenv()

# 2. Initialize Qdrant Client and Embeddings
client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)
embeddings = OpenAIEmbeddings(model="text-embedding-3-large", openai_api_key=os.getenv("OPENAI_API_KEY"))

# 3. Connect Qdrant Collection
collection_name = "HomeAlong OCR Run 3" 

vector_store = QdrantVectorStore(
    client=client,
    collection_name=collection_name,
    embedding=embeddings,
    content_payload_key="content",
    metadata_payload_key="metadata"
)

# 4. Set up the LLM
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, openai_api_key=os.getenv("OPENAI_API_KEY"))

# 5. Create the Prompt
system_prompt = ( 
    "You are a professional assistant for Home Along. "
    "Answer the user's question using ONLY the provided context.\n\n"

    "CURRENT DATE (AUTHORITATIVE — DO NOT GUESS):\n"
    "Today's date is: {current_date}\n"
    "When a user asks about \"this month\", \"this week\", \"today\", or any relative time reference, you MUST use this date as your reference. NEVER guess, assume, or invent a date. If the retrieved documents do not contain information relevant to the current date/month, use the Fallback Response."
    "Do NOT include a file if the deadline or effective date has already passed relative to today. If a document's date is in the past, ignore it unless the user specifically asks for historical information."
    
    "CRITICAL RULES:\n"
    "1. PLAIN TEXT ONLY: Do absolutely no text formatting. Do not use bolding, asterisks, italics, or markdown bullet points. Output plain, readable text with standard line breaks.\n"
    "2. CITATION: Always provide the Source File and Link at the end of your response.\n"
    "3. FALLBACK: If the answer is not in the context, say: 'I cannot answer this based on the provided documents.'\n\n"
    
    "CONTEXT:\n"
    "{context}" 
)

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "{input}"),
])

def format_docs(docs):
    formatted_chunks = []
    for doc in docs:
        content = doc.page_content
        file_name = doc.metadata.get("original_file_name")
        url = doc.metadata.get("webUrl", "No URL provided")
        
        # Append all
        formatted_chunks.append(f"Source File: {file_name}\nLink: {url}\nContent: {content}\n---")
    
    return "\n".join(formatted_chunks)

# 6. Initialize the separate components
generation_chain = prompt | llm | StrOutputParser()

# The retriever
retriever = vector_store.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 5} 
)

# CHAT LOOP ----------------------------
def start_chat():
    print("====================================================")
    print("\t\tLangChain Chatbot")
    print("====================================================\n")

    while True:
        # 1. Get user input
        user_input = input("\nYou: ")

        # 2. Check for exit commands
        if user_input.lower() in ['exit', 'quit', 'q']:
            print("Shutting down chatbot. Goodbye!")
            break
        
        # 3. Skip empty inputs
        if not user_input.strip():
            continue

        try:
            print("Bot is thinking...\n")
            now = datetime.now().strftime("%B %d, %Y")
            # STEP 1: Retrieve documents
            retrieved_docs = retriever.invoke(user_input)
            
            # STEP 2: Format the retrieved documents
            formatted_context = format_docs(retrieved_docs)
            
            # STEP 3: Pass the clean dictionary, now including the current date
            answer = generation_chain.invoke({
                "context": formatted_context,
                "input": user_input,
                "current_date": now
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
            
            # Print the final answer
            print(f"Bot: {answer}")

        except Exception as e:
            print(f"\n[Error]: {e}")

if __name__ == "__main__":
    start_chat()