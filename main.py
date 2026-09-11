import os
import time
import json
from threading import Thread
import telebot
from telebot import types
from flask import Flask, request, redirect

# --- Configs & Settings ---
BOT_TOKEN = "8809457101:AAERPSfuFNe9lAstqaZMlNRp1vVEvnHiLC0"  # BotFather ላይ የወሰድከውን Token አስገባ
ADMIN_ID = 7435977089             # የራስህ Telegram ID
REFERRAL_BONUS = 3.00
MIN_WITHDRAW = 20.00
DB_FILE = "users_db.json"
CHANNELS_FILE = "channels_db.json"
SERVER_URL = "https://my-telegram-bot-xn5t.onrender.com"  # የ Render URL ህ

bot = telebot.TeleBot(BOT_TOKEN)

# --- 1. Database System for Channels & Users ---

def load_channels():
    if os.path.exists(CHANNELS_FILE):
        try:
            with open(CHANNELS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Channels ማነብ አልተቻለም፦ {e}")
    default_channels = ["@skmnlm", "@ffnnmmkk", "@ttrffnm", "@proof_1621", "@Marvel5423"]
    save_channels(default_channels)
    return default_channels

def save_channels(channels_list):
    try:
        with open(CHANNELS_FILE, "w") as f:
            json.dump(channels_list, f, indent=4)
    except Exception as e:
        print(f"Channels ማስቀመጥ አልተቻለም፦ {e}")

channels_db = load_channels()

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except Exception as e:
            print(f"DB ማነብ አልተቻለም፦ {e}")
            return {}
    return {}

def save_db(db):
    try:
        with open(DB_FILE, "w") as f:
            json.dump(db, f, indent=4)
    except Exception as e:
        print(f"DB ማስቀመጥ አልተቻለም፦ {e}")

users_db = load_db()

def is_ip_registered(user_ip, current_user_id):
    for uid, udata in users_db.items():
        if udata.get('ip') == user_ip and uid != current_user_id:
            return True
    return False

# --- 2. Web Server (Flask & IP Verification) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and running!"

@app.route('/verify/<int:user_id>')
def verify_ip(user_id):
        bot_info = bot.get_me()
    return redirect(f"https://t.me/{bot_info.username}")

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- 3. Force Join Logic ---

def check_status(user_id):
    for channel in channels_db:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except Exception as e:
            print(f"የቻናል ማረጋገጥ ስህተት ({channel}): {e}")
            return False
    return True

def get_not_joined_channels(user_id):
    not_joined = []
    for channel in channels_db:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                not_joined.append(channel)
        except Exception:
            not_joined.append(channel)
    return not_joined

def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("💰 አካውንቴ (Balance)")
    btn2 = types.KeyboardButton("🔗 መጋበዣ ሊንክ (Referral)")
    btn3 = types.KeyboardButton("💵 ብር ማውጫ (Withdraw)")
    markup.add(btn1, btn2)
    markup.add(btn3)
    return markup

# --- 4. Admin Commands (በቴሌግራም መቆጣጠሪያ) ---

@bot.message_handler(commands=['addchannel'])
def add_channel_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        new_ch = message.text.split()[1].strip()
        if not new_ch.startswith("@"):
            bot.reply_to(message, "⚠️ እባክህ የቻናሉን username ከ `@` ጋር ጻፍ! (ምሳሌ፦ `/addchannel @mychannel`)")
            return
        if new_ch not in channels_db:
            channels_db.append(new_ch)
            save_channels(channels_db)
            bot.reply_to(message, f"✅ ቻናል **{new_ch}** በስኬት ተጨምሯል!")
        else:
            bot.reply_to(message, f"⚠️ ቻናል **{new_ch}** አስቀድሞ አለ!")
    except IndexError:
        bot.reply_to(message, "⚠️ ምሳሌ፦ `/addchannel @mychannel`")

@bot.message_handler(commands=['delchannel'])
def del_channel_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        rem_ch = message.text.split()[1].strip()
        if rem_ch in channels_db:
            channels_db.remove(rem_ch)
            save_channels(channels_db)
            bot.reply_to(message, f"❌ ቻናል **{rem_ch}** ተሰርዟል!")
        else:
            bot.reply_to(message, f"⚠️ ቻናል **{rem_ch}** አልተገኘም!")
    except IndexError:
        bot.reply_to(message, "⚠️ ምሳሌ፦ `/delchannel @mychannel`")

@bot.message_handler(commands=['listchannels'])
def list_channels_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    if not channels_db:
        bot.reply_to(message, "እስካሁን ምንም የተመዘገበ ቻናል የለም።")
        return
    text = "📋 **የተመዘገቡ Force Join ቻናሎች፦**\n\n"
    for ch in channels_db:
        text += f"• {ch}\n"
    bot.reply_to(message, text, parse_mode="Markdown")

# --- 5. User Handlers ---

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or "ተጠቃሚ"

    if user_id not in users_db:
        users_db[user_id] = {
            'balance': 0.0,
            'referred_by': None,
            'referred_count': 0
        }
        args = message.text.split()
        if len(args) > 1:
            try:
                referrer_id = int(args[1])
                if referrer_id in users_db and referrer_id != user_id:
                    users_db[user_id]['referred_by'] = referrer_id
            except ValueError:
                pass
        save_db(users_db)

    # IP Verification
    if not users_db[user_id].get('ip'):
        verify_url = f"{SERVER_URL}/verify/{user_id}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔒 አካውንትዎን ያረጋግጡ (Verify IP)", url=verify_url))
        bot.send_message(
            user_id,
            "⚠️ <b>አካውንት ማረጋገጫ ያስፈልጋል!</b>\n\nከአንድ በላይ አካውንት መጠቀም የተከለከለ ነው። እባክዎን ከታች ያለውን ቁልፍ ተጭነው IP አድራሻዎን ያረጋግጡ።",
            reply_markup=markup,
            parse_mode="HTML"
        )
        return

    # Check Force Join
    not_joined = get_not_joined_channels(user_id)
    if not_joined:
        markup = types.InlineKeyboardMarkup()
        for idx, ch in enumerate(not_joined, 1):
            clean_username = ch.replace("@", "").strip()
            ch_url = f"https://t.me/{clean_username}"
            btn = types.InlineKeyboardButton(text=f"📢 ቻናል {idx} ተቀላቀል", url=ch_url)
            markup.add(btn)

        check_btn = types.InlineKeyboardButton(text="✅ ተቀላቅያለሁ (Check)", callback_data="check_join")
        markup.add(check_btn)

        bot.send_message(
            user_id,
            f"👋 ሰላም {username}!\n\nቦቱን ለመጠቀም መጀመሪያ ሁሉንም ቻናሎቻችንን መቀላቀል አለብዎት፦",
            reply_markup=markup
        )
        return

    bot.send_message(user_id, f"👋 እንኳን ደህና መጡ {username}!", reply_markup=main_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def check_callback(call):
    user_id = call.from_user.id
    if check_status(user_id):
        # የሪፌራል ቦነስ ለመስጠት
        ref_id = users_db[user_id].get('referred_by')
        if ref_id and ref_id in users_db and not users_db[user_id].get('bonus_given'):
            users_db[ref_id]['balance'] += REFERRAL_BONUS
            users_db[ref_id]['referred_count'] += 1
            users_db[user_id]['bonus_given'] = True
            save_db(users_db)
            try:
                bot.send_message(ref_id, f"🎉 አዲስ ሰው ጋብዘዋል! +{REFERRAL_BONUS} ብር ተጨምሮልዎታል።")
            except Exception:
                pass

        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(user_id, "✅ በስኬት ተረጋግጧል! አሁን ቦቱን መጠቀም ይችላሉ።", reply_markup=main_keyboard())
    else:
        bot.answer_callback_query(call.id, "⚠️ እባክዎን ሁሉንም ቻናሎች ይቀላቀሉ!", show_alert=True)

@bot.message_handler(func=lambda m: True)
def handle_buttons(message):
    user_id = message.from_user.id

    if not check_status(user_id):
        start(message)
        return

    if message.text == "💰 አካውንቴ (Balance)":
        bal = users_db[user_id].get('balance', 0.0)
        refs = users_db[user_id].get('referred_count', 0)
        bot.reply_to(message, f"💳 **የእርስዎ አካውንት መረጃ፦**\n\n• ቀሪ ሂሳብ፦ `{bal:.2f}` ብር\n• የጋበዟቸው ሰዎች፦ `{refs}`", parse_mode="Markdown")

    elif message.text == "🔗 መጋበዣ ሊንክ (Referral)":
        bot_info = bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        bot.reply_to(message, f"🔗 **የእርስዎ መጋበዣ ሊንክ፦**\n\n`{ref_link}`\n\nለእያንዳንዱ ሰው ሰውን ሲጋብዙ **{REFERRAL_BONUS:.2f}** ብር ያገኛሉ!", parse_mode="Markdown")

    elif message.text == "💵 ብር ማውጫ (Withdraw)":
        bal = users_db[user_id].get('balance', 0.0)
        if bal < MIN_WITHDRAW:
            bot.reply_to(message, f"⚠️ ማውጣት የሚችሉት አነስተኛው የብር መጠን **{MIN_WITHDRAW:.2f}** ብር ነው! የእርስዎ ሂሳብ `{bal:.2f}` ብር ነው።")
        else:
            bot.reply_to(message, "✅ የብር ማውጫ ጥያቄዎን ለማስተናገድ እባክዎ የአድሚን አካውንቱን ያነጋግሩ።")

def run_bot():
    bot.infinity_polling()

if __name__ == "__main__":
    Thread(target=run_flask).start()
    run_bot()
