# PERFECT Agent Browser Extension (Chrome + Edge)

This extension is built with the standard Chromium WebExtension format (Manifest V3), so the same folder works in both:

- Google Chrome
- Microsoft Edge

## 1) Start the local backend

From the project root:

```bash
uv sync
uv run verify-setup
uv run start-server --reload
```

Default backend URL: `http://localhost:8000`

## 2) Load extension in Chrome

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select the `browser-extension/` folder

## 3) Load extension in Edge

1. Open `edge://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select the `browser-extension/` folder

## 4) Configure settings

- Click the extension icon, then ⚙ to open settings
- Set backend URL and timeout if needed
- Use **Health** to verify connectivity

## 5) Package a distributable zip

```bash
uv run package-browser-extension
```

Output zip:

`dist/perfect-agent-browser-extension-v0.1.0.zip`

You can upload this zip to Chrome/Edge extension portals, or share it internally.
