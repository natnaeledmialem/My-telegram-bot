import os
import re
from flask import Flask
import telebot
from telebot import types

# --- ማስተካከያ ቦታዎች ---
BOT_TOKEN = "8884008636:AAHYs5SV-H_HBMSc02LTsZAUP2iz8r12CSw"
CHANNELS = ["@et5_m"]
INITIAL_ADMIN = 7435977089  # ዋናው የመጀመሪያው አድሚን
ADMINS = [INITIAL_ADMIN]

REFERRAL_BONUS = 3.00
MIN_WITHDRAW = 30.00
# ---------------------

bot = telebot.TeleBot(BOT_TOKEN)
users_db = {}


def check_status(user_id):
  for channel in CHANNELS:
    try:
      member = bot.get_chat_member(channel, user_id)
      if member.status not in ["member", "administrator", "creator"]:
        return False
    except Exception:
      return False
  return True


def get_not_joined_channels(user_id):
  not_joined = []
  for channel in CHANNELS:
    try:
      member = bot.get_chat_member(channel, user_id)
      if member.status not in ["member", "administrator", "creator"]:
        not_joined.append(channel)
    except Exception:
      not_joined.append(channel)
  return not_joined


def main_keyboard():
  markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  btn1 = types.KeyboardButton("🟢 Balance")
  btn2 = types.KeyboardButton("🟢 Referral")
  btn3 = types.KeyboardButton("🟩 Withdraw")
  btn4 = types.KeyboardButton("🟩 Wallet")
  btn5 = types.KeyboardButton("🟢 Statistics")
  markup.add(btn1, btn2)
  markup.add(btn3, btn4)
  markup.add(btn5)
  return markup


@bot.message_handler(commands=["start"])
def start(message):
  user_id = message.from_user.id
  username = message.from_user.username or "User"
  first_name = message.from_user.first_name

  if user_id in users_db and users_db[user_id].get("banned", False):
    bot.send_message(
        user_id,
        "<b>❌ ፖሊሲ በመጣስዎ ምክንያት አካውንትዎ ታግዷል! (Your account is"
        " banned!)</b>",
        parse_mode="html",
    )
    return

  if user_id not in users_db:
    users_db[user_id] = {
        "balance": 0.0,
        "referred_by": None,
        "referred_count": 0,
        "wallet": "Not Set",
        "banned": False,
    }

    args = message.text.split()
    if len(args) > 1:
      try:
        referrer_id = int(args[1])
        if referrer_id == user_id:
          users_db[user_id]["banned"] = True
          bot.send_message(
              user_id,
              "<b>❌ ፖሊሲ በመጣስዎ ምክንያት አካውንትዎ በቋሚነት ታግዷል (Multi-account is"
              " not allowed)!</b>",
              parse_mode="html",
          )
          return

        if referrer_id in users_db and not users_db[referrer_id]["banned"]:
          users_db[user_id]["referred_by"] = referrer_id
      except ValueError:
        pass

  not_joined = get_not_joined_channels(user_id)

  if not_joined:
    markup = types.InlineKeyboardMarkup()
    for i, ch in enumerate(not_joined, 1):
      url_link = f"https://t.me/{ch.replace('@', '')}"
      markup.add(types.InlineKeyboardButton(f"📢 Join Channel {i}", url=url_link))

    markup.add(
        types.InlineKeyboardButton("✅ Joined (Check)", callback_data="check_join")
    )

    bot.send_message(
        user_id,
        (
            f"<b>👋 Hello {first_name}!\n\n✨ Welcome to our earning and withdrawal"
            " bot. እንኳን በደህና መጡ!\n\n⚠️ Please join all channels below to start"
            " using the bot! ቻናሎቹን መቀላቀል ግዴታ ነው! Click '✅ Joined' after"
            " joining.</b>"
        ),
        parse_mode="html",
        reply_markup=markup,
    )
    return

  ref_id = users_db[user_id]["referred_by"]
  if ref_id and users_db[user_id]["referred_count"] == 0:
    global REFERRAL_BONUS
    users_db[ref_id]["balance"] += REFERRAL_BONUS
    users_db[ref_id]["referred_count"] += 1
    users_db[user_id]["referred_count"] = -1
    try:
      bot.send_message(
          ref_id,
          (
              f"<b>🎉 Congratulations! You invited a new user and earned 💰"
              f" {REFERRAL_BONUS} Birr! አዲስ ሰው ጋብዘዋል!</b>"
          ),
          parse_mode="html",
      )
    except:
      pass

  bot.send_message(
      user_id,
      (
          f"<b>✨ Hello {first_name}! Welcome back to the bot!\nእንኳን በደህና መጡ!"
          " Please choose an option from the menu below 👇\nከታች ካሉት ቁልፎች"
          " ይምረጡ፦</b>"
      ),
      parse_mode="html",
      reply_markup=main_keyboard(),
  )


