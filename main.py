import os
import time
import json
from threading import Thread
import telebot
from telebot import types
from flask import Flask, request, redirect

# --- ማስተካከያ ቦታዎች ---
BOT_TOKEN = "8891177020:AAHemQBAUImmB_WYce_uAyDtSAKy5DYYVy0"  # የቦትህ ቶክን

CHANNELS = ["@skmnlm", "@ffnnmmkk", "@ttrffnm", "@proof_1621", "@tech_zone_ya"]
PAYOUT_CHANNEL = "@proof_1621"

ADMIN_ID = 8465808385           
REFERRAL_BONUS = 1.00 
MIN_WITHDRAW = 10.00  
DB_FILE = "users_db.json"

# በ Render ላይ የሚሰጠውን Domain አድራሻ እዚህ ጋር ያስገቡ (ለምሳሌ፦ https://my-bot.onrender.com)
SERVER_URL = "https://my-telegram-bot-xn5t.onrender.com
# ---------------------

bot = telebot.TeleBot(BOT_TOKEN)

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except Exception as e:
            print(f"DB ማንበብ አልተቻለም፦ {e}")
            return {}
    return {}

def save_db(db):
    try:
        with open(DB_FILE, "w") as f:
            json.dump(db, f, indent=4)
    except Exception as e:
        print(f"DB ማስቀመጥ አልተቻለም፦ {e}")

users_db = load_db()

# IP Address በመመዝገብ Multi-Account መከላከል
def is_ip_registered(user_ip, current_user_id):
    for uid, udata in users_db.items():
        if udata.get('ip') == user_ip and uid != current_user_id:
            return True
    return False

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and running!"

# IP Address መያዣ መስመር (Endpoint)
@app.route('/verify/<int:user_id>')
def verify_ip(user_id):
    # Cloudflare/Render IP ለማግኘት
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if user_ip and ',' in user_ip:
        user_ip = user_ip.split(',')[0].strip()

    if user_id in users_db:
        # IP አድራሻው ቀደም ሲል ሌላ ሰው ተጠቅሞበት እንደሆነ ማረጋገጥ
        if is_ip_registered(user_ip, user_id):
            return "<h3>❌ ይቅርታ! በዚህ ስልክ/ኢንተርኔት (IP Address) ሌላ አካውንት ተከፍቷል። በስልክዎ ከአንድ በላይ አካውንት መጠቀም አይችሉም!</h3>", 403
        
        users_db[user_id]['ip'] = user_ip
        save_db(users_db)
        
        # የቦቱን ውይይት ለመክፈት አቅጣጫ ማስቀየር
        bot_info = bot.get_me()
        return redirect(f"https://t.me/{bot_info.username}")
    
    return "ተጠቃሚው አልተገኘም!", 404

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def check_status(user_id):
    for channel in CHANNELS:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except Exception as e:
            print(f"ቻናል ማረጋገጥ አልተቻለም ({channel}): {e}")
            return False
    return True

def get_not_joined_channels(user_id):
    not_joined = []
    for channel in CHANNELS:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
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

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or "ተጠቃሚ"
    
    # አዲስ ተጠቃሚ ሲሆን ፕሮፋይል መክፈት
    if user_id not in users_db:
        users_db[user_id] = {'balance': 0.0, 'referred_by': None, 'referred_count': 0, 'ip': None}
        args = message.text.split()
        if len(args) > 1:
            try:
                referrer_id = int(args[1])
                if referrer_id in users_db and referrer_id != user_id:
                    users_db[user_id]['referred_by'] = referrer_id
            except ValueError:
                pass
        save_db(users_db)

    # ተጠቃሚው IP Verification ካላደረገ አረጋግጥ የሚል ሊንክ መስጠት
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

    not_joined = get_not_joined_channels(user_id)
    
    if not_joined:
        markup = types.InlineKeyboardMarkup(row_width=1)
        for i, ch in enumerate(not_joined, 1):
            url_link = f"https://t.me/{ch.replace('@', '')}"
            markup.add(types.InlineKeyboardButton(f"📢 ቻናል {i}ን ተቀላቀል", url=url_link))
        
        markup.add(types.InlineKeyboardButton("✅ ተቀላቅያለሁ (Check)", callback_data="check_join"))
        
        bot.send_message(
            user_id, 
            f"👋 <b>ሰላም {username}!</b>\n\nቦቱን ለመጠቀም መጀመሪያ ሁሉንም ቻናሎቻችንን መቀላቀል አለብዎት።👇", 
            reply_markup=markup,
            parse_mode="HTML"
        )
        return

    # የሪፈራል ቦነስ መስጠት
    ref_id = users_db[user_id]['referred_by']
    if ref_id and users_db[user_id]['referred_count'] == 0:
        if ref_id in users_db:
            users_db[ref_id]['balance'] += REFERRAL_BONUS
            users_db[ref_id]['referred_count'] += 1
            users_db[user_id]['referred_count'] = -1 
            save_db(users_db)
            try:
                bot.send_message(ref_id, f"🎉 <b>አዲስ ሰው ጋብዘዋል!</b>\n<b>+{REFERRAL_BONUS} ብር</b> ወደ አካውንትዎ ተጨምሯል።", parse_mode="HTML")
            except Exception:
                pass

    bot.send_message(
        user_id, 
        "✨ <b>እንኳን በደህና መጡ!</b>\n\nከታች ያሉትን ቁልፎች በመጠቀም ሰዎችን ይጋብዙ እና ያትርፉ።", 
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )

