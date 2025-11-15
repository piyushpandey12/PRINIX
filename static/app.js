const chatArea = document.getElementById("chatArea");
const userInput = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");
const micBtn = document.getElementById("micBtn");
const locationBtn = document.getElementById("locationBtn");

const popularSites = {
  youtube: "https://www.youtube.com",
  google: "https://www.google.com",
  gmail: "https://mail.google.com",
  facebook: "https://www.facebook.com",
  twitter: "https://www.twitter.com",
  whatsapp: "https://web.whatsapp.com",
  insta: "https://www.instagram.com",
  instagram: "https://www.instagram.com"
};

function normalizeTarget(t) {
  return (t || "").trim().toLowerCase().replace(/[.,!?;:]+$/g, "");
}

function speak(text, lang = "en-US") {
  if (!text || !window.speechSynthesis) return;
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = lang;
  window.speechSynthesis.speak(utter);
}

function addMessage(text, type = "bot") {
  if (!text) return;
  const bubble = document.createElement("div");
  bubble.className = type === "user" ? "bubble user" : "bubble bot";
  bubble.innerHTML = text;
  chatArea.appendChild(bubble);
  chatArea.scrollTo({ top: chatArea.scrollHeight, behavior: "smooth" });
}

let currentAudio = null;
let playlist = [];
let currentIndex = -1;

let audioCtx, analyser, source, dataArray, bufferLength, animationId;

function setupVisualizer(audio) {
  const canvas = document.getElementById("audioVisualizer");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const core = document.querySelector(".jarvis-core");
  const noMusicMsg = document.getElementById("noMusicMsg");
  if (noMusicMsg) noMusicMsg.style.display = "none";

  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  analyser = audioCtx.createAnalyser();
  source = audioCtx.createMediaElementSource(audio);
  source.connect(analyser);
  analyser.connect(audioCtx.destination);
  analyser.fftSize = 128;

  bufferLength = analyser.frequencyBinCount;
  dataArray = new Uint8Array(bufferLength);

  function draw() {
    animationId = requestAnimationFrame(draw);
    analyser.getByteFrequencyData(dataArray);
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const barWidth = (canvas.width / bufferLength) * 1.5;
    let x = 0;
    let avg = 0;

    for (let i = 0; i < bufferLength; i++) {
      avg += dataArray[i];
      const barHeight = dataArray[i] * 0.7;
      const gradient = ctx.createLinearGradient(0, canvas.height, 0, canvas.height - barHeight);
      gradient.addColorStop(0, "#00ffff");
      gradient.addColorStop(0.5, "#6a5acd");
      gradient.addColorStop(1, "#ff1493");

      ctx.fillStyle = gradient;
      ctx.shadowBlur = 15;
      ctx.shadowColor = "#00ffff";
      ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);
      x += barWidth + 1;
    }

    avg = avg / bufferLength;
    if (core) {
      const scale = 1 + avg / 500;
      core.style.transform = `scale(${scale})`;
      core.style.boxShadow = `0 0 ${avg / 3}px #00ffff`;
    }
  }
  draw();
}

function stopVisualizer() {
  if (animationId) cancelAnimationFrame(animationId);
  const canvas = document.getElementById("audioVisualizer");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const core = document.querySelector(".jarvis-core");
  if (core) core.style.transform = "scale(1)";
  const msg = document.getElementById("noMusicMsg");
  if (msg) msg.style.display = "block";
}

function fadeOutAudio(audio, callback) {
  if (!audio) return callback?.();
  let volume = audio.volume;
  const fade = setInterval(() => {
    volume -= 0.05;
    if (volume <= 0) {
      clearInterval(fade);
      audio.pause();
      audio.currentTime = 0;
      audio.volume = 1.0;
      if (callback) callback();
    } else audio.volume = volume;
  }, 100);
}