@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def check_callback(call):
  user_id = call.from_user.id
  if users_db.get(user_id, {}).get("banned", False):
    return

  if check_status(user_id):
    try:
      bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
      pass
    start(call.message)
  else:
    bot.answer_callback_query(
        call.id,
        "❌ Please join all channels first! ቻናሎቹን ሙሉ በሙሉ አልተቀላቀሉም!",
        show_alert=True,
    )


# 👑 አድሚን ፓነል ትእዛዝ
@bot.message_handler(commands=["admin"])
def admin_panel(message):
  if message.from_user.id not in ADMINS:
    bot.reply_to(
        message, "<b>❌ This command is for admins only!</b>", parse_mode="html"
    )
    return

  markup = types.InlineKeyboardMarkup(row_width=2)
  markup.add(
      types.InlineKeyboardButton("💸 Set Min Withdraw", callback_data="set_minw"),
      types.InlineKeyboardButton("🎁 Set Per Referral", callback_data="set_pref"),
      types.InlineKeyboardButton("📢 Broadcast", callback_data="broadcast"),
      types.InlineKeyboardButton(
          "⚙️ Manage Channels", callback_data="manage_channels"
      ),
      types.InlineKeyboardButton("👑 Admin Management", callback_data="admin_mgmt"),
      types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_home"),
  )

  bot.reply_to(
      message,
      (
          f"<b>👑 Welcome to Admin Panel!\n\n⚙️ Current Settings:\n- Min"
          f" Withdraw: {MIN_WITHDRAW} Birr\n- Per Referral: {REFERRAL_BONUS}"
          f" Birr\n- Total Channels: {len(CHANNELS)}\n- Total Admins:"
          f" {len(ADMINS)}\n\nChoose an option from below 👇</b>"
      ),
      parse_mode="html",
      reply_markup=markup,
  )


