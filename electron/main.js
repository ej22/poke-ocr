const { app, BrowserWindow, shell } = require("electron");
const { spawn } = require("node:child_process");
const path = require("node:path");

let serviceProcess;

function startService() {
  const python = process.env.CODEXOCR_PYTHON || "python3";
  serviceProcess = spawn(python, ["-m", "codexocr.server"], {
    cwd: path.resolve(__dirname, ".."),
    env: { ...process.env, CODEXOCR_HOST: "127.0.0.1", CODEXOCR_PORT: "8765" },
    stdio: "inherit",
  });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1180,
    height: 760,
    title: "CodexOCR Pokémon Overlay",
    webPreferences: {
      contextIsolation: true,
      sandbox: true,
    },
  });

  win.loadURL("http://127.0.0.1:8765/control");
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

app.whenReady().then(() => {
  startService();
  setTimeout(createWindow, 700);
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  if (serviceProcess) {
    serviceProcess.kill();
  }
});
