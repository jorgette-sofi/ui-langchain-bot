import os
import re
import asyncio
from dotenv import load_dotenv
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode, ChatAction
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()

# Import chain components from retrieval.py
from retrieval import generation_chain, rewrite_chain, retriever, format_docs

# Local DB for user chat histories
user_histories = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip().lower()
    if user_input == "/start" or user_input == "hi" or user_input == "hello":
        await update.message.reply_text("Hello! I'm your Home Along assistant. I can help you with verifying documents,"
                                        "checking product prices, and providing details about installment requirements."
                                        "What do you need assistance with today?")
    else:
        await update.message.reply_text("To start chatting, use the command: /start or say hi/hello.")

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip().lower()
    if user_input == "#clear":
        chat_id = update.effective_chat.id
        user_histories[chat_id] = []
        await update.message.reply_text("<i>Chat history cleared.</i>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("To clear chat history, use the command: #clear", parse_mode=ParseMode.HTML)

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with open("helpPrompt.txt", "r", encoding="utf-8") as file:
        helpGuide = file.read()

    user_input = update.message.text.strip().lower()
    if user_input == "/help":
        await update.message.reply_text(helpGuide, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("To view help, use the command: #help", parse_mode=ParseMode.HTML)

def clean_markdown(text):
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'#{1,6}\s*', '', text)
    return text

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_input = update.message.text
    chat_history = user_histories.get(chat_id, [])

    # Typing indicator
    stop_typing = asyncio.Event()
    async def keep_typing():
        while not stop_typing.is_set():
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            await asyncio.sleep(4)
    typing_task = asyncio.create_task(keep_typing())

    # thinking_msg = await update.message.reply_text("<i>Thinking...</i>", parse_mode=ParseMode.HTML)

    try:
        now = datetime.now().strftime('%B %Y')

        query_for_retrieval = await asyncio.to_thread(rewrite_chain.invoke, {
            "input": user_input,
            "chat_history": chat_history,
            "current_date": now
        })

        search_query = f"{query_for_retrieval} {datetime.now().strftime('%B %Y')}"
        retrieved_docs = await asyncio.to_thread(retriever.invoke, search_query)
        formatted_context = format_docs(retrieved_docs)

        answer = await asyncio.to_thread(generation_chain.invoke, {
            "context": formatted_context,
            "input": user_input,
            "current_date": now,
            "chat_history": chat_history
        })

        answer = clean_markdown(answer)

        chat_history.append(HumanMessage(content=user_input))
        chat_history.append(AIMessage(content=answer))
        user_histories[chat_id] = chat_history[-10:]

        # await thinking_msg.edit_text(answer)
        await update.message.reply_text(answer, parse_mode=ParseMode.HTML)

        # for doc in retrieved_docs:
        #     print(doc.metadata)

    except Exception as e:
        # await thinking_msg.edit_text(f"Error: {e}")
        await update.message.reply_text(f"Error: {e}")

    finally:
        stop_typing.set()
        typing_task.cancel()


def main():
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex(r'(?i)^(hi|hello)$'), start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CommandHandler("help", help))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    print("Bot Username:", os.getenv("BOT_USERNAME"))
    main()
