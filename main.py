#!/usr/bin/env python3
# SynapseLab Telegram AI Bot - ready-to-deploy
# Embedded tokens as requested by user (BE CAREFUL — these are sensitive)
TELEGRAM_TOKEN = "8323894251:AAFRGQiIQm2_DQTkBACCOZOW6PgyDaFA9HU"
GEMINI_API_KEY = "AIzaSyBiAl5WbG7fIyOJpCqL9-WpSNOYISfQ5mY"

import os, time, json, logging, threading, re
from html import escape
from flask import Flask, request, redirect, url_for, render_template_string
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Try import Gemini library
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except Exception:
    genai = None
    HAS_GEMINI = False

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s - %(message)s")

CREATOR_USERNAME = "bear1berry"  # admin username
DATA_FILE = "synapse_data.json"
PORT = int(os.getenv("PORT", "10000"))

flask_app = Flask(__name__)
chat_memory = {}
user_profiles = {}
dev_mode = False
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-pro")

# Configure Gemini if possible
if GEMINI_API_KEY and HAS_GEMINI:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        logging.info("Gemini configured.")
    except Exception as e:
        logging.warning("Gemini configure error: %s", e)
else:
    logging.info("Gemini not configured or library missing. HAS_GEMINI=%s", HAS_GEMINI)

def load_data():
    global chat_memory, user_profiles, dev_mode
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                chat_memory = d.get("chat_memory", {})
                user_profiles = d.get("user_profiles", {})
                dev_mode = d.get("dev_mode", False)
            logging.info("Loaded data.")
        except Exception as e:
            logging.error("Load error: %s", e)

def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"chat_memory": chat_memory, "user_profiles": user_profiles, "dev_mode": dev_mode}, f, ensure_ascii=False, indent=2)
        logging.info("Saved data.")
    except Exception as e:
        logging.error("Save error: %s", e)

def analyze_style(text: str) -> str:
    t = text.lower()
    if any(x in t for x in ("деньги","бизнес","заработок","продажи")):
        return "деловой"
    if any(x in t for x in ("творч","арт","идея")):
        return "креативный"
    if any(x in t for x in ("жизнь","философ","смысл")):
        return "философский"
    if any(x in t for x in ("погнали","давай","быстро","срочно")):
        return "энергичный"
    return "нейтральный"

ADMIN_HTML = """<!doctype html>
<html>
<head><meta charset="utf-8"><title>Synapse Admin</title>
<style>body{background:#05060a;color:#dff7ff;font-family:Inter, Roboto, sans-serif;padding:18px}
.card{background:#0f1724;padding:12px;border-radius:10px;margin-bottom:12px}
a.btn{display:inline-block;padding:8px 12px;border-radius:8px;text-decoration:none;margin-right:8px;background:#0ea5a4;color:#001}
a.danger{background:#ef4444;color:#fff}</style>
</head><body>
<h1>Synapse — Admin</h1>
<p>Viewer: <b>{{viewer}}</b></p>
{% if not allowed %}
<div class="card">Access denied. Open <code>?user={{req_user}}</code></div>
{% else %}
<div class="card"><b>Dev:</b> {{ 'ON' if dev_mode else 'OFF' }} — <a class="btn" href="{{url_for('admin_toggle', user=viewer)}}">Toggle Dev</a></div>
<div class="card"><h3>Users ({{ users|length }})</h3>
{% for uid, p in users.items() %}<div style="margin-bottom:8px;padding:8px;border-radius:8px;background:#071728;">
<b>{{uid}}</b> — style: {{p.style}} — msgs: {{p.messages}} <a class="btn" href="{{url_for('admin_view_user', user=viewer, target=uid)}}">View</a></div>{% endfor %}</div>
{% endif %}
<hr><small>Server: {{server_info}}</small></body></html>"""

