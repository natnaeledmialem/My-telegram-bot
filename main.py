import logging
import sqlite3
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# --- CONFIGURATION ---
BOT_TOKEN = "8985332397:AAGVO0bxDG0ccnr5AGNMyUwNdBNrDh97ayE"  # የቦትህን Token እዚህ አስገባ
ADMIN_ID = 8825122216  # የራስህን Telegram User ID እዚህ አስገባ
PAYMENT_PROOF_CHANNEL = "@Paymentprooff2"  # የ Payment Proof Channel

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
    
    # Users
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance REAL DEFAULT 0.0,
        task_earnings REAL DEFAULT 0.0,
        referral_earnings REAL DEFAULT 0.0,
        bonus_earnings REAL DEFAULT 0.0,
        referred_by INTEGER,
        is_verified INTEGER DEFAULT 0,
        telebirr TEXT,
        cbe TEXT,
        last_bonus TEXT
    )''')
    
    # Referrals
    cursor.execute('''CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        referred_id INTEGER,
        UNIQUE(referrer_id, referred_id)
    )''')
    
    # Mandatory Channels Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE
    )''')

    # Dynamic Tasks Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        link TEXT,
        reward REAL
    )''')

    # Completed Tasks
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_tasks (
        user_id INTEGER,
        task_id INTEGER,
        PRIMARY KEY (user_id, task_id)
    )''')

    # Withdrawals
    cursor.execute('''CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        method TEXT,
        account TEXT,
        status TEXT DEFAULT 'PENDING'
    )''')
    
    # Default Channels (ለመጀመሪያ ጊዜ ዳታቤዝ ባዶ ከሆነ)
    cursor.execute("SELECT COUNT(*) FROM channels")
    if cursor.fetchone()[0] == 0:
        default_channels = [
            "@ethiocashflow", "@Sheger_tech1", "@EthioVortex1",
            "@AmanIncomeLab", "@OnlineIncomeHub07", "@Paymentprooff2"
        ]
        for ch in default_channels:
            cursor.execute("INSERT OR IGNORE INTO channels (username) VALUES (?)", (ch,))

    conn.commit()
    conn.close()

init_db()

# --- HELPER FUNCTIONS ---
def get_mandatory_channels():
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM channels")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

async def check_channel_membership(bot, user_id):
    channels = get_mandatory_channels()
    unjoined = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status in ['left', 'kicked']:
                unjoined.append(ch)
        except Exception:
            unjoined.append(ch)
    return unjoined

