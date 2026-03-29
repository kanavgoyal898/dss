/**
 * Purpose: DSS Electron main process — production-ready one-click launcher.
 * Responsibilities:
 *   - Verify Python 3 is available and install/upgrade Python dependencies silently.
 *   - Present a welcome dialog for Admin vs User mode selection.
 *   - For User Mode: show a styled coordinator-URL input window with persistence.
 *   - Auto-allocate free ports; never conflict with existing services.
 *   - Spawn and supervise FastAPI backend processes.
 *   - Show a loading splash while backends warm up.
 *   - Cleanly kill all child processes on exit.
 * Dependencies: electron, child_process, net, path, fs, os
 */

const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");
const { spawn, execFile, execFileSync } = require("child_process");
const net = require("net");
const path = require("path");
const fs = require("fs");
const os = require("os");

const IS_WIN = process.platform === "win32";
const IS_MAC = process.platform === "darwin";
const UI_URL = "http://localhost:3000";
const PREFS_FILE = path.join(app.getPath("userData"), "dss-prefs.json");

let mainWindow = null;
let splashWindow = null;
const childProcesses = [];

function loadPrefs() {
  try {
    return JSON.parse(fs.readFileSync(PREFS_FILE, "utf8"));
  } catch {
    return {};
  }
}

function savePrefs(data) {
  try {
    fs.mkdirSync(path.dirname(PREFS_FILE), { recursive: true });
    const existing = loadPrefs();
    fs.writeFileSync(PREFS_FILE, JSON.stringify({ ...existing, ...data }, null, 2));
  } catch {}
}

function findPython() {
  const candidates = IS_WIN
    ? ["python", "python3", "py"]
    : ["python3", "python"];
  for (const cmd of candidates) {
    try {
      const out = execFileSync(cmd, ["--version"], { timeout: 5000, stdio: "pipe" }).toString();
      if (/Python 3\.\d+/.test(out)) return cmd;
    } catch {}
  }
  return null;
}

function installDependencies(pythonCmd, dssRoot) {
  return new Promise((resolve, reject) => {
    const reqFile = path.join(dssRoot, "requirements.txt");
    const args = ["-m", "pip", "install", "--quiet", "--disable-pip-version-check"];
    if (fs.existsSync(reqFile)) {
      args.push("-r", reqFile);
    } else {
      args.push(
        "fastapi>=0.111.0",
        "uvicorn[standard]>=0.30.1",
        "httpx>=0.27.0",
        "pydantic>=2.7.4",
        "pydantic-settings>=2.3.1",
        "cryptography>=42.0.8",
        "python-jose[cryptography]>=3.3.0",
        "python-multipart>=0.0.9"
      );
    }
    const proc = spawn(pythonCmd, args, { stdio: ["ignore", "pipe", "pipe"] });
    proc.on("close", (code) => (code === 0 ? resolve() : reject(new Error(`pip exited ${code}`))));
    proc.on("error", reject);
  });
}

async function findFreePort(preferred) {
  return new Promise((resolve) => {
    const s = net.createServer();
    s.listen(preferred, "127.0.0.1", () => {
      const { port } = s.address();
      s.close(() => resolve(port));
    });
    s.on("error", () => {
      const s2 = net.createServer();
      s2.listen(0, "127.0.0.1", () => {
        const { port } = s2.address();
        s2.close(() => resolve(port));
      });
    });
  });
}

