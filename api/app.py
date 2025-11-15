from flask import Flask, render_template, request, jsonify, session, send_from_directory
import os
import re
import subprocess
import threading
import platform
import uuid
import webbrowser
import yt_dlp
import google.generativeai as genai
import shutil

# Correct folders for Vercel
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))

app = Flask(
    __name__,
    static_folder=os.path.join(ROOT, "static"),
    template_folder=os.path.join(ROOT, "templates")
)
app.secret_key = "supersecretkey"

# ----------------------------
#  REMOVE pyttsx3 on VERCEL
# ----------------------------
# pyttsx3 requires system audio libraries not available in Vercel.
# We disable TTS on Vercel to avoid runtime crashes.

def speak_text(text):
    return  # Disabled for Vercel

# ----------------------------
#  GEMINI INIT
# ----------------------------
API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBYesGjVe5oinLRiY_3ndW50KFBgiNjrvo")
try:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")
except:
    model = None

chat_sessions = {}
PUNCT_STRIP = re.compile(r"[.,!?;:]+$")


def normalize(text: str) -> str:
    return PUNCT_STRIP.sub("", (text or "").strip().lower())


# ----------------------------
#  YouTube Audio Search
# ----------------------------
def search_youtube_audio(query):
    try:
        opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "noplaylist": True,
            "default_search": "ytsearch1",
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if "entries" in info:
                info = info["entries"][0]
            return {
                "title": info.get("title"),
                "url": info.get("url"),
                "id": info.get("id"),
            }
    except Exception as e:
        print("YouTube error:", e)
        return None


# ----------------------------
#  Open App (Disabled on Vercel)
# ----------------------------
def open_app(target):
    return {"reply": "⚠️ Opening apps is not supported on Vercel."}


# ----------------------------
#  Chat Logic
# ----------------------------
def nova_response(user_input, user_id):
    raw_text = user_input or ""
    ui = normalize(raw_text)

    # Play music
    if ui.startswith("play "):
        song = raw_text[5:]
        music = search_youtube_audio(song)
        if not music:
            return {"reply": "❌ Could not find that song."}
        return {"reply": f"🎵 {music['title']}", "music_url": music["url"]}

    # Greetings
    if any(w in ui for w in ["hi", "hello", "hey"]):
        return {"reply": "👋 Hello! How can I help you?"}

    if "who are you" in ui:
        return {"reply": "🤖 I am PRINIX, your AI assistant."}

    # Gemini Chat
    if model:
        chat = chat_sessions.get(user_id) or model.start_chat()
        chat_sessions[user_id] = chat

        try:
            response = chat.send_message(raw_text)
            reply = (response.text or "").strip()
        except:
            reply = "⚠️ Error contacting AI model."

        return {"reply": reply}

    return {"reply": "🤔 I'm not sure, but I'm learning!"}


# ----------------------------
#  ROUTES
# ----------------------------

@app.route("/")
def home():
    return render_template("index.html")


# Serve static files manually (for Vercel)
@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(os.path.join(ROOT, "static"), filename)


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json() or {}
    message = data.get("message", "")

    user_id = session.get("user_id")
    if not user_id:
        user_id = str(uuid.uuid4())
        session["user_id"] = user_id

    return jsonify(nova_response(message, user_id))


# ----------------------------
# Required for Vercel
# ----------------------------
def handler(request, context):
    return app(request, context)


# Local debug
if __name__ == "__main__":
    app.run(debug=True)
