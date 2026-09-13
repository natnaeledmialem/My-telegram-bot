import os
import re
import sqlite3
import logging
from datetime import datetime
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

# --- FLASK KEEP ALIVE SERVER SETUP ---
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app_flask.run(host='0.0.0.0', port=port)

# Flask Server በ Background Thread እንዲነሳ ማድረግ
Thread(target=run_flask, daemon=True).start()

# --- CONFIGURATION ---
BOT_TOKEN = "8985332397:AAGV00bxDG0ccnr5AGNmYUwNdBNrDh97ayE"
ADMIN_ID = 8825122216
PAYMENT_PROOF_CHANNEL = "@Paymentprooff2"
REFERRAL_REWARD = 2.0  # 2 ETB

# States for ConversationHandlers
SET_WALLET_VAL = 0
WITHDRAW_TYPE, WITHDRAW_AMOUNT = range(1, 3)
ADD_CHANNEL_STATE, ADD_TASK_TITLE, ADD_TASK_LINK, ADD_TASK_REWARD = range(3, 7)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- DATABASE SETUP ---
def db_connect():
    return sqlite3.connect("ethio_smart_bot.db")

def init_db():
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0.0,
            wallet TEXT DEFAULT '',
            referrer_id INTEGER,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_username TEXT UNIQUE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            link TEXT,
            reward REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS completed_tasks (
            user_id INTEGER,
            task_id INTEGER,
            PRIMARY KEY (user_id, task_id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- HELPER FUNCTIONS ---
def get_main_keyboard():
    # በ 3 Row (ረድፍ) እና በ Bold ፅሁፍ የተደራጁ የሜኑ ቁልፎች
    keyboard = [
        [
            InlineKeyboardButton("💰 **የእኔ ባላንስ**", callback_data="btn_balance"),
            InlineKeyboardButton("👥 **ሪፈራል / ጋብዝ**", callback_data="btn_referral"),
            InlineKeyboardButton("📢 **ቻናሎች**", callback_data="btn_channels")
        ],
        [
            InlineKeyboardButton("🎯 **ስራዎች (Tasks)**", callback_data="btn_tasks"),
            InlineKeyboardButton("💳 **ዋሌት ማስተካከያ**", callback_data="btn_wallet"),
            InlineKeyboardButton("🏧 **ብር ለማውጣት**", callback_data="btn_withdraw")
        ],
        [
            InlineKeyboardButton("📊 **ስታቲስቲክስ**", callback_data="btn_stats"),
            InlineKeyboardButton("⚙️ **አድሚን ፓነል**", callback_data="btn_admin")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    referrer_id = None

    if args and args[0].isdigit():
        possible_referrer = int(args[0])
        if possible_referrer != user_id:
            referrer_id = possible_referrer

    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.execute("INSERT INTO users (user_id, referrer_id) VALUES (?, ?)", (user_id, referrer_id))
        conn.commit()
        if referrer_id:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REFERRAL_REWARD, referrer_id))
            conn.commit()
            try:
                await context.bot.send_message(
                    chat_id=referrer_id, 
                    text=f"🎉 **አዲስ ሰው በጋበዙበት ሊንክ ተመዝግቧል!**\n🎁 **+{REFERRAL_REWARD} ETB** ወደ ባላንስዎ ተጨምሯል።",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

    conn.close()
    
    welcome_text = (
        f"👋 **ሰላም {update.effective_user.first_name}!**\n\n"
        "✨ **ወደ ቦቱ በደህና መጡ!**\n"
        "ከታች ያሉትን ቁልፎች በመጠቀም ስራዎችን መስራት፣ ሰዎችን መጋበዝ እና ብር ማውጣት ይችላሉ።"
    )
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard(), parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.reply_text(welcome_text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    conn = db_connect()
    cursor = conn.cursor()

    if data == "btn_balance":
        cursor.execute("SELECT balance, wallet FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        balance = row[0] if row else 0.0
        wallet = row[1] if row and row[1] else "ግልፅ አልተደረገም"
        
        msg = f"💳 **የእኔ ባላንስ መረጃ**\n\n💵 **ሂሳብ፦** `{balance}` ETB\n👛 **ዋሌት፦** `{wallet}`"
        await query.message.edit_text(msg, reply_markup=get_main_keyboard(), parse_mode="Markdown")

    elif data == "btn_referral":
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
        count = cursor.fetchone()[0]
        
        msg = (
            f"🔗 **የእርስዎ የሪፈራል ሊንክ፦**\n`{ref_link}`\n\n"
            f"👥 **የጋበዟቸው ሰዎች ብዛት፦** `{count}`\n"
            f"🎁 **ለእያንዳንዱ ሰው የሚያገኙት፦** `{REFERRAL_REWARD}` ETB"
        )
        await query.message.edit_text(msg, reply_markup=get_main_keyboard(), parse_mode="Markdown")

    elif data == "btn_stats":
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        msg = f"📊 **የቦቱ ጠቅላላ ስታቲስቲክስ**\n\n👥 **ጠቅላላ ተጠቃሚዎች፦** `{total_users}`"
        await query.message.edit_text(msg, reply_markup=get_main_keyboard(), parse_mode="Markdown")

    conn.close()

# --- CONVERSATION HANDLERS (WALLET & WITHDRAW) ---
async def wallet_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("📝 **እባክዎን የባንክ ሂሳብ ቁጥርዎን ወይም የስልክ ቁጥርዎን ያስገቡ፦**", parse_mode="Markdown")
    return SET_WALLET_VAL

async def wallet_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet = update.message.text
    user_id = update.effective_user.id
    
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET wallet = ? WHERE user_id = ?", (wallet, user_id))
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ **የባንክ ሂሳብ ቁጥርዎ በደህና ተቀምጧል!**", reply_markup=get_main_keyboard(), parse_mode="Markdown")
    return ConversationHandler.END

async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("SELECT balance, wallet FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[1]:
        await query.message.reply_text("⚠️ **እባክዎን መጀመሪያ '💳 ዋሌት ማስተካከያ' ላይ ገብተው ሂሳብ ቁጥርዎን ያስገቡ!**", reply_markup=get_main_keyboard(), parse_mode="Markdown")
        return ConversationHandler.END

    if row[0] < 10.0: # Minimum withdraw 10 ETB
        await query.message.reply_text("⚠️ **ብር ለማውጣት ዝቅተኛው መጠን 10 ETB ነው።**", reply_markup=get_main_keyboard(), parse_mode="Markdown")
        return ConversationHandler.END

    await query.message.reply_text("💸 **ማውጣት የሚፈልጉትን የብር መጠን ያስገቡ፦**", parse_mode="Markdown")
    return WITHDRAW_AMOUNT

async def withdraw_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount_text = update.message.text
    user_id = update.effective_user.id

    try:
        amount = float(amount_text)
    except ValueError:
        await update.message.reply_text("❌ **እባክዎን ትክክለኛ ቁጥር ያስገቡ!**", parse_mode="Markdown")
        return WITHDRAW_AMOUNT

    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("SELECT balance, wallet FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if row and row[0] >= amount:
        new_balance = row[0] - amount
        cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        conn.commit()
        
        # Send Notice to Admin Channel
        admin_msg = (
            f"🔔 **አዲስ የክፍያ ጥያቄ (Withdrawal Request)**\n\n"
            f"👤 **ተጠቃሚ ID፦** `{user_id}`\n"
            f"💰 **የተጠየቀው መጠን፦** `{amount}` ETB\n"
            f"💳 **የክፍያ አድራሻ (Wallet)፦** `{row[1]}`"
        )
        try:
            await context.bot.send_message(chat_id=PAYMENT_PROOF_CHANNEL, text=admin_msg, parse_mode="Markdown")
        except Exception:
            pass

        await update.message.reply_text("✅ **የክፍያ ጥያቄዎ በተሳካ ሁኔታ ተልኳል! በቅርቡ ገቢ ይደረጋል።**", reply_markup=get_main_keyboard(), parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ **በቂ ባላንስ የለዎትም!**", reply_markup=get_main_keyboard(), parse_mode="Markdown")

    conn.close()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ **ሂደቱ ተሰርዟል።**", reply_markup=get_main_keyboard(), parse_mode="Markdown")
    return ConversationHandler.END

# --- ADMIN COMMANDS ---
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("👑 **እንኳን ወደ አድሚን ፓነል በደህና መጡ!**", parse_mode="Markdown")

# --- MAIN APPLICATION BUILDER ---
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Conversation Handlers
    wallet_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(wallet_start, pattern="^btn_wallet$")],
        states={SET_WALLET_VAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, wallet_save)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    withdraw_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(withdraw_start, pattern="^btn_withdraw$")],
        states={WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_process)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Handlers Registration
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))

    app.add_handler(wallet_conv)
    app.add_handler(withdraw_conv)

    app.add_handler(CallbackQueryHandler(menu_handler, pattern="^btn_(balance|referral|stats)$"))

    app.add_error_handler(lambda u, c: logging.error(f"Update {u} caused error {c.error}"))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