function spawnPython(pythonCmd, dssRoot, module, env) {
  const projectParent = path.dirname(dssRoot);
  const proc = spawn(pythonCmd, ["-m", module], {
    cwd: projectParent,
    env: {
      ...process.env,
      PYTHONPATH: process.env.PYTHONPATH
        ? `${projectParent}${path.delimiter}${process.env.PYTHONPATH}`
        : projectParent,
      ...env,
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  childProcesses.push(proc);
  proc.stdout.on("data", (d) => process.stdout.write(`[${module}] ${d}`));
  proc.stderr.on("data", (d) => process.stderr.write(`[${module}] ${d}`));
  proc.on("exit", (code) => {
    if (code !== 0 && code !== null && !app.isQuitting) {
      dialog.showErrorBox(
        "DSS — Service Stopped",
        `A background service stopped unexpectedly (code ${code}).\nPlease restart DSS.`
      );
    }
  });
  return proc;
}

function waitForPort(port, retries = 60, delay = 800) {
  return new Promise((resolve, reject) => {
    let n = 0;
    function attempt() {
      const s = net.createConnection({ port, host: "127.0.0.1" });
      s.on("connect", () => { s.destroy(); resolve(); });
      s.on("error", () => {
        s.destroy();
        if (++n >= retries) { reject(new Error(`DSS: port ${port} never opened`)); return; }
        setTimeout(attempt, delay);
      });
    }
    attempt();
  });
}

function createSplash(message) {
  splashWindow = new BrowserWindow({
    width: 400,
    height: 200,
    frame: false,
    resizable: false,
    center: true,
    alwaysOnTop: true,
    backgroundColor: "#ffffff",
    webPreferences: { nodeIntegration: false, contextIsolation: true },
  });
  splashWindow.loadURL(
    "data:text/html," +
      encodeURIComponent(`
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        * { margin:0; padding:0; box-sizing:border-box; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
        body { display:flex; flex-direction:column; align-items:center; justify-content:center;
               height:100vh; background:#fff; color:#0a0a0a; }
        h1 { font-size:22px; font-weight:700; letter-spacing:-0.5px; }
        p { font-size:13px; color:#666; margin-top:10px; }
        .dot { display:inline-block; width:6px; height:6px; border-radius:50%;
               background:#0a0a0a; margin:0 2px; animation:bounce 1.2s infinite; }
        .dot:nth-child(2) { animation-delay:0.2s; }
        .dot:nth-child(3) { animation-delay:0.4s; }
        @keyframes bounce { 0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-6px)} }
        .dots { margin-top:20px; }
      </style>
    </head>
    <body>
      <h1>DSS</h1>
      <p>${message}</p>
      <div class="dots">
        <span class="dot"></span><span class="dot"></span><span class="dot"></span>
      </div>
    </body>
    </html>
  `)
  );
}

function closeSplash() {
  if (splashWindow && !splashWindow.isDestroyed()) {
    splashWindow.close();
    splashWindow = null;
  }
}

function createMainWindow(route) {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 900,
    minHeight: 600,
    title: "DSS",
    show: false,
    backgroundColor: "#ffffff",
    webPreferences: { nodeIntegration: false, contextIsolation: true },
  });
  mainWindow.loadURL(`${UI_URL}${route}`);
  mainWindow.once("ready-to-show", () => {
    closeSplash();
    mainWindow.show();
  });
  mainWindow.on("closed", () => { mainWindow = null; });
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

function promptCoordinatorUrl(savedUrl) {
  return new Promise((resolve, reject) => {
    const win = new BrowserWindow({
      width: 500,
      height: 300,
      title: "DSS — Join Network",
      resizable: false,
      minimizable: false,
      center: true,
      webPreferences: { nodeIntegration: true, contextIsolation: false },
    });
    const escaped = (savedUrl || "http://localhost:8000").replace(/"/g, "&quot;");
    win.loadURL(
      "data:text/html," +
        encodeURIComponent(`
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <style>
          *{box-sizing:border-box;margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,sans-serif}
          body{padding:32px 36px;background:#fff;color:#0a0a0a}
          h2{font-size:16px;font-weight:600;margin-bottom:8px}
          .sub{font-size:12px;color:#555;line-height:1.6;margin-bottom:22px}
          label{font-size:12px;font-weight:500;display:block;margin-bottom:6px}
          input{width:100%;padding:9px 12px;border:1.5px solid #d4d4d4;border-radius:7px;
                font-size:13px;font-family:monospace;outline:none;transition:border-color 0.15s}
          input:focus{border-color:#0a0a0a}
          .err{font-size:11px;color:#dc2626;margin-top:5px;min-height:16px}
          .row{display:flex;gap:8px;margin-top:20px;justify-content:flex-end}
          button{padding:9px 20px;border-radius:7px;border:1.5px solid #d4d4d4;font-size:13px;
                 cursor:pointer;background:#fff;font-weight:500;transition:opacity 0.15s}
          button.primary{background:#0a0a0a;color:#fff;border-color:#0a0a0a}
          button:hover{opacity:0.82}
          button:disabled{opacity:0.45;cursor:not-allowed}
        </style>
      </head>
      <body>
        <h2>Join DSS Network</h2>
        <p class="sub">Enter the address of the DSS Coordinator that the admin gave you.<br>
          It looks like <strong>http://192.168.1.10:8000</strong> or similar.</p>
        <label for="url">Coordinator Address</label>
        <input id="url" type="text" value="${escaped}" placeholder="http://192.168.1.10:8000" autofocus />
        <div class="err" id="err"></div>
        <div class="row">
          <button onclick="cancel()">Cancel</button>
          <button class="primary" id="btn" onclick="connect()">Connect</button>
        </div>
        <script>
          const { ipcRenderer } = require('electron');
          const input = document.getElementById('url');
          const err = document.getElementById('err');
          const btn = document.getElementById('btn');
          input.addEventListener('keydown', (e)=>{
            if(e.key==='Enter') connect();
            if(e.key==='Escape') cancel();
          });
          function validate(v) {
            if (!v) return 'Please enter an address.';
            if (!v.startsWith('http://') && !v.startsWith('https://'))
              return 'Address must start with http:// or https://';
            return '';
          }
          function connect() {
            const val = input.value.trim();
            const msg = validate(val);
            if (msg) { err.textContent = msg; return; }
            btn.disabled = true;
            btn.textContent = 'Connecting…';
            ipcRenderer.send('coordinator-url', val);
          }
          function cancel() { ipcRenderer.send('coordinator-url', null); }
        </script>
      </body>
      </html>
    `)
    );
    win.on("closed", () => reject(new Error("cancelled")));
    ipcMain.once("coordinator-url", (_, url) => {
      win.destroy();
      if (url) resolve(url);
      else reject(new Error("cancelled"));
    });
  });
}

async function setup() {
  const dssRoot = IS_MAC
    ? path.join(process.resourcesPath || path.join(__dirname, "../.."), "app")
    : path.join(__dirname, "../..");

  const effectiveRoot = app.isPackaged
    ? path.join(process.resourcesPath, "dss")
    : path.join(__dirname, "../..");

  const pythonCmd = findPython();
  if (!pythonCmd) {
    dialog.showErrorBox(
      "DSS — Python Not Found",
      "DSS requires Python 3.9 or later.\n\n" +
        "Please install Python from https://python.org and restart DSS.\n\n" +
        (IS_WIN ? "Make sure to check 'Add Python to PATH' during installation." : "")
    );
    app.quit();
    return;
  }

  createSplash("Installing dependencies…");
  try {
    await installDependencies(pythonCmd, effectiveRoot);
  } catch (e) {
    closeSplash();
    dialog.showErrorBox(
      "DSS — Setup Failed",
      `Could not install Python packages:\n${e.message}\n\nCheck your internet connection and try again.`
    );
    app.quit();
    return;
  }

  closeSplash();

  const { response } = await dialog.showMessageBox({
    type: "none",
    title: "DSS",
    message: "Welcome to DSS",
    detail:
      "How would you like to use DSS today?\n\n" +
      "  Coordinator — Start a new storage network on this machine.\n" +
      "  Peer Node   — Join an existing network and store files.",
    buttons: ["Start Coordinator", "Join as Peer Node", "Quit"],
    defaultId: 0,
    cancelId: 2,
    icon: null,
  });

  if (response === 2) { app.quit(); return; }

  try {
    if (response === 0) {
      await launchCoordinator(pythonCmd, effectiveRoot);
    } else {
      const prefs = loadPrefs();
      const coordinatorUrl = await promptCoordinatorUrl(prefs.lastCoordinatorUrl);
      savePrefs({ lastCoordinatorUrl: coordinatorUrl });
      await launchPeer(pythonCmd, effectiveRoot, coordinatorUrl);
    }
  } catch (err) {
    closeSplash();
    if (err.message !== "cancelled") {
      dialog.showErrorBox("DSS — Startup Error", err.message);
    }
    app.quit();
  }
}

async function launchCoordinator(pythonCmd, dssRoot) {
  const port = await findFreePort(8000);
  createSplash("Starting DSS Coordinator…");
  spawnPython(pythonCmd, dssRoot, "dss.server.app.main", {
    DSS_SERVER_PORT: String(port),
    DSS_SERVER_HOST: "127.0.0.1",
    DSS_JWT_SECRET: generateSecret(),
    DSS_ADMIN_PASSWORD: "",
  });
  process.env.NEXT_PUBLIC_COORDINATOR_URL = `http://127.0.0.1:${port}`;
  try {
    await waitForPort(port);
  } catch (e) {
    throw new Error("DSS Coordinator did not start in time. Check that Python dependencies are installed.");
  }
  createMainWindow("/admin");
}

async function launchPeer(pythonCmd, dssRoot, coordinatorUrl) {
  const port = await findFreePort(8100);
  createSplash("Starting DSS Peer Node…");
  spawnPython(pythonCmd, dssRoot, "dss.client.app.main", {
    DSS_NODE_PORT: String(port),
    DSS_COORDINATOR_URL: coordinatorUrl,
    DSS_NODE_HOST: "0.0.0.0",
    DSS_ADVERTISED_HOST: getLocalIp(),
  });
  process.env.NEXT_PUBLIC_NODE_URL = `http://127.0.0.1:${port}`;
  try {
    await waitForPort(port);
  } catch (e) {
    throw new Error("DSS Peer Node did not start in time. Check that Python dependencies are installed.");
  }
  createMainWindow("/node");
}

function generateSecret() {
  const chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  return Array.from({ length: 48 }, () => chars[Math.floor(Math.random() * chars.length)]).join("");
}

function getLocalIp() {
  const ifaces = os.networkInterfaces();
  for (const name of Object.keys(ifaces)) {
    for (const iface of ifaces[name]) {
      if (iface.family === "IPv4" && !iface.internal) return iface.address;
    }
  }
  return "127.0.0.1";
}

app.whenReady().then(setup);

app.on("window-all-closed", () => {
  if (!IS_MAC) app.quit();
});

app.on("before-quit", () => { app.isQuitting = true; });

app.on("will-quit", () => {
  for (const proc of childProcesses) {
    try { proc.kill("SIGTERM"); } catch {}
  }
});
