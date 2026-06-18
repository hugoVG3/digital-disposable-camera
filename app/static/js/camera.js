document.addEventListener("DOMContentLoaded", () => {
  const config = window.CAMERA_CONFIG || { maxPhotos: 24, cooldownSeconds: 3, secondsUntilReady: 0 };

  const introScreen = document.getElementById("intro-screen");
  const startBtn = document.getElementById("start-btn");
  const shootingScreen = document.getElementById("shooting-screen");
  const viewfinder = document.getElementById("viewfinder");
  const liveVideo = document.getElementById("live-video");
  const placeholder = document.getElementById("viewfinder-placeholder");
  const fileInput = document.getElementById("photo-input");
  const canvas = document.getElementById("capture-canvas");
  const shutterBtn = document.getElementById("shutter-btn");
  const counterEl = document.getElementById("frame-counter");
  const statusEl = document.getElementById("status-message");
  const flashEl = document.getElementById("flash");
  const controlsEl = document.getElementById("camera-controls");

  if (!startBtn) return; // roll already finished -- nothing to wire up

  let usingLiveCamera = false;
  let mediaStream = null;
  let isBusy = false;

  function updateCounterDisplay(remaining, maxPhotos) {
    counterEl.textContent = `${remaining} / ${maxPhotos}`;
    counterEl.classList.toggle("low", remaining > 0 && remaining <= 3);
    counterEl.classList.toggle("critical", remaining === 0);
  }

  updateCounterDisplay(config.remaining, config.maxPhotos);

  // ---------- Sound + haptics (small, synthesized -- no asset files needed) ----------
  function playShutterSound() {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const now = ctx.currentTime;

      const click = ctx.createOscillator();
      const clickGain = ctx.createGain();
      click.type = "square";
      click.frequency.setValueAtTime(1200, now);
      clickGain.gain.setValueAtTime(0.15, now);
      clickGain.gain.exponentialRampToValueAtTime(0.001, now + 0.04);
      click.connect(clickGain).connect(ctx.destination);
      click.start(now);
      click.stop(now + 0.05);

      const thud = ctx.createOscillator();
      const thudGain = ctx.createGain();
      thud.type = "sine";
      thud.frequency.setValueAtTime(220, now + 0.04);
      thudGain.gain.setValueAtTime(0.12, now + 0.04);
      thudGain.gain.exponentialRampToValueAtTime(0.001, now + 0.12);
      thud.connect(thudGain).connect(ctx.destination);
      thud.start(now + 0.04);
      thud.stop(now + 0.13);

      setTimeout(() => ctx.close(), 300);
    } catch (err) {
      /* sound is a nice-to-have, never block on it */
    }
  }

  function hapticBuzz() {
    if (navigator.vibrate) {
      try { navigator.vibrate(35); } catch (err) { /* ignore */ }
    }
  }

  // ---------- Live viewfinder (best-effort; falls back gracefully) ----------
  async function tryStartLiveCamera() {
    if (!window.isSecureContext || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return false;
    }
    const attempts = [
      { video: { facingMode: { ideal: "environment" }, width: { ideal: 4096 }, height: { ideal: 4096 } }, audio: false },
      { video: { facingMode: "environment" }, audio: false },
      { video: true, audio: false },
    ];
    for (const constraints of attempts) {
      try {
        mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
        liveVideo.srcObject = mediaStream;
        await liveVideo.play().catch(() => {});
        liveVideo.classList.remove("hidden");
        placeholder.classList.add("hidden");
        return true;
      } catch (err) {
        /* try the next, less strict, constraint set */
      }
    }
    return false;
  }

  function stopLiveCamera() {
    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop());
      mediaStream = null;
    }
  }

  window.addEventListener("pagehide", stopLiveCamera);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") stopLiveCamera();
  });

  // ---------- Capturing a shot ----------
  function captureFromLiveVideo() {
    const track = mediaStream.getVideoTracks()[0];
    const settings = track && track.getSettings ? track.getSettings() : {};
    const width = settings.width || liveVideo.videoWidth || 1280;
    const height = settings.height || liveVideo.videoHeight || 720;
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(liveVideo, 0, 0, width, height);
    return new Promise((resolve) => {
      canvas.toBlob((blob) => resolve(blob), "image/jpeg", 0.95);
    });
  }

  async function handleShutterPress() {
    if (isBusy) return;

    if (usingLiveCamera) {
      isBusy = true;
      fireShotEffects();
      const blob = await captureFromLiveVideo();
      await uploadPhoto(blob, "capture.jpg");
      isBusy = false;
    } else {
      // Fallback: hand off to the phone's native camera app via the file input.
      fileInput.click();
    }
  }

  fileInput.addEventListener("change", async () => {
    if (!fileInput.files.length) return;
    isBusy = true;
    fireShotEffects();
    const file = fileInput.files[0];
    await uploadPhoto(file, file.name || "capture.jpg");
    fileInput.value = "";
    isBusy = false;
  });

  function fireShotEffects() {
    flashEl.classList.add("flash-active");
    setTimeout(() => flashEl.classList.remove("flash-active"), 220);
    playShutterSound();
    hapticBuzz();
  }

  // ---------- Upload + cooldown ----------
  async function uploadPhoto(blob, filename) {
    shutterBtn.disabled = true;
    statusEl.textContent = "Developing...";

    const formData = new FormData();
    formData.append("photo", blob, filename);

    try {
      const response = await fetch("/capture", { method: "POST", body: formData });
      const data = await response.json();

      if (data.success) {
        updateCounterDisplay(data.remaining, data.max_photos);
        statusEl.textContent = "";
        if (data.finished) {
          showFinishedState();
        } else {
          startCooldown(data.cooldown_seconds || config.cooldownSeconds);
        }
      } else if (response.status === 429 && typeof data.cooldown_remaining === "number") {
        startCooldown(data.cooldown_remaining);
      } else if (data.finished) {
        showFinishedState();
      } else {
        statusEl.textContent = data.error || "Something went wrong. Try again.";
        shutterBtn.disabled = false;
      }
    } catch (err) {
      statusEl.textContent = "Upload failed. Check your connection and try again.";
      shutterBtn.disabled = false;
    }
  }

  function startCooldown(seconds) {
    let remaining = Math.ceil(seconds);
    if (remaining <= 0) {
      shutterBtn.disabled = false;
      return;
    }
    shutterBtn.disabled = true;
    shutterBtn.classList.add("winding");
    statusEl.textContent = `Winding film... ${remaining}s`;

    const tick = setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) {
        clearInterval(tick);
        shutterBtn.disabled = false;
        shutterBtn.classList.remove("winding");
        statusEl.textContent = "";
      } else {
        statusEl.textContent = `Winding film... ${remaining}s`;
      }
    }, 1000);
  }

  function showFinishedState() {
    stopLiveCamera();
    shootingScreen.innerHTML =
      '<div class="intro-screen">' +
      '<div class="intro-icon">🎞️</div>' +
      '<h1 class="intro-title">Roll complete</h1>' +
      '<p class="intro-sub">All shots are used up. Hand the camera back to get them developed.</p>' +
      "</div>";
  }

  // ---------- Wire up the "Start shooting" splash screen ----------
  startBtn.addEventListener("click", async () => {
    introScreen.classList.add("hidden");
    shootingScreen.classList.remove("hidden");

    usingLiveCamera = await tryStartLiveCamera();

    if (config.secondsUntilReady > 0) {
      startCooldown(config.secondsUntilReady);
    }
  });

  shutterBtn.addEventListener("click", handleShutterPress);
});
