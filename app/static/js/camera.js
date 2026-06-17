document.addEventListener("DOMContentLoaded", () => {
  const shutterBtn = document.getElementById("shutter-btn");
  const fileInput = document.getElementById("photo-input");
  const counterEl = document.getElementById("frame-counter");
  const statusEl = document.getElementById("status-message");
  const flashEl = document.getElementById("flash");
  const controlsEl = document.getElementById("camera-controls");

  if (!shutterBtn || !fileInput) return; // roll already finished, nothing to wire up

  shutterBtn.addEventListener("click", () => fileInput.click());

  fileInput.addEventListener("change", async () => {
    if (!fileInput.files.length) return;

    shutterBtn.disabled = true;
    statusEl.textContent = "";
    flashEl.classList.add("flash-active");

    const formData = new FormData();
    formData.append("photo", fileInput.files[0]);

    try {
      const response = await fetch("/capture", { method: "POST", body: formData });
      const data = await response.json();

      if (data.success) {
        counterEl.textContent = `${data.remaining} / ${data.max_photos}`;
        if (data.finished) {
          controlsEl.innerHTML =
            '<p class="finished-msg">Roll complete! Hand the camera back to get your photos developed.</p>';
        }
      } else {
        statusEl.textContent = data.error || "Something went wrong. Try again.";
      }
    } catch (err) {
      statusEl.textContent = "Upload failed. Check your connection and try again.";
    } finally {
      fileInput.value = "";
      if (shutterBtn) shutterBtn.disabled = false;
      setTimeout(() => flashEl.classList.remove("flash-active"), 250);
    }
  });
});
