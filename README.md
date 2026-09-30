# ⚡ Beat Strobe - Dual Monitor & Multi-Computer Bluetooth Audio Visualizer

A high-performance real-time desktop application that turns your monitor(s) and connected computers into a dynamic music-synchronized strobe light show. It captures system audio (Spotify, YouTube, VLC, browser, games, etc.) or microphone input using WASAPI loopback, analyzes frequency bands and spectral flux with FFT, and strobes colors across **both monitors in seamless borderless fullscreen**, with **Bluetooth & Network Multi-Computer Synchronization**.

---

## 📡 Multi-Computer Bluetooth & Network Sync

You can run Beat Strobe across multiple PCs / laptops in the same room or at a party to synchronize all screens to the exact same beat over **Bluetooth** or **Local Network**!

### 📥 Downloading from GitHub on other computers:
1. Clone or download the repository:
   ```bash
   git clone https://github.com/jatgm/colors.git
   cd colors
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Launch with `run.bat` or `python main.py`.

---

### 🎙️ How Host & Client Mode Work

Press **`N`** (or click `Sync: [BT / Network]` on the HUD) to open the **Multi-Computer Sync Panel**:

#### 1. Host Mode (The DJ / Music Computer)
- Switch to the **Host** tab.
- The Host plays music (or captures audio), runs the FFT beat detector, and automatically broadcasts beat pulses, color palettes, strobe modes, and BPM to all connected computers.
- Opens a direct **Bluetooth RFCOMM Server** (Channel 4) and a **Local Network Server** (Port 42424), broadcasting beacons every 1.5 seconds.
- Displays your computer's local Bluetooth address (e.g. `34:C9:3D:20:5D:40`) and number of connected computers.

#### 2. Client Mode (Any other laptop / PC)
- Switch to the **Client** tab.
- Automatically searches for nearby / paired **Bluetooth Devices** and **Network Host Beacons**.
- Click **Connect** on the detected Host.
- Local audio processing pauses on the client, and all screens on the client machine strobe in **sub-millisecond lockstep** with the Host!

---

## 🖥 Multi-Monitor Setup (Dual Screens)

The program automatically detects all connected monitors (e.g. two 1920x1080 monitors) and defaults to **Dual Monitor Fullscreen (3840x1080)**.

### 🎭 Dual-Monitor Visual Schemes (Press `B` or `2`):
1. **Dual Synced**: Both monitors strobe identical vibrant colors in lockstep. Effects are centered individually on each screen to avoid bezel splits.
2. **Ping-Pong Alternating**: Left and right monitors take turns flashing on consecutive beats (Kick 1 hits Left, Kick 2 hits Right).
3. **Complementary Contrast**: Left monitor flashes Palette Color A while Right monitor flashes Palette Color B (e.g. Neon Pink on Left, Electric Cyan on Right).
4. **Panoramic Ultra-Wide**: Spans the entire 3840x1080 canvas as one colossal ultra-wide rave display.

### 🎯 Smart Active-Monitor HUD:
The control overlay and photosensitivity safety dialog automatically anchor to whichever monitor your mouse is hovering over.

---

## ⚠ Photosensitivity & Epilepsy Warning
This application produces rapid flashing lights, high-contrast strobes, and color flashes across multiple displays.
- If you or anyone around you has photosensitive epilepsy, seizures, or light sensitivity, do **not** use the hard strobe mode.
- Use **Safe Mode** (`S` key or button) for a gentle, warm, rhythmic ambient glow instead of hard flickering.

---

## 🚀 Quick Start

### 1. Launch with double-click:
Double-click [`run.bat`](file:///D:/Projects/colors/run.bat) in the project folder.

### 2. Launch via Terminal / Command Prompt:
```powershell
python main.py
```

---

## 🎮 Controls & Shortcuts

| Key | Action | Description |
| :--- | :--- | :--- |
| **`ESC`** | **Exit / Close Modal** | Closes active modal or exits the application safely. |
| **`N`** | **Bluetooth Sync Modal** | Opens the Multi-Computer Host & Client Bluetooth panel. |
| **`F`** or **`F11`** | **Display Mode** | Cycles: *Dual Monitor Fullscreen (3840x1080)* $\to$ *Monitor 1* $\to$ *Monitor 2* $\to$ *Windowed*. |
| **`B`** or **`2`** | **Dual FX Scheme** | Cycles: *Dual Synced* $\to$ *Ping-Pong Alternating* $\to$ *Complementary Contrast* $\to$ *Panoramic*. |
| **`H`** or **`TAB`** | **Toggle HUD** | Shows or hides the control overlay (HUD auto-fades after 3.5s of mouse inactivity). |
| **`M`** | **Cycle Strobe Mode** | Switches between 6 strobe modes (*Hard Strobe*, *Kick+Snare Dual*, *Smooth Pulse*, etc.). |
| **`P`** | **Cycle Palette** | Switches between 9 color palettes (*Cyberpunk*, *Rave Neon*, *Rainbow*, *Fire*, etc.). |
| **`V`** | **Cycle Visual Style** | Solid Fullscreen $\leftrightarrow$ Radial Shockwave $\leftrightarrow$ Horizon Pulse. |
| **`D`** | **Switch Audio Source** | Cycles between System Audio Loopback, Monitors, and Microphones. |
| **`S`** | **Safe Mode Toggle** | Toggles gentle pulsing glow vs intense hard strobe. |
| **`T`** | **Demo Mode Toggle** | Synthesizes a 128 BPM electronic beat to test visuals without music. |
| **`↑` / `↓`** | **Sensitivity** | Increases or decreases beat detection sensitivity. |
| **`→` / `←`** | **Decay Speed** | Adjusts how fast flashes fade out (snappy strobe vs lingering rave glow). |
| **`SPACE`** | **Manual Flash** | Forces an instant kick beat flash. |
