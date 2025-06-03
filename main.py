from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from pymongo import MongoClient
import random
from collections import defaultdict
import asyncio
from datetime import datetime, timedelta
import pytz
UTC = pytz.utc

# Bot Token & MongoDB Setup
TELEGRAM_BOT_TOKEN = '8156506636:AAEDnTMsUBCNWCSDsgi_5VrIADNpNv5AAnk'
client = MongoClient("mongodb+srv://rishi:ipxkingyt@rishiv.ncljp.mongodb.net/?retryWrites=true&w=majority&appName=rishiv")
db = client['lecturebot']
lecture_col = db['lectures']
verified_col = db['verified_users']
user_video_state = defaultdict(dict)
user_state = {}  # user_id: subject
pending_col = db['pending_passwords']
# Add at the top
user_waiting_for_password = set()
ADMIN_ID = 1944182800  # ← yahan apna Telegram user ID daal do
password_col = db['dynamic_passwords']
premium_col = db["premium_users"]

# Passwords and Links
passwords_and_links = {
    "864028": "https://linksgo.in/odOy8O",
    "25115452": "https://linksgo.in/JWeb0v",
    "284846": "https://linksgo.in/iNY9WUUv",
    "4558": "https://linksgo.in/asFZ5hRY",
    "H23365948": "https://linksgo.in/YwTy",
    "64136451": "https://linksgo.in/PNMAR",
    "791564384": "https://linksgo.in/hnUe0ms",
    "64956735": "https://linksgo.in/niYt",
    "6582352": "https://linksgo.in/f0mhkrrc",
    "5485313": "https://linksgo.in/oZ1vRH",
}

# Subject state and mode
user_state = {}  # user_id: subject
simple_mode = {}  # user_id: True/False

# Command: /addpass <password> <link>
async def add_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ You are not authorized to use this command.")

    if len(context.args) < 2:
        return await update.message.reply_text("Usage: /addpass <password> <link>")

    password = context.args[0]
    link = " ".join(context.args[1:])

    password_col.update_one(
        {"password": password},
        {"$set": {"link": link, "created_at": datetime.now(UTC)}},
        upsert=True
    )
    await update.message.reply_text(f"✅ Password '{password}' with link added/updated.")

# Command: /allpass (admin only)
async def list_passwords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ You are not authorized to view this.")

    entries = list(password_col.find())
    if not entries:
        return await update.message.reply_text("No passwords found.")

    msg = "\n\n".join([f"**{entry['password']}** → {entry['link']}" for entry in entries])
    await update.message.reply_text(msg, parse_mode="Markdown")

# /post command
async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Subject nahi diya. Use: /post Physics [simple]")
        return

    args = context.args
    subject = " ".join(args[:-1]) if args[-1].lower() == "simple" else " ".join(args)
    is_simple = args[-1].lower() == "simple"

    user_id = update.effective_user.id
    user_state[user_id] = subject
    simple_mode[user_id] = is_simple

    mode_text = " (Simple Mode ON)" if is_simple else ""
    await update.message.reply_text(f"✅ Subject set: {subject}{mode_text}\nAb videos bhejo.")

# Video handler
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    subject = user_state.get(user_id)
    is_simple = simple_mode.get(user_id, False)

    if not subject:
        await update.message.reply_text("❌ Pehle /post command se subject set karo.")
        return

    caption = update.message.caption or ""
    chapter_title = ""
    topic_line = ""

    if is_simple:
        # In simple mode, use full caption as title
        topic_line = caption.strip()
    else:
        # Filter mode
        lines = caption.split('\n')
        filtered_lines = []
        for line in lines:
            lower_line = line.lower()
            if all(keyword not in lower_line for keyword in ['classnotes', 'dpp', '📦', '📅', 'watch link', '🔗']):
                filtered_lines.append(line.strip())

        if filtered_lines and "concept" in filtered_lines[0].lower():
            chapter_title = filtered_lines[0]
            topic_line = " ".join(filtered_lines[1:]).strip() if len(filtered_lines) > 1 else ""
        elif filtered_lines:
            topic_line = " ".join(filtered_lines).strip()

    # Save to database
    lecture_count = lecture_col.count_documents({})
    lecture_id = lecture_count + 1

    lecture_col.insert_one({
        "lecture_id": lecture_id,
        "chat_id": update.message.chat_id,
        "message_id": update.message.message_id,
        "subject": subject
    })

    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start=lec{lecture_id}"
    date_today = datetime.now().strftime("%d-%m-%Y")

    # Final message
    text = ""
    if chapter_title:
        text += f" {chapter_title}\n"
    if topic_line:
        text += f" {topic_line}\n"
    text += f"\n📦 {subject}\n📅 {date_today}\n\n🔗 Watch Link : [Click Here]({link})"

    await update.message.reply_text(text, parse_mode="Markdown")

import re

