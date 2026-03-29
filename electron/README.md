# DSS Electron App

## Purpose

The DSS Electron app is the recommended way to run DSS. It handles everything automatically:
- Checks that Python 3 is installed
- Installs all Python dependencies on first launch
- Starts the right backend process
- Opens the dashboard in a window

No terminal or command-line knowledge is required.

---

## For End Users

1. Download the DSS app for your platform (macOS `.dmg`, Windows `.exe`, Linux `.AppImage`).
2. Open the app.
3. Choose **Start Coordinator** (if you're setting up the network) or **Join as Peer Node** (if you're connecting to an existing network).
4. The app does the rest.

**Joining a network?** You'll need the coordinator's IP address and port from your admin — it looks like `http://192.168.1.10:8000`. Your address is saved for next time.

---

## Troubleshooting

**"Python not found"**
Install Python 3.9+ from https://python.org. On Windows, check "Add Python to PATH" during setup.

**App opens but dashboard is blank**
The UI (Next.js) may not be running. In development, run `npm run dev` inside the `ui/` folder.

**"A background service stopped unexpectedly"**
Check that Python dependencies installed correctly. Try running `pip install -r requirements.txt` manually.

---

## Development

```bash
cd electron
npm install
npm start          # run in development mode
```

For the full experience, also start the UI in parallel:

```bash
cd ui
npm install
npm run dev
```

## Building a Distributable

```bash
cd electron
npm run build:mac     # macOS .dmg
npm run build:win     # Windows NSIS installer
npm run build:linux   # Linux AppImage
```

## Key Modules

```
electron/
├── package.json     # App metadata, electron-builder config
└── src/
    └── main.js      # Main process: Python check, dep install, mode dialog,
                     #   port allocation, process spawning, splash screen
```

## Data Flow

```
App launches
  → Check Python available
  → pip install requirements silently
  → Mode dialog: Coordinator | Peer | Quit
  → Coordinator: allocate port → spawn dss.server.app.main → wait for port → open /admin
  → Peer: prompt coordinator URL (saved) → allocate port → spawn dss.client.app.main → open /node
  → will-quit: kill all child processes
```