def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("💰 Balance", callback_data="btn_balance"), InlineKeyboardButton("👥 Referral", callback_data="btn_referral")],
        [InlineKeyboardButton("🎯 Tasks", callback_data="btn_tasks"), InlineKeyboardButton("🎁 Bonus", callback_data="btn_bonus")],
        [InlineKeyboardButton("💳 Wallet", callback_data="btn_wallet"), InlineKeyboardButton("💸 Withdraw", callback_data="btn_withdraw")],
        [InlineKeyboardButton("📞 Support", callback_data="btn_support")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- START & VERIFICATION ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = user.id
    args = context.args

    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("SELECT is_verified FROM users WHERE user_id = ?", (chat_id,))
    row = cursor.fetchone()

    if not row:
        referrer_id = None
        if args and args[0].isdigit():
            ref = int(args[0])
            if ref != chat_id:
                referrer_id = ref
        
        cursor.execute("INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)",
                       (chat_id, user.username, referrer_id))
        conn.commit()
        is_verified = 0
    else:
        is_verified = row[0]

    conn.close()

    if is_verified:
        await update.message.reply_text(f"👋 እንኳን ደህና መጡ {user.first_name}!\n\nMain Menu:", reply_markup=get_main_keyboard())
    else:
        await send_verification_msg(update, context)

async def send_verification_msg(update: Update, context: ContextTypes.DEFAULT_TYPE, unjoined_override=None):
    user_id = update.effective_user.id
    bot = context.bot

    unjoined = unjoined_override if unjoined_override else await check_channel_membership(bot, user_id)

    if not unjoined:
        conn = db_connect()
        cursor = conn.cursor()
        cursor.execute("SELECT is_verified, referred_by FROM users WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        
        if res and res[0] == 0:
            cursor.execute("UPDATE users SET is_verified = 1 WHERE user_id = ?", (user_id,))
            referrer = res[1]
            
            if referrer:
                try:
                    cursor.execute("INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)", (referrer, user_id))
                    cursor.execute("UPDATE users SET balance = balance + ?, referral_earnings = referral_earnings + ? WHERE user_id = ?",
                                   (REFERRAL_REWARD, REFERRAL_REWARD, referrer))
                    await bot.send_message(chat_id=referrer, text=f"🎉 አዲስ Referral! +{REFERRAL_REWARD} ETB አግኝተዋል።")
                except sqlite3.IntegrityError:
                    pass

            conn.commit()
        conn.close()

        msg = "✅ Verification Successful! እንኳን ወደ Ethio Smart Bot በደህና መጡ።"
        if update.callback_query:
            await update.callback_query.message.edit_text(msg, reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text(msg, reply_markup=get_main_keyboard())
    else:
        keyboard = []
        for ch in unjoined:
            keyboard.append([InlineKeyboardButton(f"🔗 Join {ch}", url=f"https://t.me/{ch.replace('@', '')}")])
        keyboard.append([InlineKeyboardButton("✅ Verify Membership", callback_data="verify_channels")])
        
        text = "👋 እንኳን ደህና መጡ!\n\nቦቱን ለመጠቀም እባክዎን የሚከተሉትን Channels ይቀላቀሉ:"
        
        if update.callback_query:
            await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    unjoined = await check_channel_membership(context.bot, query.from_user.id)
    if unjoined:
        await query.answer("❌ እስካሁን ሁሉንም Channels አልተቀላቀሉም!", show_alert=True)
        await send_verification_msg(update, context, unjoined_override=unjoined)
    else:
        await send_verification_msg(update, context)

# --- MAIN MENU CALLBACKS ---
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    await query.answer()

    conn = db_connect()
    cursor = conn.cursor()

    if data == "btn_balance":
        cursor.execute("SELECT balance, task_earnings, referral_earnings, bonus_earnings FROM users WHERE user_id = ?", (user_id,))
        bal, task, ref, bonus = cursor.fetchone()
        text = (f"💰 **የእርስዎ Balance መረጃ**\n\n"
                f"💵 Total Balance: {bal:.2f} ETB\n"
                f"🎯 Task Earnings: {task:.2f} ETB\n"
                f"👥 Referral Earnings: {ref:.2f} ETB\n"
                f"🎁 Bonus Earnings: {bonus:.2f} ETB")
        kb = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "btn_referral":
        cursor.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
        count = cursor.fetchone()[0]
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        
        text = (f"👥 **Referral Program**\n\n"
                f"ጓደኞችዎን ይጋብዙ እና ለእያንዳንዱ verified ተጋባዥ **{REFERRAL_REWARD} ETB** ያግኙ!\n\n"
                f"🔗 Your Link:\n`{ref_link}`\n\n"
                f"📊 Total Referrals: {count}")
        kb = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "btn_tasks":
        cursor.execute("SELECT id, title, link, reward FROM tasks")
        all_tasks = cursor.fetchall()
        
        if not all_tasks:
            text = "🎯 **Daily Tasks**\n\n📌 አሁን ላይ ምንም አይነት ክፍት Task የለም!\n\nአዳዲስ Taskዎች ሲጨመሩ ወዲያውኑ በቦቱ እናስታውቃችኋለን።"
            kb = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        else:
            text = "🎯 **Daily Tasks**\n\nየሚከተሉትን Taskዎች በመስራት ተጨማሪ ገንዘብ ያግኙ፦\n"
            kb = []
            for tid, title, link, reward in all_tasks:
                cursor.execute("SELECT * FROM user_tasks WHERE user_id = ? AND task_id = ?", (user_id, tid))
                status = "✅ Done" if cursor.fetchone() else f"💰 +{reward} ETB"
                kb.append([InlineKeyboardButton(f"{title} ({status})", callback_data=f"do_task_{tid}")])
            kb.append([InlineKeyboardButton("🔙 Back", callback_data="back_main")])
            
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("do_task_"):
        tid = int(data.replace("do_task_", ""))
        cursor.execute("SELECT * FROM user_tasks WHERE user_id = ? AND task_id = ?", (user_id, tid))
        if cursor.fetchone():
            await query.answer("❌ ይህን Task ቀደም ብለው ሠርተዋል!", show_alert=True)
        else:
            cursor.execute("SELECT reward, link FROM tasks WHERE id = ?", (tid,))
            trow = cursor.fetchone()
            if trow:
                rew, link = trow
                cursor.execute("INSERT INTO user_tasks (user_id, task_id) VALUES (?, ?)", (user_id, tid))
                cursor.execute("UPDATE users SET balance = balance + ?, task_earnings = task_earnings + ? WHERE user_id = ?", (rew, rew, user_id))
                conn.commit()
                await query.answer(f"✅ Task Completed! +{rew} ETB ተጨምሯል።", show_alert=True)

    elif data == "btn_bonus":
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("SELECT last_bonus FROM users WHERE user_id = ?", (user_id,))
        last = cursor.fetchone()[0]

        if last == today:
            await query.answer("❌ የዛሬውን Daily Bonus ቀደም ብለው ወስደዋል! ነገ ተመልሰው ይሞክሩ።", show_alert=True)
        else:
            bonus_amt = 1.0
            cursor.execute("UPDATE users SET balance = balance + ?, bonus_earnings = bonus_earnings + ?, last_bonus = ? WHERE user_id = ?",
                           (bonus_amt, bonus_amt, today, user_id))
            conn.commit()
            await query.answer(f"🎉 የዛሬው Bonus +{bonus_amt} ETB ደርሶዎታል!", show_alert=True)

    elif data == "btn_support":
        text = "📞 **Support & Help**\n\nለማንኛውም ጥያቄ ወይም እርዳታ በደስታ እናስተናግዳለን፦\n👤 Support Admin: @AmanM_12"
        kb = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "back_main":
        await query.message.edit_text("Main Menu:", reply_markup=get_main_keyboard())

    conn.close()

# --- WALLET MANAGEMENT ---
async def wallet_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("SELECT telebirr, cbe FROM users WHERE user_id = ?", (query.from_user.id,))
    tb, cbe = cursor.fetchone()
    conn.close()

    text = (f"💳 **Your Saved Wallets**\n\n"
            f"📱 Telebirr: `{tb if tb else 'Not Set'}`\n"
            f"🏦 CBE: `{cbe if cbe else 'Not Set'}`\n\n"
            f"ለመለወጥ ወይም አዲስ ለመመዝገብ ከታች ይምረጡ:")
    kb = [
        [InlineKeyboardButton("📱 Edit Telebirr", callback_data="set_tb"), InlineKeyboardButton("🏦 Edit CBE", callback_data="set_cbe")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
    ]
    await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def wallet_set_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    w_type = "Telebirr" if query.data == "set_tb" else "CBE"
    context.user_data['w_type'] = w_type

    msg = "📱 እባክዎን የ Telebirr ቁጥርዎን ያስገቡ (10 digits, 09 ወይም 07 የሚጀምር)፦" if w_type == "Telebirr" else "🏦 እባክዎን የ CBE አካውንት ቁጥርዎን ያስገቡ (13 digits, 1000 የሚጀምር)፦"
    await query.message.edit_text(msg)
    return SET_WALLET_VAL

async def wallet_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    w_type = context.user_data.get('w_type')
    user_id = update.effective_user.id

    valid = False
    if w_type == "Telebirr" and re.match(r"^(09|07)\d{8}$", text):
        valid = True
    elif w_type == "CBE" and re.match(r"^1000\d{9}$", text):
        valid = True

    if not valid:
        await update.message.reply_text("❌ የተሳሳተ ቁጥር! እባክዎን ደግመው ትክክለኛውን ያስገቡ (ወይም /cancel ይበሉ)።")
        return SET_WALLET_VAL

    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE users SET {'telebirr' if w_type == 'Telebirr' else 'cbe'} = ? WHERE user_id = ?", (text, user_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ {w_type} Wallet በተሳካ ሁኔታ ተመዝግቧል!", reply_markup=get_main_keyboard())
    return ConversationHandler.END

# --- WITHDRAWAL SYSTEM ---
async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    kb = [
        [InlineKeyboardButton("📱 Telebirr", callback_data="w_Telebirr"), InlineKeyboardButton("🏦 CBE", callback_data="w_CBE")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
    ]
    await query.message.edit_text("💸 የወጪ ማድረጊያ ዘዴ (Withdrawal Method) ይምረጡ፦", reply_markup=InlineKeyboardMarkup(kb))
    return WITHDRAW_TYPE

async def withdraw_type_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.replace("w_", "")
    user_id = query.from_user.id

    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("SELECT telebirr, cbe, balance FROM users WHERE user_id = ?", (user_id,))
    tb, cbe, bal = cursor.fetchone()
    conn.close()

    acc = tb if method == "Telebirr" else cbe
    if not acc:
        await query.message.edit_text(f"❌ የ {method} Wallet አልመዘገቡም! አስቀድመው Wallet Menu ውስጥ ያዘጋጁ።", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]))
        return ConversationHandler.END

    context.user_data['w_method'] = method
    context.user_data['w_acc'] = acc
    context.user_data['user_bal'] = bal

    await query.message.edit_text(f"💵 የሎት Balance: {bal:.2f} ETB\n\nማውጣት የሚፈልጉትን የገንዘብ መጠን ያስገቡ፦")
    return WITHDRAW_AMOUNT

async def withdraw_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user
    user_id = user.id

    try:
        amount = float(text)
    except ValueError:
        await update.message.reply_text("❌ እባክዎን ትክክለኛ ቁጥር ያስገቡ፦")
        return WITHDRAW_AMOUNT

    bal = context.user_data['user_bal']
    if amount <= 0 or amount > bal:
        await update.message.reply_text("❌ በቂ ያልሆነ Balance ወይም የተሳሳተ መጠን! ደግመው ያስገቡ፦")
        return WITHDRAW_AMOUNT

    method = context.user_data['w_method']
    acc = context.user_data['w_acc']

    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
    cursor.execute("INSERT INTO withdrawals (user_id, amount, method, account) VALUES (?, ?, ?, ?)", (user_id, amount, method, acc))
    wid = cursor.lastrowid
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ የ Withdrawal ጥያቄዎ በቀጥታ ለ Admin ተልኳል። በጥቂት ደቂቃዎች ውስጥ ይስተናገዳል!", reply_markup=get_main_keyboard())

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    proof_msg = (
        f"🆕 **New Withdrawal Request!**\n\n"
        f"🆔 **Request ID:** #{wid}\n"
        f"👤 **User:** {user.mention_markdown_v2()} (`{user_id}`)\n"
        f"💰 **Amount:** {amount:.2f} ETB\n"
        f"💳 **Method:** {method}\n"
        f"📱 **Account Number:** `{acc}`\n"
        f"⏰ **Time:** {now_str}\n"
        f"📌 **Status:** ⏳ Pending Approval"
    )
    
    try:
        await context.bot.send_message(chat_id=PAYMENT_PROOF_CHANNEL, text=proof_msg, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Failed to post on Payment Proof Channel: {e}")

    admin_kb = [
        [InlineKeyboardButton("✅ Approve", callback_data=f"adm_app_{wid}"), InlineKeyboardButton("❌ Reject", callback_data=f"adm_rej_{wid}")]
    ]
    admin_msg = f"🔔 **አዲስ Withdrawal Request!**\n\nID: `{wid}`\nUser: {user.full_name} (`{user_id}`)\nAmount: {amount} ETB\nMethod: {method}\nAccount: `{acc}`"
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(admin_kb))

    return ConversationHandler.END

# --- ADMIN PANEL & CHANNEL/TASK MANAGEMENT ---
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    text = "🛠 **Admin Panel**\n\nከታች አንዱን መምረጥ ይችላሉ፦"
    kb = [
        [InlineKeyboardButton("👤 Total Users", callback_data="adm_users")],
        [InlineKeyboardButton("📢 Manage Channels", callback_data="adm_ch_menu")],
        [InlineKeyboardButton("🎯 Add New Task", callback_data="adm_add_task")]
    ]
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    conn = db_connect()
    cursor = conn.cursor()

    if data == "adm_users":
        cursor.execute("SELECT COUNT(*) FROM users")
        cnt = cursor.fetchone()[0]
        await query.message.edit_text(f"📊 Total Registered Users: {cnt}")

    elif data == "adm_ch_menu":
        channels = get_mandatory_channels()
        ch_text = "\n".join([f"• {c}" for c in channels]) if channels else "ምንም ቻናል የለም"
        text = f"📢 **Mandatory Channels Management**\n\n**ያሉት ቻናሎች፦**\n{ch_text}"
        kb = [
            [InlineKeyboardButton("➕ Add Channel", callback_data="adm_add_ch_start")],
            [InlineKeyboardButton("➖ Remove Channel", callback_data="adm_rem_ch_menu")],
            [InlineKeyboardButton("🔙 Back Admin", callback_data="adm_back")]
        ]
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "adm_rem_ch_menu":
        channels = get_mandatory_channels()
        if not channels:
            await query.answer("ምንም የሚወገድ ቻናል የለም!", show_alert=True)
            return
        kb = []
        for ch in channels:
            kb.append([InlineKeyboardButton(f"❌ Remove {ch}", callback_data=f"del_ch_{ch}")])
        kb.append([InlineKeyboardButton("🔙 Back", callback_data="adm_ch_menu")])
        await query.message.edit_text("የሚወገደውን ቻናል ይምረጡ፦", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("del_ch_"):
        ch_to_del = data.replace("del_ch_", "")
        cursor.execute("DELETE FROM channels WHERE username = ?", (ch_to_del,))
        conn.commit()
        await query.answer(f"✅ {ch_to_del} ተወግዷል!", show_alert=True)
        conn.close()
        return await admin_actions(update, context) # Refresh menu

    elif data.startswith("adm_app_"):
        wid = int(data.replace("adm_app_", ""))
        cursor.execute("SELECT user_id, amount FROM withdrawals WHERE id = ?", (wid,))
        row = cursor.fetchone()
        if row:
            uid, amt = row
            cursor.execute("UPDATE withdrawals SET status = 'PAID' WHERE id = ?", (wid,))
            conn.commit()
            await query.message.edit_text(f"✅ Withdrawal #{wid} Approved.")
            await context.bot.send_message(chat_id=uid, text=f"🎉 የ {amt} ETB Withdrawal ጥያቄዎ ጸድቆ ተከፍሏል!")

    elif data.startswith("adm_rej_"):
        wid = int(data.replace("adm_rej_", ""))
        cursor.execute("SELECT user_id, amount FROM withdrawals WHERE id = ?", (wid,))
        row = cursor.fetchone()
        if row:
            uid, amt = row
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amt, uid))
            cursor.execute("UPDATE withdrawals SET status = 'REJECTED' WHERE id = ?", (wid,))
            conn.commit()
            await query.message.edit_text(f"❌ Withdrawal #{wid} Rejected & Refunded.")
            await context.bot.send_message(chat_id=uid, text=f"❌ የ {amt} ETB Withdrawal ጥያቄዎ ውድቅ ተደርጓል! ገንዘቡ ወደ Balance ዎ ተመልሷል።")

    elif data == "adm_back":
        text = "🛠 **Admin Panel**"
        kb = [
            [InlineKeyboardButton("👤 Total Users", callback_data="adm_users")],
            [InlineKeyboardButton("📢 Manage Channels", callback_data="adm_ch_menu")],
            [InlineKeyboardButton("🎯 Add New Task", callback_data="adm_add_task")]
        ]
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

    conn.close()

# --- ADD CHANNEL CONVERSATION ---
async def add_ch_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text("➕ እባክዎን የቻናሉን Username ያስገቡ (ለምሳሌ፦ `@mychannel`)፦")
    return ADD_CHANNEL_STATE

async def add_ch_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ch_name = update.message.text.strip()
    if not ch_name.startswith("@"):
        ch_name = "@" + ch_name

    conn = db_connect()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO channels (username) VALUES (?)", (ch_name,))
        conn.commit()
        await update.message.reply_text(f"✅ ቻናል {ch_name} በተሳካ ሁኔታ ተጨምሯል!")
    except sqlite3.IntegrityError:
        await update.message.reply_text("❌ ይህ ቻናል አስቀድሞ ተጨምሯል!")
    conn.close()
    return ConversationHandler.END

# --- ADD TASK CONVERSATION ---
async def add_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text("🎯 **Task Title** ያስገቡ (ለምሳሌ፦ `Join Ethio Channel`)፦")
    return ADD_TASK_TITLE

async def add_task_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['t_title'] = update.message.text.strip()
    await update.message.reply_text("🔗 የ Task ቻናል/ግሩፕ **Link** ያስገቡ (ለምሳሌ፦ `https://t.me/...`)፦")
    return ADD_TASK_LINK

async def add_task_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['t_link'] = update.message.text.strip()
    await update.message.reply_text("💰 ለዚህ Task የሚሰጠውን **Reward መጠን (በ ETB)** ያስገቡ (ለምሳሌ፦ `1.5`)፦")
    return ADD_TASK_REWARD

async def add_task_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        reward = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ እባክዎን ትክክለኛ ቁጥር ያስገቡ፦")
        return ADD_TASK_REWARD

    title = context.user_data['t_title']
    link = context.user_data['t_link']

    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tasks (title, link, reward) VALUES (?, ?, ?)", (title, link, reward))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ አዲስ Task በተሳካ ሁኔታ ተመዝግቧል!\n\n📌 **Title:** {title}\n💰 **Reward:** {reward} ETB")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ተሰርዟል!", reply_markup=get_main_keyboard())
    return ConversationHandler.END

