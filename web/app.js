const statusEl = document.querySelector("#scan-state");
const currentCardEl = document.querySelector("#current-card");
const settingsForm = document.querySelector("#settings-form");
const simulateForm = document.querySelector("#simulate-form");
const catalogForm = document.querySelector("#catalog-form");
const catalogMessageEl = document.querySelector("#catalog-message");
const videoEl = document.querySelector("#camera-preview");
const canvasEl = document.querySelector("#camera-canvas");
const cameraMessageEl = document.querySelector("#camera-message");
let cameraStream;

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

document.querySelector("#start-camera-button").addEventListener("click", async () => {
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });
    videoEl.srcObject = cameraStream;
    await videoEl.play();
    cameraMessageEl.textContent = "Camera ready.";
  } catch (error) {
    cameraMessageEl.textContent = `Camera unavailable: ${error.message}`;
  }
});

document.querySelector("#scan-frame-button").addEventListener("click", async () => {
  if (!cameraStream) {
    cameraMessageEl.textContent = "Start the camera first.";
    return;
  }
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
  }
  renderStatus({ scan: payload.scan });
});

refresh();
setInterval(refresh, 1500);
