from flask import Flask, render_template, request, jsonify, session
import os
import re
import subprocess
import webbrowser
import threading
import platform
import uuid
import urllib.parse
import yt_dlp
import pyttsx3
import google.generativeai as genai
import shutil

# IMPORTANT: Correct paths for Vercel
app = Flask(__name__, static_folder="../static", template_folder="../templates")
app.secret_key = "supersecretkey"

engine = pyttsx3.init()
last_reply = ""


def speak_text(text):
    if not text:
        return

    def run():
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception:
            pass

    threading.Thread(target=run, daemon=True).start()


API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBYesGjVe5oinLRiY_3ndW50KFBgiNjrvo")
try:
    if API_KEY:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")
    else:
        model = None
except Exception:
    model = None

chat_sessions = {}

PUNCT_STRIP = re.compile(r"[.,!?;:]+$")


def normalize(text: str) -> str:
    return PUNCT_STRIP.sub("", (text or "").strip().lower())


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
        print("❌ YouTube error:", e)
        return None


def _open_path_cross_platform(path):
    try:
        system = platform.system()
        if system == "Windows":
            os.startfile(path)
            return True, None
        elif system == "Darwin":
            subprocess.Popen(["open", path])
            return True, None
        else:
            if shutil.which("xdg-open"):
                subprocess.Popen(["xdg-open", path])
            else:
                subprocess.Popen([path], shell=True)
            return True, None
    except Exception as e:
        return False, str(e)


def open_app(target):
    if not target or not str(target).strip():
        return {"reply": "❌ No target provided."}

    system = platform.system()
    original_target = str(target).strip().strip('"').strip("'")
    target_lower = original_target.lower()

    possible_paths = [
        original_target,
        os.path.join(os.getcwd(), original_target),
        os.path.expanduser(original_target),
        os.path.expanduser(f"~/{original_target}"),
    ]

    for path in possible_paths:
        try:
            path = os.path.expanduser(path)
            if os.path.exists(path):
                success, err = _open_path_cross_platform(path)
                if success:
                    kind = "folder" if os.path.isdir(path) else "file"
                    return {"reply": f"📁 Opening {kind}: {path}", "redirect": path}
                else:
                    return {"reply": f"⚠️ Could not open {path}: {err}"}
        except Exception:
            continue

    if system == "Windows":
        common_apps = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "cmd": "cmd.exe",
            "paint": "mspaint.exe",
            "explorer": "explorer.exe",
            "task manager": "taskmgr.exe",
            "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        }

        for key, exe in common_apps.items():
            if key in target_lower or target_lower in key:
                exe_path = exe.replace("%USERNAME%", os.getenv("USERNAME", ""))
                try:
                    if os.path.exists(exe_path):
                        subprocess.Popen([exe_path], shell=True)
                    else:
                        subprocess.Popen([exe], shell=True)
                    return {"reply": f"✅ Opening {key.capitalize()}...", "redirect": exe}
                except Exception as e:
                    return {"reply": f"⚠️ Failed to open {key}: {e}"}

    if re.search(r"\.[a-z]{2,}$", target_lower):
        url = target_lower
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        webbrowser.open(url)
        return {"reply": f"🌐 Opening website: {url}", "redirect": url}

    return {"reply": f"❌ Unable to open {original_target}."}


def nova_response(user_input, user_id):
    global last_reply
    raw_text, ui = user_input or "", normalize(user_input)

    if ui.startswith("play "):
        song = raw_text[5:]
        music = search_youtube_audio(song)
        if not music:
            return {"reply": "❌ Could not find that song."}
        title = music["title"]
        reply = f"🎵 {title}"
        last_reply = reply
        speak_text(title)
        return {"reply": reply, "music_url": music["url"]}

    if ui.startswith("open "):
        target = raw_text[5:].strip()
        r = open_app(target)
        reply = r.get("reply")
        last_reply = reply
        speak_text(reply)
        return r

    if any(w in ui for w in ["hi", "hello", "hey"]):
        return {"reply": "👋 Hello! How can I help you?"}

    if "who are you" in ui:
        return {"reply": "🤖 I am PRINIX, your AI assistant."}

    if model:
        chat = chat_sessions.get(user_id) or model.start_chat()
        chat_sessions[user_id] = chat
        try:
            response = chat.send_message(raw_text)
            reply = (response.text or "").strip()
        except:
            reply = "⚠️ Error contacting AI model."
        last_reply = reply
        return {"reply": reply}

    return {"reply": "🤔 I'm not sure, but I'm learning!"}


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json() or {}
    message = data.get("message", "")
    user_id = session.get("user_id", str(uuid.uuid4()))
    session["user_id"] = user_id
    return jsonify(nova_response(message, user_id))


# REQUIRED BY VERCEL
def handler(event, context):
    return app(event, context)
