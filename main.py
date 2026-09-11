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
REFERRAL_BONUS = 3.40
MIN_WITHDRAW = 20.00
DB_FILE = "users_db.json"
CHANNELS_FILE = "channels_db.json"

bot = telebot.TeleBot(BOT_TOKEN)

# --- 1. Database System for Channels & Users ---

def load_channels():
    if os.path.exists(CHANNELS_FILE):
        try:
            with open(CHANNELS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Channels ማነብ አልተቻለም፦ {e}")
    default_channels = ["@skmnlm", "@ffnnmmkk", "@ttrffnm", "@proof_1621", "@Marvel5"]
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

# --- 2. Web Server (Flask Keep-Alive) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and running!"

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

# --- 4. Admin Commands ---

@bot.message_handler(commands=['addchannel'])
def add_channel_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        new_ch = message.text.split()[1].strip()
        if not new_ch.startswith("@"):
            bot.reply_to(message, "⚠️ <b>እባክህ የቻናሉን username ከ @ ጋር ጻፍ! (ምሳሌ፦ /addchannel @mychannel)</b>", parse_mode="HTML")
            return
        if new_ch not in channels_db:
            channels_db.append(new_ch)
            save_channels(channels_db)
            bot.reply_to(message, f"✅ <b>ቻናል {new_ch} በስኬት ተጨምሯል!</b>", parse_mode="HTML")
        else:
            bot.reply_to(message, f"⚠️ <b>ቻናል {new_ch} አስቀድሞ አለ!</b>", parse_mode="HTML")
    except IndexError:
        bot.reply_to(message, "⚠️ <b>ምሳሌ፦ /addchannel @mychannel</b>", parse_mode="HTML")

@bot.message_handler(commands=['delchannel'])
def del_channel_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        rem_ch = message.text.split()[1].strip()
        if rem_ch in channels_db:
            channels_db.remove(rem_ch)
            save_channels(channels_db)
            bot.reply_to(message, f"❌ <b>ቻናል {rem_ch} ተሰርዟል!</b>", parse_mode="HTML")
        else:
            bot.reply_to(message, f"⚠️ <b>ቻናል {rem_ch} አልተገኘም!</b>", parse_mode="HTML")
    except IndexError:
        bot.reply_to(message, "⚠️ <b>ምሳሌ፦ /delchannel @mychannel</b>", parse_mode="HTML")

@bot.message_handler(commands=['listchannels'])
def list_channels_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    if not channels_db:
        bot.reply_to(message, "<b>እስካሁን ምንም የተመዘገበ ቻናል የለም።</b>", parse_mode="HTML")
        return
    text = "📋 <b>የተመዘገቡ Force Join ቻናሎች፦</b>\n\n"
    for ch in channels_db:
        text += f"• <b>{ch}</b>\n"
    bot.reply_to(message, text, parse_mode="HTML")

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
            f"👋 <b>ሰላም {username}!</b>\n\n<b>ቦቱን ለመጠቀም መጀመሪያ ሁሉንም ቻናሎቻችንን መቀላቀል አለብዎት፦</b>",
            reply_markup=markup,
            parse_mode="HTML"
        )
        return

    bot.send_message(user_id, f"👋 <b>እንኳን ደህና መጡ {username}!</b>", reply_markup=main_keyboard(), parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def check_callback(call):
    user_id = call.from_user.id
    if check_status(user_id):
        ref_id = users_db[user_id].get('referred_by')
        if ref_id and ref_id in users_db and not users_db[user_id].get('bonus_given'):
            users_db[ref_id]['balance'] += REFERRAL_BONUS
            users_db[ref_id]['referred_count'] += 1
            users_db[user_id]['bonus_given'] = True
            save_db(users_db)
            try:
                bot.send_message(ref_id, f"🎉 <b>አዲስ ሰው ጋብዘዋል! +{REFERRAL_BONUS} ብር ተጨምሮልዎታል።</b>", parse_mode="HTML")
            except Exception:
                pass

        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(user_id, "✅ <b>በስኬት ተረጋግጧል! አሁን ቦቱን መጠቀም ይችላሉ።</b>", reply_markup=main_keyboard(), parse_mode="HTML")
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
        bot.reply_to(message, f"💳 <b>የእርስዎ አካውንት መረጃ፦</b>\n\n• ቀሪ ሂሳብ፦ <b>{bal:.2f} ብር</b>\n• የጋበዟቸው ሰዎች፦ <b>{refs}</b>", parse_mode="HTML")

    elif message.text == "🔗 መጋበዣ ሊንክ (Referral)":
        bot_info = bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        bot.reply_to(message, f"🔗 <b>የእርስዎ መጋበዣ ሊንክ፦</b>\n\n<code>{ref_link}</code>\n\n<b>ለእያንዳንዱ ሰው ሰውን ሲጋብዙ {REFERRAL_BONUS:.2f} ብር ያገኛሉ!</b>", parse_mode="HTML")

    elif message.text == "💵 ብር ማውጫ (Withdraw)":
        bal = users_db[user_id].get('balance', 0.0)
        if bal < MIN_WITHDRAW:
            bot.reply_to(message, f"⚠️ <b>ማውጣት የሚችሉት አነስተኛው የብር መጠን {MIN_WITHDRAW:.2f} ብር ነው! የእርስዎ ሂሳብ {bal:.2f} ብር ነው።</b>", parse_mode="HTML")
        else:
            bot.reply_to(message, "✅ <b>የብር ማውጫ ጥያቄዎን ለማስተናገድ እባክዎ የአድሚን አካውንቱን ያነጋግሩ።</b>", parse_mode="HTML")

def run_bot():
    bot.infinity_polling()

if __name__ == "__main__":
    Thread(target=run_flask).start()
    run_bot()
