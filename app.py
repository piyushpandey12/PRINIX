from flask import Flask, render_template, request, jsonify, session
import os
import re
import uuid
import yt_dlp
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret")

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

chat_sessions = {}

PUNCT_STRIP = re.compile(r"[.,!?;:]+$")


def normalize(text):
    return PUNCT_STRIP.sub("", (text or "").strip().lower())


def search_youtube_audio(query):
    try:
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "noplaylist": True,
            "default_search": "ytsearch1",
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)

            if "entries" in info:
                info = info["entries"][0]

            return {
                "title": info.get("title"),
                "url": info.get("url"),
                "id": info.get("id")
            }

    except Exception as e:
        print("\nYOUTUBE ERROR:")
        print(e)
        return None


def ai_reply(message, user_id):
    try:
        if user_id not in chat_sessions:
            chat_sessions[user_id] = [
                {
                    "role": "system",
                    "content": (
                        "You are PRINIX AI Assistant.\n"
                        "Understand the user's question deeply before answering.\n"
                        "Response Rules:\n"
                        "1. If the answer can be given in one word, give one word only.\n"
                        "2. If the answer can be short, give only 1-2 concise lines.\n"
                        "3. Give detailed explanations ONLY when the user explicitly asks:\n"
                        "'explain', 'detailed', 'why', 'how', 'describe', etc.\n"
                        "4. Avoid unnecessary greetings and introductions.\n"
                        "5. Answer directly and accurately.\n"
                        "6. Use bullet points only when useful.\n"
                        "7. For factual questions, provide exact answers.\n"
                        "8. For coding questions, give optimized and correct code.\n"
                        "9. Be intelligent, concise, and professional.\n"
                        "10. Never make answers unnecessarily long."
                    )
                }
            ]

        chat_sessions[user_id].append({
            "role": "user",
            "content": message
        })

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=chat_sessions[user_id],
            temperature=0.3,
            max_tokens=700
        )

        reply = completion.choices[0].message.content.strip()

        if not reply:
            return "⚠️ Empty AI response."

        chat_sessions[user_id].append({
            "role": "assistant",
            "content": reply
        })

        return reply

    except Exception as e:
        print("\nGROQ ERROR:")
        print(type(e).__name__)
        print(e)
        return f"⚠️ AI Error: {str(e)}"


def nova_response(user_input, user_id):
    raw_text = user_input or ""
    ui = normalize(raw_text)
    words = ui.split()

    if words and words[0] in ["hi", "hello", "hey"]:
        return {
            "reply": "👋 Hello! How can I help you?"
        }

    if "who are you" in ui:
        return {
            "reply": "🤖 I am PRINIX AI Assistant."
        }

    if ui.startswith("play "):
        song = raw_text[5:]
        music = search_youtube_audio(song)

        if not music:
            return {
                "reply": "❌ Song not found."
            }

        return {
            "reply": f"🎵 Playing: {music['title']}",
            "music_url": music["url"]
        }

    reply = ai_reply(raw_text, user_id)

    return {
        "reply": reply
    }


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "reply": "❌ No data received."
            })

        message = data.get("message", "").strip()

        if not message:
            return jsonify({
                "reply": "⚠️ Please enter a message."
            })

        user_id = session.get("user_id")

        if not user_id:
            user_id = str(uuid.uuid4())
            session["user_id"] = user_id

        response = nova_response(message, user_id)

        return jsonify(response)

    except Exception as e:
        print("\nSERVER ERROR:")
        print(type(e).__name__)
        print(e)

        return jsonify({
            "reply": f"❌ Server Error: {str(e)}"
        })


if __name__ == "__main__":
    print("\n====================================")
    print(" PRINIX AI Assistant Running")
    print(" http://127.0.0.1:5000")
    print("====================================\n")

    app.run(debug=True)