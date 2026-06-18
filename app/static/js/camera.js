document.addEventListener("DOMContentLoaded", () => {
  const config = window.CAMERA_CONFIG || { maxPhotos: 24, cooldownSeconds: 3, secondsUntilReady: 0, remaining: 24 };

  const introScreen      = document.getElementById("intro-screen");
  const startBtn         = document.getElementById("start-btn");
  const shootingScreen   = document.getElementById("shooting-screen");
  const liveVideo        = document.getElementById("live-video");
  const placeholder      = document.getElementById("viewfinder-placeholder");
  const cameraLoading    = document.getElementById("camera-loading");
  const developingOverlay= document.getElementById("developing-overlay");
  const fileInput        = document.getElementById("photo-input");
  const canvas           = document.getElementById("capture-canvas");
  const shutterBtn       = document.getElementById("shutter-btn");
  const counterEl        = document.getElementById("frame-counter");
  const statusEl         = document.getElementById("status-message");
  const flashEl          = document.getElementById("flash");
  const flashToggle      = document.getElementById("flash-toggle");
  const flashIcon        = document.getElementById("flash-icon");
  const toastEl          = document.getElementById("toast");

  if (!startBtn) return; // roll already finished

  let usingLiveCamera = false;
  let mediaStream      = null;
  let isBusy           = false;
  let flashEnabled     = true;   // on by default, just like a real disposable
  let wakeLock         = null;
  let toastTimer       = null;

  // ── Counter display ──────────────────────────────────────────────
  function updateCounter(remaining, max) {
    counterEl.textContent = `${remaining} / ${max}`;
    counterEl.classList.toggle("low",      remaining > 0 && remaining <= 3);
    counterEl.classList.toggle("critical", remaining === 0);
  }
  updateCounter(config.remaining, config.maxPhotos);

  // ── Flash toggle ─────────────────────────────────────────────────
  flashToggle.addEventListener("click", () => {
    flashEnabled = !flashEnabled;
    flashIcon.textContent  = flashEnabled ? "⚡" : "⚡";
    flashToggle.classList.toggle("flash-off", !flashEnabled);
    flashToggle.title = flashEnabled ? "Flash activado" : "Flash desactivado";
    showToast(flashEnabled ? "Flash activado" : "Flash desactivado");
  });

  // ── Toast ─────────────────────────────────────────────────────────
  function showToast(msg, duration = 1800) {
    if (toastTimer) clearTimeout(toastTimer);
    toastEl.textContent = msg;
    toastEl.classList.remove("hidden");
    toastTimer = setTimeout(() => toastEl.classList.add("hidden"), duration);
  }

  // ── Sound (synthesised, no files) ────────────────────────────────
  function playShutterSound() {
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      const ctx = new Ctx();
      const now = ctx.currentTime;

      const click = ctx.createOscillator();
      const cGain = ctx.createGain();
      click.type = "square";
      click.frequency.setValueAtTime(1100, now);
      cGain.gain.setValueAtTime(0.14, now);
      cGain.gain.exponentialRampToValueAtTime(0.001, now + 0.04);
      click.connect(cGain).connect(ctx.destination);
      click.start(now); click.stop(now + 0.05);

      const thud = ctx.createOscillator();
      const tGain = ctx.createGain();
      thud.type = "sine";
      thud.frequency.setValueAtTime(200, now + 0.04);
      tGain.gain.setValueAtTime(0.11, now + 0.04);
      tGain.gain.exponentialRampToValueAtTime(0.001, now + 0.13);
      thud.connect(tGain).connect(ctx.destination);
      thud.start(now + 0.04); thud.stop(now + 0.14);

      setTimeout(() => ctx.close(), 400);
    } catch (_) {}
  }

  function hapticBuzz() {
    try { navigator.vibrate && navigator.vibrate(30); } catch (_) {}
  }

  // ── Screen wake lock (keep screen on while shooting) ─────────────
  async function requestWakeLock() {
    try {
      if ("wakeLock" in navigator) {
        wakeLock = await navigator.wakeLock.request("screen");
      }
    } catch (_) {}
  }

  document.addEventListener("visibilitychange", async () => {
    if (document.visibilityState === "visible" && usingLiveCamera) {
      await requestWakeLock();
    }
    if (document.visibilityState === "hidden") {
      stopLiveCamera();
    }
  });
  window.addEventListener("pagehide", stopLiveCamera);

  // ── Live camera ───────────────────────────────────────────────────
  async function tryStartLiveCamera() {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
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
        cameraLoading.classList.add("hidden");
        placeholder.classList.add("hidden");
        return true;
      } catch (_) {}
    }
    return false;
  }

  function stopLiveCamera() {
    mediaStream?.getTracks().forEach(t => t.stop());
    mediaStream = null;
  }

  // ── Capture from live video ───────────────────────────────────────
  function captureFromLiveVideo() {
    const track    = mediaStream.getVideoTracks()[0];
    const settings = track?.getSettings?.() ?? {};
    const w = settings.width  || liveVideo.videoWidth  || 1280;
    const h = settings.height || liveVideo.videoHeight || 720;
    canvas.width  = w;
    canvas.height = h;
    canvas.getContext("2d").drawImage(liveVideo, 0, 0, w, h);
    return new Promise(res => canvas.toBlob(blob => res(blob), "image/jpeg", 0.95));
  }

  // ── Shot effects ──────────────────────────────────────────────────
  function fireShotEffects() {
    if (flashEnabled) {
      flashEl.classList.add("flash-active");
      setTimeout(() => flashEl.classList.remove("flash-active"), 200);
    }
    playShutterSound();
    hapticBuzz();
  }

  // ── Shutter press ─────────────────────────────────────────────────
  async function handleShutterPress() {
    if (isBusy || shutterBtn.disabled) return;
    if (usingLiveCamera) {
      isBusy = true;
      fireShotEffects();
      const blob = await captureFromLiveVideo();
      await uploadPhoto(blob, "capture.jpg");
      isBusy = false;
    } else {
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

  shutterBtn.addEventListener("click", handleShutterPress);

  // ── Upload ────────────────────────────────────────────────────────
  async function uploadPhoto(blob, filename) {
    shutterBtn.disabled = true;
    statusEl.textContent = "";
    developingOverlay.classList.remove("hidden");

    const fd = new FormData();
    fd.append("photo", blob, filename);

    try {
      const res  = await fetch("/capture", { method: "POST", body: fd });
      const data = await res.json();

      developingOverlay.classList.add("hidden");

      if (data.success) {
        updateCounter(data.remaining, data.max_photos);
        if (data.finished) {
          showFinishedState();
        } else {
          if (data.remaining === 1) showToast("¡Última foto!", 2500);
          startCooldown(data.cooldown_seconds ?? config.cooldownSeconds);
        }
      } else if (res.status === 429 && typeof data.cooldown_remaining === "number") {
        startCooldown(data.cooldown_remaining);
      } else if (data.finished) {
        showFinishedState();
      } else {
        statusEl.textContent = data.error || "Algo salió mal. Inténtalo de nuevo.";
        shutterBtn.disabled = false;
      }
    } catch (_) {
      developingOverlay.classList.add("hidden");
      statusEl.textContent = "Error de conexión. Comprueba tu red e inténtalo de nuevo.";
      shutterBtn.disabled = false;
    }
  }

  // ── Cooldown (winding film) ───────────────────────────────────────
  function startCooldown(seconds) {
    let rem = Math.ceil(seconds);
    if (rem <= 0) { shutterBtn.disabled = false; return; }

    shutterBtn.disabled = true;
    shutterBtn.classList.add("winding");
    statusEl.textContent = `Enrollando el carrete... ${rem}s`;

    const tick = setInterval(() => {
      rem -= 1;
      if (rem <= 0) {
        clearInterval(tick);
        shutterBtn.disabled = false;
        shutterBtn.classList.remove("winding");
        statusEl.textContent = "";
      } else {
        statusEl.textContent = `Enrollando el carrete... ${rem}s`;
      }
    }, 1000);
  }

  // ── Finished state ────────────────────────────────────────────────
  function showFinishedState() {
    stopLiveCamera();
    shootingScreen.innerHTML =
      '<div class="intro-screen">' +
        '<div class="intro-icon">🎞️</div>' +
        '<h1 class="intro-title">¡Carrete completo!</h1>' +
        '<p class="intro-sub">Has usado todas las fotos. ' +
        'Devuelve la cámara para que podamos revelarlas — ¡pronto las verás todas!</p>' +
      '</div>';
  }

  // ── Start button ──────────────────────────────────────────────────
  startBtn.addEventListener("click", async () => {
    introScreen.classList.add("hidden");
    shootingScreen.classList.remove("hidden");

    // show loading state while getUserMedia negotiates
    cameraLoading.classList.remove("hidden");

    usingLiveCamera = await tryStartLiveCamera();

    if (!usingLiveCamera) {
      cameraLoading.classList.add("hidden");
      placeholder.classList.remove("hidden");
    }

    await requestWakeLock();

    // enable shutter (was disabled until camera is ready)
    shutterBtn.disabled = false;

    if (config.secondsUntilReady > 0) {
      startCooldown(config.secondsUntilReady);
    }
  });
});