@bot.message_handler(func=lambda message: True)
def handle_buttons(message):
  user_id = message.from_user.id
  text = message.text

  if text and text.startswith("/admin"):
    if user_id not in ADMINS:
      bot.reply_to(
          message, "<b>❌ This command is for admins only!</b>", parse_mode="html"
      )
      return
    admin_panel(message)
    return

  if user_id not in users_db:
    bot.send_message(
        user_id, "Please type /start first. እባክዎ /start ይበሉ ዋናውን ማኑ ለማግኘት"
    )
    return

  if users_db[user_id].get("banned", False):
    bot.send_message(
        user_id, "<b>❌ Your account is banned! አካውንትዎ ታግዷል!</b>", parse_mode="html"
    )
    return

  if not check_status(user_id):
    start(message)
    return

  if text == "🟢 Balance":
    bal = users_db[user_id]["balance"]
    count = max(0, users_db[user_id]["referred_count"])
    wallet_num = users_db[user_id]["wallet"]
    bot.send_message(
        user_id,
        (
            f"<b>💳 Your Account Info:\n\n💰 Balance: <code>{bal}</code>"
            f" Birr\n💳 Telebirr Wallet: <code>{wallet_num}</code>\n👥 Total"
            f" Referrals: <code>{count}</code> users</b>"
        ),
        parse_mode="html",
    )

  elif text == "🟢 Referral":
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    count = max(0, users_db[user_id]["referred_count"])
    bot.send_message(
        user_id,
        (
            f"<b>👥 Referral Program:\n\n🔗 Your Referral Link:\n{ref_link}\n\n🎁"
            f" Note: You earn <code>{REFERRAL_BONUS} Birr</code> for every"
            f" invited person!\n📈 Total Referrals: <code>{count}</code>"
            " users</b>"
        ),
        parse_mode="html",
    )

  elif text == "🟩 Wallet":
    msg = bot.send_message(
        user_id,
        (
            "<b>💳 Enter your Telebirr phone number:\n\nPlease send a valid"
            " Telebirr phone number starting with '09' and containing exactly"
            " 10 digits (e.g., 0912345678):</b>"
        ),
        parse_mode="html",
    )
    bot.register_next_step_handler(msg, process_wallet_input)

  elif text == "🟩 Withdraw":
    wallet_num = users_db[user_id]["wallet"]
    if wallet_num == "Not Set":
      bot.send_message(
          user_id,
          (
              "<b>⚠️ Please set your Telebirr wallet number before"
              " withdrawing!\n(Click '🟩 Wallet' below to set it)</b>"
          ),
          parse_mode="html",
      )
      return

    bal = users_db[user_id]["balance"]
    if bal < MIN_WITHDRAW:
      bot.send_message(
          user_id,
          (
              f"<b>❌ Sorry, you need at least <code>{MIN_WITHDRAW} Birr</code> to"
              f" withdraw.\n💵 Your Balance: <code>{bal}</code> Birr</b>"
          ),
          parse_mode="html",
      )
    else:
      users_db[user_id]["balance"] = 0.0
      username = message.from_user.username or "No Username"

      admin_msg = (
          f"🚨 **New Withdrawal Request!**\n\n"
          f"👤 User ID: `{user_id}`\n"
          f"🏷 Username: @{username}\n"
          f"💳 Telebirr Number: `{wallet_num}`\n"
          f"💰 Amount: {bal} Birr"
      )
      for adm in ADMINS:
        try:
          bot.send_message(adm, admin_msg, parse_mode="markdown")
        except:
          pass

      bot.send_message(
          user_id,
          (
              f"<b>✅ Withdrawal request submitted successfully!\n💳 Telebirr:"
              f" {wallet_num}\n💰 Amount: {bal} Birr\n\nIt will be sent to your"
              " account soon!</b>"
          ),
          parse_mode="html",
      )

  elif text == "🟢 Statistics":
    total_users = len(users_db)
    bot.send_message(
        user_id,
        (
            f"<b>📊 Bot Statistics:\n\n👥 Total Users: <code>{total_users}</code>"
            " users</b>"
        ),
        parse_mode="html",
    )


def process_wallet_input(message):
  user_id = message.from_user.id
  phone = message.text.strip()

  if re.match(r"^09\d{8}$", phone):
    users_db[user_id]["wallet"] = phone
    bot.send_message(
        user_id,
        (
            f"<b>Telebirr number saved successfully! ✅\n💳 Number:"
            f" <code>{phone}</code></b>"
        ),
        parse_mode="html",
        reply_markup=main_keyboard(),
    )
  else:
    msg = bot.send_message(
        user_id,
        (
            "<b>❌ Invalid phone number!\n\nPlease send a valid Telebirr number"
            " starting with '09' and having 10 digits:</b>"
        ),
        parse_mode="html",
    )
    bot.register_next_step_handler(msg, process_wallet_input)