# --- MAIN APP SETUP ---
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    wallet_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(wallet_set_start, pattern="^(set_tb|set_cbe)$")],
        states={SET_WALLET_VAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, wallet_save)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    withdraw_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(withdraw_start, pattern="^btn_withdraw$")],
        states={
            WITHDRAW_TYPE: [CallbackQueryHandler(withdraw_type_select, pattern="^w_")],
            WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_confirm)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    add_ch_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_ch_start, pattern="^adm_add_ch_start$")],
        states={ADD_CHANNEL_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_ch_save)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    add_task_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_task_start, pattern="^adm_add_task$")],
        states={
            ADD_TASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_task_title)],
            ADD_TASK_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_task_link)],
            ADD_TASK_REWARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_task_save)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))

    app.add_handler(wallet_conv)
    app.add_handler(withdraw_conv)
    app.add_handler(add_ch_conv)
    app.add_handler(add_task_conv)

    app.add_handler(CallbackQueryHandler(verify_callback, pattern="^verify_channels$"))
    app.add_handler(CallbackQueryHandler(wallet_menu, pattern="^btn_wallet$"))
    app.add_handler(CallbackQueryHandler(admin_actions, pattern="^adm_"))
    app.add_handler(CallbackQueryHandler(menu_handler))

    app.add_error_handler(lambda u, c: logging.error(f"Update {u} caused error {c.error}"))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
