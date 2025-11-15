from flask import Flask, render_template, request, jsonify, session
import os, re, subprocess, webbrowser, threading, platform, uuid
import yt_dlp, pyttsx3, google.generativeai as genai

app = Flask(__name__)
app.secret_key = "supersecretkey"  # ⚠️ Change in production

# ===================== TTS =====================
engine = pyttsx3.init()
last_reply = ""


def speak_text(text):
    """Speak text using TTS asynchronously"""
    if not text:
        return
    def run():
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()


# ===================== Gemini AI =====================
API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBYesGjVe5oinLRiY_3ndW50KFBgiNjrvo")
try:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")
except Exception:
    model = None

chat_sessions = {}

# ===================== Helpers =====================
PUNCT_STRIP = re.compile(r"[.,!?;:]+$")

def normalize(text: str) -> str:
    return PUNCT_STRIP.sub("", (text or "").strip().lower())


# ===================== YouTube Search =====================
def search_youtube_audio(query):
    """Search YouTube and get direct audio URL"""
    try:
        opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "noplaylist": True,
            "default_search": "ytsearch1"
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if "entries" in info:
                info = info["entries"][0]
            return {
                "title": info.get("title"),
                "url": info.get("url"),
                "id": info.get("id")
            }
    except Exception as e:
        print("❌ YouTube error:", e)
        return None


# ===================== Open Apps =====================
def open_app(app_name):
    """Launch common system apps"""
    system = platform.system()
    try:
        if system == "Windows":
            if app_name in ("notepad",):
                os.startfile("notepad.exe"); return "✅ Opening Notepad…"
            if app_name in ("calculator", "calc"):
                os.startfile("calc.exe"); return "✅ Opening Calculator…"
            if app_name == "chrome":
                subprocess.Popen(["start", "", "chrome"], shell=True)
                return "✅ Opening Chrome…"
            subprocess.Popen([app_name], shell=True)
            return f"✅ Opening {app_name}…"
        elif system == "Darwin":
            subprocess.Popen(["open", "-a", app_name])
            return f"✅ Opening {app_name}…"
        else:
            subprocess.Popen([app_name])
            return f"✅ Opening {app_name}…"
    except Exception as e:
        return f"⚠️ Error: {e}"


# ===================== Command Handler =====================
def nova_response(user_input, user_id):
    """Main AI command handler"""
    global last_reply
    raw_text, ui = user_input or "", normalize(user_input)

    # --- Play Music ---
    if ui.startswith("play "):
        song = raw_text[5:]
        music = search_youtube_audio(song)
        if not music:
            return {"reply": "❌ Could not find that song."}

        # Clean title only (remove extra YouTube info)
        title = music["title"].split("|")[0].strip()
        reply = f"🎵 {title}"
        last_reply = reply
        speak_text(title)

        # Return direct playable URL for frontend
        return {"reply": reply, "music_url": music["url"]}

    # --- Open apps/sites ---
    if ui.startswith("open "):
        target = raw_text[5:]
        reply = open_app(target)
        last_reply = reply
        speak_text(reply)
        return {"reply": reply}

    # --- Smalltalk ---
    if any(w in ui for w in ["hi", "hello", "hey"]):
        return {"reply": "👋 Hello! How can I help you?"}
    if "how are you" in ui:
        return {"reply": "😊 I'm running fine, ready to assist."}
    if "time" in ui:
        from datetime import datetime
        return {"reply": f"🕒 {datetime.now().strftime('%I:%M %p')}"}
    if "date" in ui:
        from datetime import datetime
        return {"reply": f"📅 {datetime.now().strftime('%A, %d %B %Y')}"}
    if "who are you" in ui:
        return {"reply": "🤖 I am NOVA, your AI assistant."}

    # --- Read last reply ---
    if ui == "read":
        if last_reply:
            speak_text(last_reply)
            return {"reply": f"🔊 {last_reply}"}
        return {"reply": "❌ No reply to read."}

    # --- AI Chat Fallback ---
    if model:
        chat = chat_sessions.get(user_id) or model.start_chat()
        chat_sessions[user_id] = chat
        response = chat.send_message(raw_text)
        reply = (response.text or "").strip() or "🤖 (No response)"
        last_reply = reply
        return {"reply": reply}

    return {"reply": "🤔 I'm not sure, but I'm learning!"}


# ===================== Routes =====================
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(force=True) or {}
    message = data.get("message", "")
    user_id = session.get("user_id", str(uuid.uuid4()))
    session["user_id"] = user_id
    return jsonify(nova_response(message, user_id))


# ===================== Run =====================
if __name__ == "__main__":
    print("🚀 NOVA running at http://127.0.0.1:5000")
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(debug=True)