@bot.callback_query_handler(
    func=lambda call: call.data
    in [
        "set_minw",
        "set_pref",
        "broadcast",
        "manage_channels",
        "admin_mgmt",
        "back_home",
        "add_admin",
        "remove_admin",
        "back_admin",
        "add_ch",
        "remove_ch",
    ]
)
def admin_callbacks(call):
  if call.from_user.id not in ADMINS:
    return

  if call.data == "back_home":
    try:
      bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
      pass
    bot.send_message(
        call.message.chat.id,
        "<b>🏠 Returned to Main Menu / ወደ ዋናው ማኑ ተመልሰዋል 👇</b>",
        parse_mode="html",
        reply_markup=main_keyboard(),
    )

  elif call.data == "set_minw":
    msg = bot.send_message(
        call.message.chat.id,
        "<b>Enter new minimum withdrawal amount (number only):</b>",
        parse_mode="html",
    )
    bot.register_next_step_handler(msg, save_new_minw)

  elif call.data == "set_pref":
    msg = bot.send_message(
        call.message.chat.id,
        "<b>Enter new referral bonus amount (number only):</b>",
        parse_mode="html",
    )
    bot.register_next_step_handler(msg, save_new_pref)

  elif call.data == "broadcast":
    msg = bot.send_message(
        call.message.chat.id,
        "<b>Send the message or photo you want to broadcast:</b>",
        parse_mode="html",
    )
    bot.register_next_step_handler(msg, execute_broadcast)

  elif call.data == "manage_channels":
    ch_list = "\n".join(CHANNELS)
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("➕ Add Channel", callback_data="add_ch"),
        types.InlineKeyboardButton("➖ Remove Channel", callback_data="remove_ch"),
        types.InlineKeyboardButton("🔙 Back to Admin", callback_data="back_admin"),
    )
    bot.send_message(
        call.message.chat.id,
        f"<b>📢 Current Channels:\n{ch_list}\n\nSelect action:</b>",
        parse_mode="html",
        reply_markup=markup,
    )

  elif call.data == "admin_mgmt":
    adm_list = "\n".join([str(a) for a in ADMINS])
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("➕ Add Admin", callback_data="add_admin"),
        types.InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin"),
        types.InlineKeyboardButton("🔙 Back to Admin", callback_data="back_admin"),
    )
    bot.send_message(
        call.message.chat.id,
        f"<b>👑 Current Admins (IDs):\n{adm_list}\n\nSelect action:</b>",
        parse_mode="html",
        reply_markup=markup,
    )

  elif call.data == "add_admin":
    msg = bot.send_message(
        call.message.chat.id,
        "<b>➕ Enter Telegram User ID to add as Admin:</b>",
        parse_mode="html",
    )
    bot.register_next_step_handler(msg, add_admin_process)

  elif call.data == "remove_admin":
    msg = bot.send_message(
        call.message.chat.id,
        "<b>➖ Enter Telegram User ID to remove from Admin:</b>",
        parse_mode="html",
    )
    bot.register_next_step_handler(msg, remove_admin_process)

  elif call.data == "back_admin":
    try:
      bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
      pass
    admin_panel(call.message)

  elif call.data == "add_ch":
    msg = bot.send_message(
        call.message.chat.id,
        "<b>➕ Enter channel username to add (e.g., @channelname):</b>",
        parse_mode="html",
    )
    bot.register_next_step_handler(msg, add_channel_process)

  elif call.data == "remove_ch":
    msg = bot.send_message(
        call.message.chat.id,
        "<b>➖ Enter channel username to remove (e.g., @channelname):</b>",
        parse_mode="html",
    )
    bot.register_next_step_handler(msg, remove_channel_process)


def save_new_minw(message):
  global MIN_WITHDRAW
  try:
    val = float(message.text.strip())
    MIN_WITHDRAW = val
    bot.reply_to(
        message,
        f"<b>✅ Minimum withdraw updated successfully to {val} Birr!</b>",
        parse_mode="html",
    )
  except ValueError:
    bot.reply_to(message, "<b>❌ Please enter a valid number!</b>", parse_mode="html")


