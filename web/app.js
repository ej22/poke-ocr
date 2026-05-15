const statusEl = document.querySelector("#scan-state");
const currentCardEl = document.querySelector("#current-card");
const settingsForm = document.querySelector("#settings-form");
const simulateForm = document.querySelector("#simulate-form");
const catalogForm = document.querySelector("#catalog-form");
const catalogMessageEl = document.querySelector("#catalog-message");
const videoEl = document.querySelector("#camera-preview");
const canvasEl = document.querySelector("#camera-canvas");
const cameraMessageEl = document.querySelector("#camera-message");
const startCameraButton = document.querySelector("#start-camera-button");
const scanFrameButton = document.querySelector("#scan-frame-button");
const startAutoScanButton = document.querySelector("#start-auto-scan-button");
const stopAutoScanButton = document.querySelector("#stop-auto-scan-button");
const scanIntervalInput = document.querySelector("#scan-interval-input");
const obsConfigEl = document.querySelector("#obs-config");
let cameraStream;
let autoScanTimer;
let autoScanRunning = false;
let frameUploadInProgress = false;

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  return response.json();
}

function readForm(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function renderStatus(payload) {
  const scan = payload.scan;
  statusEl.textContent = scan.state.replace("_", " ");
  const identity = scan.identity;
  const candidate = scan.candidate;
  const price = scan.price;
  if (identity) {
    currentCardEl.textContent = `${identity.name} | ${identity.set_name} ${identity.collector_number} | ${
      price?.market ? `${price.currency} ${price.market.toFixed(2)}` : scan.message
    }`;
  } else if (candidate) {
    currentCardEl.textContent = `${candidate.name || "Unknown card"} | ${candidate.collector_number || "No number"} | ${
      scan.message
    }`;
  } else {
    currentCardEl.textContent = scan.message || "Waiting for a card.";
  }
}

async function refresh() {
  renderStatus(await request("/api/status"));
}

async function loadObsConfig() {
  const payload = await request("/api/obs/source-config");
  const config = payload.browser_source;
  document.querySelector("#overlay-url").value = config.url;
  document.querySelector("#overlay-preview-link").href = config.url;
  obsConfigEl.textContent = JSON.stringify(config, null, 2);
}

function clampScanInterval(value) {
  const interval = Number.parseInt(value, 10);
  if (Number.isNaN(interval)) {
    return 2500;
  }
  return Math.min(10000, Math.max(750, interval));
}

async function startCamera() {
  if (cameraStream) {
    return true;
  }
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });
    videoEl.srcObject = cameraStream;
    await videoEl.play();
    cameraMessageEl.textContent = "Camera ready.";
    return true;
  } catch (error) {
    cameraMessageEl.textContent = `Camera unavailable: ${error.message}`;
    return false;
  }
}

function stopAutoScan() {
  if (autoScanTimer) {
    clearInterval(autoScanTimer);
    autoScanTimer = undefined;
  }
  autoScanRunning = false;
  scanFrameButton.disabled = false;
  startAutoScanButton.disabled = false;
  stopAutoScanButton.disabled = true;
}

function stopCamera() {
  stopAutoScan();
  if (cameraStream) {
    cameraStream.getTracks().forEach((track) => track.stop());
    cameraStream = undefined;
    videoEl.srcObject = null;
  }
}

async function captureAndScanFrame({ automatic = false } = {}) {
  if (!cameraStream) {
    cameraMessageEl.textContent = "Start the camera first.";
    return;
  }
  if (frameUploadInProgress) {
    return;
  }
  frameUploadInProgress = true;
  try {
    canvasEl.width = videoEl.videoWidth || 1280;
    canvasEl.height = videoEl.videoHeight || 720;
    canvasEl.getContext("2d").drawImage(videoEl, 0, 0, canvasEl.width, canvasEl.height);
    const image = canvasEl.toDataURL("image/jpeg", 0.82);
    const payload = await request("/api/scan/frame", {
      method: "POST",
      body: JSON.stringify({ image }),
    });
    if (payload.error) {
      cameraMessageEl.textContent = payload.error;
      if (automatic) {
        stopAutoScan();
      }
    } else {
      cameraMessageEl.textContent = automatic ? "Auto scan is running." : "Frame scanned.";
    }
    renderStatus({ scan: payload.scan });
  } catch (error) {
    cameraMessageEl.textContent = `Scan failed: ${error.message}`;
    if (automatic) {
      stopAutoScan();
    }
  } finally {
    frameUploadInProgress = false;
  }
}

settingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = readForm(settingsForm);
  if (!data.pokewallet_api_key) {
    delete data.pokewallet_api_key;
  }
  await request("/api/settings", { method: "POST", body: JSON.stringify(data) });
  await refresh();
});

simulateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  for (let index = 0; index < 3; index += 1) {
    await request("/api/scan/simulate", {
      method: "POST",
      body: JSON.stringify({ ...readForm(simulateForm), confidence: 0.95, source: "manual" }),
    });
  }
  await refresh();
});

document.querySelector("#pause-button").addEventListener("click", async () => {
  await request("/api/scan/pause", { method: "POST", body: "{}" });
  await refresh();
});

document.querySelector("#resume-button").addEventListener("click", async () => {
  await request("/api/scan/resume", { method: "POST", body: "{}" });
  await refresh();
});

catalogForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  catalogMessageEl.textContent = "Syncing card index...";
  const payload = await request("/api/cards/sync", {
    method: "POST",
    body: JSON.stringify(readForm(catalogForm)),
  });
  catalogMessageEl.textContent = payload.ok
    ? `Imported ${payload.imported} cards from ${payload.pages} page(s).`
    : payload.error;
  await refresh();
});

startCameraButton.addEventListener("click", async () => {
  await startCamera();
});

scanFrameButton.addEventListener("click", async () => {
  await captureAndScanFrame();
});

startAutoScanButton.addEventListener("click", async () => {
  if (autoScanRunning) {
    return;
  }
  const ready = await startCamera();
  if (!ready) {
    return;
  }
  const interval = clampScanInterval(scanIntervalInput.value);
  scanIntervalInput.value = interval;
  autoScanRunning = true;
  scanFrameButton.disabled = true;
  startAutoScanButton.disabled = true;
  stopAutoScanButton.disabled = false;
  cameraMessageEl.textContent = "Auto scan is running.";
  await captureAndScanFrame({ automatic: true });
  if (!autoScanRunning) {
    return;
  }
  autoScanTimer = setInterval(() => {
    captureAndScanFrame({ automatic: true });
  }, interval);
});

stopAutoScanButton.addEventListener("click", stopAutoScan);
window.addEventListener("beforeunload", stopCamera);

refresh();
loadObsConfig();
setInterval(refresh, 1500);