def extract_lecture_title(caption: str, subject: str) -> str:
    lecture_number = ""
    topic = ""
    teacher = ""

    if caption:
        # Extract lecture number
        match = re.search(r"(📍|𝗟𝗲𝗰𝘁𝘂𝗿𝗲)\s*(Lecture\s*)?(\d+)", caption, re.IGNORECASE)
        if match:
            lecture_number = f"Lecture {match.group(3)}"

        # Extract topic
        match = re.search(r"(⚜️|💡)\s*([^\n]+)", caption)
        if match:
            topic = match.group(2).strip()

        # Extract teacher
        match = re.search(r"(⚡️|🔮|𝗕𝘆)\s*([^\n]+)", caption)
        if match:
            teacher = match.group(2).strip()

    parts = [part for part in [lecture_number, topic, teacher, subject] if part]
    return " | ".join(parts)

from datetime import datetime, timedelta, timezone

# /start command with lecture access
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    user_id = update.effective_user.id

    # First: Check premium access
    premium_user = premium_col.find_one({"user_id": user_id})
    if premium_user and "approved_at" in premium_user:
        approved_at = premium_user["approved_at"]
        if approved_at.tzinfo is None:
            approved_at = approved_at.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) - approved_at < timedelta(days=30):
            # If /start lecID provided
            if args and args[0].startswith("lec"):
                try:
                    lecture_id = int(args[0][3:])
                    lecture = lecture_col.find_one({"lecture_id": lecture_id})

                    if lecture:
                        await context.bot.forward_message(
                            chat_id=update.message.chat_id,
                            from_chat_id=lecture["chat_id"],
                            message_id=lecture["message_id"]
                        )
                        return
                except Exception as e:
                    print(f"Error accessing lecture: {e}")
                    return

            return await update.message.reply_text(
                "✅ *Aapka premium access active hai!* Kisi bhi lecture link pe click karke dekh sakte ho.",
                parse_mode="Markdown"
            )

    # Second: Check normal verified access
    user_data = verified_col.find_one({"user_id": user_id})
    if not user_data or "access_granted_time" not in user_data:
        return await send_verification_prompt(update)

    granted_time = user_data["access_granted_time"]
    if granted_time.tzinfo is None:
        granted_time = granted_time.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) - granted_time > timedelta(hours=1):
        verified_col.delete_one({"user_id": user_id})
        return await send_verification_prompt(update)

    # If /start lecID provided
    if args and args[0].startswith("lec"):
        try:
            lecture_id = int(args[0][3:])
            lecture = lecture_col.find_one({"lecture_id": lecture_id})

            if lecture:
                await context.bot.forward_message(
                    chat_id=update.message.chat_id,
                    from_chat_id=lecture["chat_id"],
                    message_id=lecture["message_id"]
                )
                return
        except Exception as e:
            print(f"Error accessing lecture: {e}")
            return

    await update.message.reply_text(
        "✅ *Aapka access active hai!* Kisi bhi lecture link pe click karke dekh sakte ho.",
        parse_mode="Markdown"
    )
    
async def verify_user(user_id, password, message_func):
    user_password = password
    pending = pending_col.find_one({"user_id": user_id})

    if pending and user_password == pending.get("password"):
        verified_col.update_one(
            {"user_id": user_id},
            {"$set": {
                "access_granted_time": datetime.utcnow()
            }},
            upsert=True
        )
        pending_col.delete_one({"user_id": user_id})

        await message_func(
            "✅ *Password valid!* Aapka verification ho chuka hai.\n\n"
            "⏳ *Ab aapko 1 hour ke liye lecture access mil gaya hai.*\n"
            "Uske baad fir se verification karna padega.",
            parse_mode="Markdown"
        )
    else:
        await message_func(
            "❌ *Galat ya expire ho chuka password!* Kripya sahi password daalein.",
            parse_mode="Markdown"
        )
        
from datetime import datetime, timedelta, UTC

def is_access_valid(user_id):
    # Check premium access first
    premium = premium_col.find_one({"user_id": user_id})
    if premium and "approved_at" in premium:
        approved_at = premium["approved_at"]
        if approved_at.tzinfo is None:
            approved_at = approved_at.replace(tzinfo=UTC)
        if datetime.now(UTC) - approved_at < timedelta(days=30):
            return True
        else:
            premium_col.delete_one({"user_id": user_id})  # auto-remove expired premium

    # Then check 1-hour verified access
    record = verified_col.find_one({"user_id": user_id})
    if not record or "access_granted_time" not in record:
        return False

    granted_time = record["access_granted_time"]

    # Ensure timezone-aware
    if granted_time.tzinfo is None:
        granted_time = granted_time.replace(tzinfo=UTC)

    return datetime.now(UTC) - granted_time < timedelta(hours=1)
        
async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /verify <password>")
        return

    password = context.args[0]
    await verify_user(user_id, password, update.message.reply_text)
    
from telegram.ext import CallbackQueryHandler