def save_new_pref(message):
  global REFERRAL_BONUS
  try:
    val = float(message.text.strip())
    REFERRAL_BONUS = val
    bot.reply_to(
        message,
        f"<b>✅ Referral bonus updated successfully to {val} Birr!</b>",
        parse_mode="html",
    )
  except ValueError:
    bot.reply_to(message, "<b>❌ Please enter a valid number!</b>", parse_mode="html")


def execute_broadcast(message):
  success = 0
  fail = 0
  for u_id in users_db.keys():
    try:
      bot.copy_message(u_id, message.chat.id, message.message_id)
      success += 1
    except:
      fail += 1

  bot.reply_to(
      message,
      (
          f"<b>📢 Broadcast completed!\n\n✅ Delivered: {success}\n❌ Failed:"
          f" {fail}</b>"
      ),
      parse_mode="html",
  )


def add_channel_process(message):
  global CHANNELS
  ch = message.text.strip()
  if not ch.startswith("@"):
    ch = "@" + ch

  if ch not in CHANNELS:
    CHANNELS.append(ch)
    bot.reply_to(
        message,
        f"<b>✅ Channel {ch} added successfully and active now!</b>",
        parse_mode="html",
    )
  else:
    bot.reply_to(
        message, f"<b>⚠️ Channel already exists in list!</b>", parse_mode="html"
    )


def remove_channel_process(message):
  global CHANNELS
  ch = message.text.strip()
  if not ch.startswith("@"):
    ch = "@" + ch

  if ch in CHANNELS:
    CHANNELS.remove(ch)
    bot.reply_to(
        message,
        f"<b>✅ Channel {ch} removed from list successfully!</b>",
        parse_mode="html",
    )
  else:
    bot.reply_to(
        message, f"<b>⚠️ Channel not found in list!</b>", parse_mode="html"
    )


def add_admin_process(message):
  global ADMINS
  try:
    new_adm = int(message.text.strip())
    if new_adm not in ADMINS:
      ADMINS.append(new_adm)
      bot.reply_to(
          message,
          f"<b>✅ User ID {new_adm} added as Admin successfully!</b>",
          parse_mode="html",
      )
    else:
      bot.reply_to(
          message, f"<b>⚠️ This user is already an Admin!</b>", parse_mode="html"
      )
  except ValueError:
    bot.reply_to(
        message,
        "<b>❌ Invalid ID! Please send numbers only.</b>",
        parse_mode="html",
    )


def remove_admin_process(message):
  global ADMINS
  try:
    rem_adm = int(message.text.strip())
    if rem_adm == INITIAL_ADMIN:
      bot.reply_to(
          message,
          "<b>❌ You cannot remove the main primary admin!</b>",
          parse_mode="html",
      )
      return

    if rem_adm in ADMINS:
      ADMINS.remove(rem_adm)
      bot.reply_to(
          message,
          f"<b>✅ User ID {rem_adm} removed from Admins successfully!</b>",
          parse_mode="html",
      )
    else:
      bot.reply_to(
          message, f"<b>⚠️ Admin ID not found in list!</b>", parse_mode="html"
      )
  except ValueError:
    bot.reply_to(
        message,
        "<b>❌ Invalid ID! Please send numbers only.</b>",
        parse_mode="html",
    )


print("Bot system running smoothly...")
bot.delete_webhook(drop_pending_updates=True)

app = Flask("")


@app.route("/")
def home():
  return "Bot is alive and running!"


def run_flask():
  port = int(os.environ.get("PORT", 8080))
  app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
  from threading import Thread

  Thread(target=run_flask).start()

  print("Bot is polling...")
  bot.infinity_polling(skip_pending=True)
