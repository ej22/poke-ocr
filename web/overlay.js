const cardEl = document.querySelector("#overlay-card");
const stateEl = document.querySelector("#overlay-state");
const nameEl = document.querySelector("#overlay-name");
const metaEl = document.querySelector("#overlay-meta");
const priceEl = document.querySelector("#overlay-price");
const sourceEl = document.querySelector("#overlay-source");

function money(price) {
  if (!price || price.market == null) return "--";
  return `${price.currency} ${Number(price.market).toFixed(2)}`;
}

function render(payload) {
  const scan = payload.scan;
  const settings = payload.settings;
  const identity = scan.identity;
  const candidate = scan.candidate;
  cardEl.className = `overlay-card ${settings.overlay_layout || "lower-third"}`;
  stateEl.textContent = scan.state.replace("_", " ");
  if (identity) {
    nameEl.textContent = identity.name;
    metaEl.textContent = `${identity.set_name} | ${identity.collector_number} | ${identity.language.toUpperCase()} | ${
      Math.round((candidate?.confidence || 0) * 100)
    }%`;
    priceEl.textContent = money(scan.price);
    sourceEl.textContent = scan.price ? `${scan.price.provider} ${scan.price.cache_status}` : scan.message;
  } else if (candidate) {
    nameEl.textContent = candidate.name || "Checking card";
    metaEl.textContent = `${candidate.collector_number || "No number"} | ${scan.message || "Identifying"}`;
    priceEl.textContent = "--";
    sourceEl.textContent = "waiting";
  } else {
    nameEl.textContent = "No card detected";
    metaEl.textContent = scan.message || "Hold a card in view";
    priceEl.textContent = "--";
    sourceEl.textContent = "ready";
  }
}

async function refresh() {
  const response = await fetch("/api/status");
  render(await response.json());
}

refresh();
setInterval(refresh, 1000);
