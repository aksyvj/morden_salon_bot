from telegram import (
    Update, ReplyKeyboardMarkup,
    KeyboardButton, InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    ContextTypes, MessageHandler,
    CallbackQueryHandler, filters
)
import json, os

# ===== CONFIG =====
BOT_TOKEN = os.getenv("7747554430:AAFArMAJFB1GFpbp3VaBRZ60fC14r8zovvs")
ADMIN_ID = int(os.getenv("993572089"))
QUEUE_FILE = "queue.json"

SERVICES = {
    "✂️ Haircut (15 min)": ("Haircut", 15),
    "🧔 Beard (10 min)": ("Beard", 10),
    "💆 Facial (25 min)": ("Facial", 25)
}

user_states = {}

# ===== HELPERS =====
def load_queue():
    if not os.path.exists(QUEUE_FILE):
        return []
    with open(QUEUE_FILE, "r") as f:
        return json.load(f)

def save_queue(queue):
    with open(QUEUE_FILE, "w") as f:
        json.dump(queue, f)

def next_token(queue):
    return queue[-1]["token"] + 1 if queue else 1

# ===== START / CUSTOMER MENU =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["🟢 Join Queue"],
        ["📍 My Status", "❌ Cancel"]
    ]
    await update.message.reply_text(
        "👋 Welcome to our Salon\nPlease choose:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ===== CUSTOMER FLOW =====
async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_states[update.effective_user.id] = {"step": "name"}
    await update.message.reply_text("Please enter your name:")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "🟢 Join Queue":
        await join(update, context)
        return
    if text == "📍 My Status":
        await status(update, context)
        return
    if text == "❌ Cancel":
        await cancel(update, context)
        return

    if user_id not in user_states:
        return

    state = user_states[user_id]

    if state["step"] == "name":
        state["name"] = text
        state["step"] = "phone"
        keyboard = [[KeyboardButton("📞 Share Phone Number", request_contact=True)]]
        await update.message.reply_text(
            "Share your phone number:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_states:
        return

    user_states[user_id]["phone"] = update.message.contact.phone_number
    user_states[user_id]["step"] = "service"

    keyboard = [[s] for s in SERVICES.keys()]
    await update.message.reply_text(
        "Choose service:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    )

async def service_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_states:
        return
    if update.message.text not in SERVICES:
        return

    queue = load_queue()
    service, minutes = SERVICES[update.message.text]
    token = next_token(queue)
    data = user_states[user_id]

    queue.append({
        "token": token,
        "id": user_id,
        "name": data["name"],
        "phone": data["phone"],
        "service": service,
        "time": minutes
    })
    save_queue(queue)
    user_states.pop(user_id)

    wait = sum(u["time"] for u in queue[:-1])
    await update.message.reply_text(
        f"✅ Token #{token}\n"
        f"Service: {service}\n"
        f"⏳ Approx wait: {wait} min\n\n"
        f"Thank you 🙏"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    queue = load_queue()
    wait = 0
    for u in queue:
        if u["id"] == update.effective_user.id:
            await update.message.reply_text(
                f"🎟 Token #{u['token']}\n"
                f"Service: {u['service']}\n"
                f"⏳ Waiting: {wait} min"
            )
            return
        wait += u["time"]
    await update.message.reply_text("❌ You are not in queue.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    queue = load_queue()
    queue = [u for u in queue if u["id"] != update.effective_user.id]
    save_queue(queue)
    await update.message.reply_text("❌ You have been removed from queue.")

# ===== OWNER PANEL =====
async def owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    keyboard = [
        [InlineKeyboardButton("➕ Add Walk-in", callback_data="walkin")],
        [InlineKeyboardButton("➡️ Next Customer", callback_data="next")],
        [InlineKeyboardButton("❌ Remove Current", callback_data="remove")],
        [InlineKeyboardButton("🧹 Clear Queue", callback_data="clear")]
    ]
    await update.message.reply_text(
        "👨‍💼 Owner Control Panel",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    queue = load_queue()

    if query.data == "walkin":
        keyboard = [[InlineKeyboardButton(s, callback_data=f"walkin|{s}")]
                    for s in SERVICES.keys()]
        await query.message.reply_text(
            "Select service for WALK-IN:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("walkin|"):
        service_key = query.data.split("|")[1]
        service, minutes = SERVICES[service_key]
        token = next_token(queue)

        queue.append({
            "token": token,
            "id": None,
            "name": "WALK-IN",
            "phone": None,
            "service": service,
            "time": minutes
        })
        save_queue(queue)
        await query.message.reply_text(
            f"✅ WALK-IN added\nToken #{token} – {service}"
        )

    elif query.data == "next":
        if not queue:
            await query.message.reply_text("Queue empty.")
            return
        current = queue.pop(0)
        save_queue(queue)
        if current["id"]:
            await context.bot.send_message(
                chat_id=current["id"],
                text="🔔 Your turn now! Please come to salon."
            )
        await query.message.reply_text(
            f"➡️ Serving Token #{current['token']} – {current['service']}"
        )

    elif query.data == "remove":
        if queue:
            removed = queue.pop(0)
            save_queue(queue)
            await query.message.reply_text(
                f"❌ Removed Token #{removed['token']}"
            )

    elif query.data == "clear":
        save_queue([])
        await query.message.reply_text("🧹 Queue cleared.")

# ===== RUN =====
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("owner", owner))
app.add_handler(CallbackQueryHandler(callbacks))
app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(MessageHandler(filters.TEXT, service_selected))

app.run_polling()
