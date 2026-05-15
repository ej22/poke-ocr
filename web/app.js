const statusEl = document.querySelector("#scan-state");
const currentCardEl = document.querySelector("#current-card");
const settingsForm = document.querySelector("#settings-form");
const simulateForm = document.querySelector("#simulate-form");

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

refresh();
setInterval(refresh, 1500);