async def handle_verify_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # <-- This should be done ASAP once

    user_id = query.from_user.id
    user_waiting_for_password.add(user_id)  # Mark user as waiting for password

    await query.message.reply_text(
        "📝 *Please enter your password now:*",
        parse_mode="Markdown"
    )
    
async def send_verification_prompt(update: Update):
    all_entries = list(password_col.find())

    if not all_entries:
        await update.message.reply_text("❌ No passwords available. Admin should add one using /addpass")
        return

    selected = random.choice(all_entries)
    password = selected['password']
    link = selected['link']

    button = InlineKeyboardMarkup([
    [InlineKeyboardButton("🎁 Get Ads Free", callback_data="ads_free")],
    [InlineKeyboardButton("🔓 Lecture Unlock Link", url=link)],
    [InlineKeyboardButton("✅ Verify Password", callback_data=f"verify_{password}")]
])

    pending_col.update_one(
        {"user_id": update.effective_user.id},
        {"$set": {"password": password}},
        upsert=True
    )

    await update.message.reply_text(
        "❌ *Aapke paas abhi lecture access nahi hai!* ❌\n\n"
        "✅ *Access chahiye?* Neeche diye gaye button par click karke password hasil karo.\n"
        "Uske baad `/verify <password>` command se verify karo.\n\n"
        "⏳ *Note:* Aapko *1 hour* ke liye access milega. Uske baad dobara verify karna padega.",
        parse_mode="Markdown",
        reply_markup=button
    )
    
async def handle_password_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_waiting_for_password:
        return  # Ignore if not waiting for password

    password = update.message.text.strip()
    user_waiting_for_password.discard(user_id)  # Remove from waiting list

    await verify_user(user_id, password, update.message.reply_text)
    
async def handle_ads_free_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    await query.message.reply_text(
        f"💰 *Ads-Free Access* ke liye ₹100 pay karo:\n\n"
        f"UPI ID--> `aditya802302@axl`\n\n"
        "✅ Payment ke baad screenshot bhejo yahi pe.\n"
        "Hum manual approval ke baad 30 din ka access denge.",
        parse_mode="Markdown"
    )
    
async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        user = update.effective_user
        caption = f"🧾 *Payment Screenshot Received!*\n\n👤 User: @{user.username or 'N/A'}\n🆔 ID: {user.id}"
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=update.message.photo[-1].file_id, caption=caption, parse_mode="Markdown")
        await update.message.reply_text("✅ Screenshot bhej diya gaya admin ko. Approval ke liye wait karo.")
        
async def approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ You are not authorized to use this command.")
    
    if not context.args or len(context.args) != 1:
        return await update.message.reply_text("Usage: /approve <user_id>")

    try:
        user_id_str = context.args[0]
        print("Received user_id argument:", user_id_str)
        user_id = int(user_id_str)

        result = premium_col.update_one(
            {"user_id": user_id},
            {"$set": {"approved_at": datetime.now(UTC)}},
            upsert=True
        )
        print("MongoDB update result:", result.raw_result)

        await update.message.reply_text(f"✅ User {user_id} approved for 30 days.")
    except Exception as e:
        print("Exception occurred:", e)
        await update.message.reply_text("❌ Invalid user_id.")
        
def is_access_valid(user_id):
    # Check premium access
    premium = premium_col.find_one({"user_id": user_id})
    if premium:
        approved_at = premium["approved_at"]
        if approved_at.tzinfo is None:
            approved_at = approved_at.replace(tzinfo=UTC)
        if datetime.now(UTC) - approved_at < timedelta(days=30):
            return True
        else:
            premium_col.delete_one({"user_id": user_id})  # Remove expired

    # Check normal password access
    record = verified_col.find_one({"user_id": user_id})
    if not record or "access_granted_time" not in record:
        return False

    granted_time = record["access_granted_time"]
    if granted_time.tzinfo is None:
        granted_time = granted_time.replace(tzinfo=UTC)

    return datetime.now(UTC) - granted_time < timedelta(hours=1)



import asyncio

async def print_hello():
    while True:
        print("Hello world")
        await asyncio.sleep(5)

async def run():
    

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", post))
    app.add_handler(CommandHandler("verify", verify))
    app.add_handler(CommandHandler("addpass", add_password))
    app.add_handler(CommandHandler("allpass", list_passwords))
    app.add_handler(CallbackQueryHandler(handle_ads_free_button, pattern="ads_free"))
    app.add_handler(CommandHandler("approve", approve_user))
    app.add_handler(MessageHandler(filters.PHOTO, handle_screenshot))
    app.add_handler(CallbackQueryHandler(handle_verify_button))
    app.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE, handle_video))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password_input))

    asyncio.create_task(print_hello())
    await app.run_polling()

if __name__ == "__main__":
    try:
        import nest_asyncio
        nest_asyncio.apply()

        

        asyncio.get_event_loop().run_until_complete(run())
    except RuntimeError as e:
        print(f"RuntimeError: {e}")