@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def check_callback(call):
    user_id = call.from_user.id
    
    if check_status(user_id):
        bot.answer_callback_query(call.id, "✅ በደንብ ተቀላቅለዋል!", show_alert=False)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        start(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ አሁንም ሁሉንም ቻናሎች አልተቀላቀሉም!", show_alert=True)

@bot.message_handler(func=lambda message: True)
def handle_buttons(message):
    user_id = message.from_user.id
    
    if user_id not in users_db:
        bot.send_message(user_id, "<b>እባክዎ መጀመሪያ /start ይበሉ</b>", parse_mode="HTML")
        return

    if not users_db[user_id].get('ip'):
        start(message)
        return

    if not check_status(user_id):
        start(message)
        return

    if message.text == "💰 አካውንቴ (Balance)":
        bal = users_db[user_id]['balance']
        count = max(0, users_db[user_id]['referred_count'])
        text = f"💳 <b>የአካውንትዎ መረጃ</b>\n\n💵 <b>ጠቅላላ ቀሪ ሂሳብ፦</b> <b>{bal:.2f} ብር</b>\n👥 <b>የጋበዟቸው ሰዎች ቁጥር፦</b> <b>{count} ሰው</b>"
        bot.send_message(user_id, text, parse_mode="HTML")

    elif message.text == "🔗 መጋበዣ ሊንክ (Referral)":
        try:
            bot_info = bot.get_me()
            ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
            text = f"👥 <b>ሰዎችን ይጋብዙ!</b>\n\nየእርስዎ መጋበዣ ሊንክ ይህ ነው👇\n<code>{ref_link}</code>\n\n🎁 አንድ ሰው በሊንክዎ ሲገባ <b>{REFERRAL_BONUS} ብር</b> ያገኛሉ።"
            bot.send_message(user_id, text, parse_mode="HTML")
        except Exception:
            bot.send_message(user_id, "⚠️ <b>ችግር አጋጥሟል፣ እባክዎ ትንሽ ቆይተው ድጋሚ ይሞክሩ።</b>", parse_mode="HTML")

    elif message.text == "💵 ብር ማውጫ (Withdraw)":
        bal = users_db[user_id]['balance']
        if bal < MIN_WITHDRAW:
            bot.send_message(user_id, f"❌ <b>ይቅርታ፣ ብር ለማውጣት ቢያንስ {MIN_WITHDRAW} ብር ሊኖርዎት ይገባል።</b>\n\n💵 <b>የእርስዎ ሂሳብ፦</b> <b>{bal:.2f} ብrm</b>", parse_mode="HTML")
        else:
            msg = bot.send_message(user_id, "🔄 <b>እባክዎ ብሩ የሚገባበትን ስም እና ስልክ ቁጥር (ወይም የባንክ አካውንት) ይጻፉልን፦</b>", parse_mode="HTML")
            bot.register_next_step_handler(msg, process_withdraw)

def process_withdraw(message):
    user_id = message.from_user.id
    details = message.text
    bal = users_db[user_id]['balance']
    username = message.from_user.username or "የሌለው"

    users_db[user_id]['balance'] = 0.0
    save_db(users_db)

    admin_msg = (f"🚨 <b>አዲስ የማውጫ ጥያቄ ደርሷል!</b>\n\n"
                 f"👤 <b>ተጠቃሚ ID፦</b> <code>{user_id}</code>\n"
                 f"🏷 <b>ዩዘርኔም፦</b> @{username}\n"
                 f"💰 <b>የሚወጣው ብር፦</b> <b>{bal:.2f} ብር</b>\n"
                 f"📌 <b>ዝርዝር መረጃ፦</b> <b>{details}</b>")
    
    try:
        bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
    except Exception as e:
        print(f"ለአድሚን መረጃ መላክ አልተቻለም: {e}")

    proof_msg = (f"💸 <b>አዲስ የክፍያ ጥያቄ (Withdrawal Request)</b>\n\n"
                 f"👤 <b>ተጠቃሚ፦</b> @{username}\n"
                 f"💰 <b>የብር መጠን፦</b> <b>{bal:.2f} ብር</b>\n"
                 f"📌 <b>STATUS፦</b> ⏳ <b>በመጠበቅ ላይ (Pending)</b>")
    
    try:
        bot.send_message(PAYOUT_CHANNEL, proof_msg, parse_mode="HTML")
    except Exception as e:
        print(f"ወደ Proof ቻናል ፖስት ማድረግ አልተቻለም: {e}")

    bot.send_message(user_id, "✅ <b>ጥያቄዎ በተሳካ ሁኔታ ለባለቤቱ ተልኳል! በአጭር ጊዜ ውስጥ ይላክልዎታል።</b>", parse_mode="HTML")

def run_bot():
    print("ቦቱ በ Render ላይ በስኬት መሥራት ጀምሯል...")
    try:
        bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        print(f"Webhook ማጽዳት አልተቻለም፦ {e}")
        
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"የግንኙነት ችግር አጋጥሟል፡ {e}። ከ 5 ሰከንድ በኋላ ድጋሚ ይሞክራል...")
            time.sleep(5)

if __name__ == "__main__":
    server_thread = Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()
    
    run_bot()