USER_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>User</title>
<style>body{background:#05060a;color:#dff7ff;padding:18px;font-family:Inter}</style></head><body>
<a href="{{url_for('admin', user=viewer)}}">← Back</a><h2>User {{target}}</h2><pre>{{history}}</pre></body></html>"""

@flask_app.route("/admin")
def admin():
    req_user = (request.args.get("user") or "").strip()
    allowed = req_user.lower() == CREATOR_USERNAME.lower()
    users_out = {k: type("P", (), {"style": v.get("style","-"), "messages": v.get("messages",0)}) for k,v in user_profiles.items()}
    server_info = f"time={time.asctime()} host={request.host}"
    return render_template_string(ADMIN_HTML, viewer=escape(req_user or "not-set"), allowed=allowed, req_user=CREATOR_USERNAME, users=users_out, dev_mode=dev_mode, server_info=server_info)

@flask_app.route("/admin/view/<target>")
def admin_view_user(target):
    req_user = (request.args.get("user") or "").strip()
    if req_user.lower() != CREATOR_USERNAME.lower():
        return "Access denied", 403
    history = chat_memory.get(target, [])[-100:]
    return render_template_string(USER_HTML, viewer=escape(req_user), target=escape(target), history=escape(str(history)))

@flask_app.route("/admin/toggle")
def admin_toggle():
    global dev_mode
    req_user = (request.args.get("user") or "").strip()
    if req_user.lower() != CREATOR_USERNAME.lower():
        return "Access denied", 403
    dev_mode = not dev_mode; save_data()
    return redirect(url_for("admin", user=req_user))

# Telegram bot logic
MAIN_MENU = [[KeyboardButton("💬 Диалог"), KeyboardButton("🧠 Анализ")],[KeyboardButton("🗓️ План"), KeyboardButton("⚙️ Настройки")]]
def build_markup(): return ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    user_profiles.setdefault(uid, {"style":"нейтральный","messages":0})
    chat_memory.setdefault(uid, [])
    text = ("🌑 <b>Synapse</b>
Привет! Я твой AI-помощник.
Кнопки внизу: Диалог, Анализ, План, Настройки.
Команды: /help /plan /analyze /profile /system /ask
Админ: только @" + CREATOR_USERNAME)
    await update.message.reply_html(text, reply_markup=build_markup()); save_data()

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = ("🛈 <b>Команды</b>:
/start /help /profile /plan /analyze /system /ask
Примеры: /ask напиши стих на тему ночи")
    await update.message.reply_html(txt)

async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id); p = user_profiles.get(uid, {"style":"-","messages":0})
    await update.message.reply_text(f"👤 Твой профиль:
• Стиль: {p['style']}
• Сообщений: {p['messages']}")

async def system_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = (update.effective_user.username or "").lower()
    if username != CREATOR_USERNAME.lower():
        await update.message.reply_text("🚫 Только создатель может использовать /system"); return
    args = context.args or []
    if not args:
        await update.message.reply_text("🛠 /system status|save|clearall|dev"); return
    cmd = args[0].lower()
    global dev_mode
    if cmd == "status":
        await update.message.reply_text(f"Users: {len(user_profiles)} Dev: {'ON' if dev_mode else 'OFF'}")
    elif cmd == "save":
        save_data(); await update.message.reply_text("Saved.")
    elif cmd == "clearall":
        user_profiles.clear(); chat_memory.clear(); save_data(); await update.message.reply_text("Cleared all.")
    elif cmd == "dev":
        dev_mode = not dev_mode; save_data(); await update.message.reply_text(f"Dev: {'ON' if dev_mode else 'OFF'}")
    else:
        await update.message.reply_text("Unknown /system command")

async def plan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id); text = " ".join(context.args) if context.args else ""
    if not text: await update.message.reply_text("Используй: /plan <цель>"); return
    m = re.search(r"(\d+)\s*дн", text)
    days = int(m.group(1)) if m else 14; goal = text
    plan = [f"День {i+1}: Задача для {goal}" for i in range(min(days,30))]
    user_profiles.setdefault(uid, {"style":"нейтральный","messages":0}); user_profiles[uid].setdefault("plans",[]).append({"goal":goal,"days":days,"plan":plan,"created":time.time()})
    save_data(); await update.message.reply_text("План создан и сохранён. Первые 7 дней:
" + "\n".join(plan[:7]))

async def analyze_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args) if context.args else ""
    if not text: await update.message.reply_text("Используй: /analyze <текст>"); return
    style = analyze_style(text); summary = text[:500]
    ai_summary = None
    if GENIAble():
        try:
            ai_summary = genai_generate("Сделай короткое резюме и ключевые выводы на русском:\n\n" + text)
        except Exception as e:
            logging.warning("Gemini analyze error: %s", e)
    out = f"🧠 Стиль: {style}\n\n" + (ai_summary or ("Резюме:\n" + summary))
    await update.message.reply_text(out)

def GENIAble() -> bool:
    return bool(GEMINI_API_KEY and HAS_GEMINI)

def genai_generate(prompt: str, max_output_tokens: int = 512) -> str:
    if not GENIAble(): raise RuntimeError("Gemini not configured")
    try:
        if hasattr(genai, "generate_text"):
            resp = genai.generate_text(model=GEMINI_MODEL, prompt=prompt, max_output_tokens=max_output_tokens)
            if hasattr(resp, "text"): return resp.text.strip()
            if isinstance(resp, dict): return resp.get("candidates",[{}])[0].get("content","")
            return str(resp)
        if hasattr(genai, "models") and hasattr(genai.models, "generate"):
            resp = genai.models.generate(model=GEMINI_MODEL, input=prompt)
            if isinstance(resp, dict) and "candidates" in resp: return resp["candidates"][0].get("content","").strip()
            return str(resp)
        raise RuntimeError("GenAI API unknown")
    except Exception as e:
        logging.exception("GenAI call failed: %s", e); raise

async def ask_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Используй: /ask <вопрос или подсказка>"); return
    uid = str(update.effective_user.id); user_profiles.setdefault(uid, {"style":"нейтральный","messages":0}); chat_memory.setdefault(uid, [])
    prompt = f"Ты — Synapse (тёмный стиль). Ответь кратко и по существу. Вопрос: {text}"
    reply = None
    if GENIAble():
        try: reply = genai_generate(prompt, max_output_tokens=600)
        except Exception as e: logging.warning("Gemini failed: %s", e); reply = None
    if not reply: reply = "Извиняюсь, Gemini недоступен. Вот простая замена: " + (text if len(text)<300 else text[:297]+"…")
    await update.message.reply_text(reply); chat_memory[uid].append({"role":"assistant","text":reply,"t":time.time()}); save_data()

async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await update.message.reply_text(f"Пользователей в памяти: {len(user_profiles)}. Твоих сообщений: {user_profiles.get(uid,{}).get('messages',0)}")

async def users_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = (update.effective_user.username or "").lower()
    if username != CREATOR_USERNAME.lower():
        await update.message.reply_text("Доступ запрещён"); return
    out = "\n".join([f"{k} — msgs:{v.get('messages',0)} style:{v.get('style','-')}" for k,v in user_profiles.items()])
    await update.message.reply_text("Users:\n" + (out or "none"))

async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    uid = str(update.effective_user.id); username = (update.effective_user.username or "").lower(); text = update.message.text.strip()
    user_profiles.setdefault(uid, {"style":"нейтральный","messages":0}); chat_memory.setdefault(uid, [])
    user_profiles[uid]["messages"] = user_profiles[uid].get("messages",0) + 1
    style = analyze_style(text); user_profiles[uid]["style"] = style
    chat_memory[uid].append({"role":"user","text":text,"t":time.time()}); chat_memory[uid] = chat_memory[uid][-200:]
    logging.info("[%s] %s", username or uid, text)
    if text in ("💬 Диалог","Диалог"):
        await update.message.reply_text("Пиши сообщение — отвечу.", reply_markup=build_markup()); return
    if text in ("🧠 Анализ","Анализ"):
        await update.message.reply_text("Отправь текст или используй /analyze"); return
    if text in ("🗓️ План","План"):
        await update.message.reply_text("Напиши цель или используй /plan"); return
    if text in ("⚙️ Настройки","Настройки"):
        await update.message.reply_text("Команды: /profile, /system"); return
    recent = "\n".join([f"{m['role']}: {m['text']}" for m in chat_memory[uid][-10:]])
    prompt = f"Ты — Synapse, тёмный стиль. Пользователь стиль: {style}\nДиалог:\n{recent}\nПользователь: {text}\nОтвет:"
    reply = None
    if GENIAble():
        try: reply = genai_generate(prompt, max_output_tokens=600)
        except Exception as e: logging.warning("Gemini failed, fallback: %s", e); reply = None
    if not reply:
        q_words = ("что","как","почему","когда","где","кто","помоги","помощь")
        if any(text.lower().startswith(w) for w in q_words):
            reply = f"Я вижу вопрос: «{text}». Могу предложить план или краткий ответ."
        else:
            shorter = text if len(text) < 200 else text[:197] + "…"
            reply = f"Окей — {shorter}\n(Напиши 'детальнее' для расширенного ответа.)"
    if dev_mode and username == CREATOR_USERNAME.lower():
        reply += "\n\n--- DEV PROMPT (truncated) ---\n" + prompt[:800]
    await update.message.reply_text(reply, reply_markup=build_markup())
    chat_memory[uid].append({"role":"assistant","text":reply,"t":time.time()}); save_data()

def start_flask_thread():
    def _run():
        logging.info("Starting Flask on port %s", PORT)
        flask_app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
    t = threading.Thread(target=_run, daemon=True); t.start(); return t

def main():
    load_data(); start_flask_thread()
    if not TELEGRAM_TOKEN:
        logging.error("TELEGRAM_TOKEN missing"); return
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("profile", profile_handler))
    application.add_handler(CommandHandler("system", system_handler))
    application.add_handler(CommandHandler("plan", plan_handler))
    application.add_handler(CommandHandler("analyze", analyze_handler))
    application.add_handler(CommandHandler("ask", ask_handler))
    application.add_handler(CommandHandler("stats", stats_handler))
    application.add_handler(CommandHandler("users", users_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))
    logging.info("Starting Telegram polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