function playSongAt(index) {
  if (index < 0 || index >= playlist.length) return;

  if (currentAudio) {
    currentAudio.pause();
    currentAudio.currentTime = 0;
    stopVisualizer();
  }

  const track = playlist[index];
  currentAudio = new Audio(track.url);

  currentAudio.onended = () => {
    fadeOutAudio(currentAudio, () => {
      stopVisualizer();
      addMessage("✅ Song finished playing.", "bot");
      speak("Song finished playing.");
      currentAudio = null;
      currentIndex = -1;
    });
  };

  currentAudio.play()
    .then(() => {
      setupVisualizer(currentAudio);
    })
    .catch(err => addMessage("❌ Could not play audio: " + err, "bot"));

  currentIndex = index;
}

async function askJarvis(message) {
  addMessage(message, "user");
  userInput.value = "";
  const lower = normalizeTarget(message);

  if (lower === "stop" || lower === "pause") {
    if (currentAudio && !currentAudio.paused) {
      fadeOutAudio(currentAudio, () => {
        stopVisualizer();
        addMessage("⏸️ Music stopped.", "bot");
        speak("Music stopped");
      });
    } else addMessage("⚠️ No music playing.", "bot");
    return;
  }

  if (lower === "resume" || lower === "play") {
    if (currentAudio && currentAudio.paused) {
      currentAudio.play();
      setupVisualizer(currentAudio);
      addMessage("▶️ Music resumed.", "bot");
      speak("Music resumed");
    } else addMessage("⚠️ Nothing to resume.", "bot");
    return;
  }

  if (lower === "next") { playSongAt(currentIndex + 1); speak("Next song"); return; }
  if (lower === "previous" || lower === "back") { playSongAt(currentIndex - 1); speak("Previous song"); return; }

  if (lower.startsWith("open ")) {
    const target = normalizeTarget(message.slice(5));
    if (popularSites[target]) {
      window.open(popularSites[target], "_blank", "noopener");
      addMessage(`🌐 Opening ${target}`, "bot");
      speak(`Opening ${target}`);
      return;
    }
  }

  try {
    const res = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message })
    });
    const data = await res.json();
    const reply = data.reply || "⚠️ Empty reply.";

    if (data.music_url) {
      addMessage(reply, "bot");
      playlist = [{ title: reply.replace("🎵", "").trim(), url: data.music_url }];
      playSongAt(0);
    } else {
      addMessage(reply, "bot");
    }
  } catch (err) {
    addMessage("❌ Error connecting to server.", "bot");
  }
}

sendBtn?.addEventListener("click", () => {
  const text = userInput.value.trim();
  if (text) askJarvis(text);
});

userInput?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    sendBtn.click();
  }
});

micBtn?.addEventListener("click", () => {
  const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Rec) {
    addMessage("❌ Speech recognition not supported.", "bot");
    return;
  }

  const recognition = new Rec();
  recognition.lang = "en-US";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.start();
  recognition.onresult = (e) => askJarvis(e.results[0][0].transcript);
  recognition.onspeechend = () => recognition.stop();
  recognition.onerror = (e) => {
    let msg = "❌ Voice input error.";
    if (e.error === "no-speech") msg = "🎤 No speech detected.";
    if (e.error === "not-allowed") msg = "🚫 Mic access denied.";
    addMessage(msg, "bot");
  };
});

locationBtn?.addEventListener("click", () => {
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      pos => {
        const lat = pos.coords.latitude, lon = pos.coords.longitude;
        window.open(`https://www.google.com/maps?q=${lat},${lon}`, "_blank");
      },
      err => addMessage("❌ Location error: " + err.message, "bot")
    );
  } else {
    addMessage("❌ Geolocation not supported.", "bot");
  }
});

const greetingText = (() => {
  const h = new Date().getHours();
  if (h < 12) return "Good Morning!";
  if (h < 17) return "Good Afternoon!";
  if (h < 21) return "Good Evening!";
  return "Good Night!";
})();
addMessage(greetingText, "bot");
speak(greetingText);
