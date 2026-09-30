# ⚡ Beat Strobe - Dual Monitor Audio Visualizer & Color Strober

A high-performance real-time desktop application that turns your multi-monitor setup into a dynamic music-synchronized strobe light. It captures system audio (Spotify, YouTube, VLC, browser, games, etc.) or microphone input using WASAPI loopback, analyzes frequency bands and spectral flux with FFT, and strobes colors across **both monitors in seamless borderless fullscreen**.

---

## 🖥 Multi-Monitor Setup

The program automatically detects all connected monitors (e.g. your two 1920x1080 MSI monitors) and defaults to **Dual Monitor Fullscreen (3840x1080)**.

### 🎭 Dual-Monitor Visual Schemes (Press `B` or `2`):
1. **Dual Synced**: Both monitors strobe identical vibrant colors in absolute lockstep. Shockwaves and visual effects are centered individually on each screen so you never get awkward bezel splits.
2. **Ping-Pong Alternating**: Left and right monitors take turns flashing on consecutive beats! (Kick 1 hits Left, Kick 2 hits Right!).
3. **Complementary Contrast**: Left monitor flashes Palette Color A while Right monitor flashes Palette Color B (e.g. Neon Pink on Left, Electric Cyan on Right), swapping or cycling on each beat.
4. **Panoramic Ultra-Wide**: Spans the entire 3840x1080 canvas as one colossal ultra-wide rave display.

### 🎯 Smart Active-Monitor HUD:
The control overlay and photosensitivity safety dialog automatically anchor to whichever monitor your mouse is currently hovering over, so menus are never cut in half by plastic monitor bezels.

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
| **`ESC`** | **Exit** | Closes the application safely. |
| **`F`** or **`F11`** | **Display Mode** | Cycles: *Dual Monitor Fullscreen (3840x1080)* $\to$ *Monitor 1* $\to$ *Monitor 2* $\to$ *Windowed*. |
| **`B`** or **`2`** | **Dual FX Scheme** | Cycles: *Dual Synced* $\to$ *Ping-Pong Alternating* $\to$ *Complementary Contrast* $\to$ *Panoramic*. |
| **`H`** or **`TAB`** | **Toggle HUD** | Shows or hides the control overlay (HUD auto-fades after 3.5s of mouse inactivity). |
| **`M`** | **Cycle Strobe Mode** | Switches between the 6 strobe modes. |
| **`P`** | **Cycle Palette** | Switches between 9 color palettes. |
| **`V`** | **Cycle Visual Style** | Solid Fullscreen $\leftrightarrow$ Radial Shockwave $\leftrightarrow$ Horizon Pulse. |
| **`D`** | **Switch Audio Source** | Cycles between System Audio Loopback, Monitors, and Microphones. |
| **`S`** | **Safe Mode Toggle** | Toggles gentle pulsing glow vs intense hard strobe. |
| **`T`** | **Demo Mode Toggle** | Synthesizes a 128 BPM electronic beat to test visuals without music. |
| **`↑` / `↓`** | **Sensitivity** | Increases or decreases beat detection sensitivity. |
| **`→` / `←`** | **Decay Speed** | Adjusts how fast flashes fade out (snappy strobe vs lingering rave glow). |
| **`SPACE`** | **Manual Flash** | Forces an instant kick beat flash. |

---

## 🎨 Strobe Modes

1. **Hard Strobe (Classic Rave)**: Instant high-intensity color flash on every kick beat, decaying rapidly to pitch black for maximum strobe contrast.
2. **Kick + Snare Dual**: Bass kick fires primary palette color flash; snare/clap fires a bright lightning-white accent strobe.
3. **Smooth Rave Pulse**: Sinusoidal ambient glow that pulses gently with the music without harsh flickers.
4. **Audio Reactive Spectrum**: Real-time continuous color synthesis based on live audio frequencies (Bass $\to$ Red/Pink, Mids $\to$ Green/Yellow, Treble $\to$ Cyan/Blue).
5. **Chaos Blitz**: High-energy randomized neon color bursts on every transient drop.
6. **Monochrome Blitz**: Pure high-contrast black and white strobe flashes.

---

## 🌈 Color Palettes

- **Cyberpunk**: Neon Pink, Electric Cyan, Neon Purple, Electric Yellow, Mint Neon
- **Rave Neon**: Laser Green, Hot Pink, Deep Violet, Sunset Orange, Electric Blue
- **Rainbow Cycle**: Smooth 360-degree HSV rainbow cycle advancing on each beat
- **Fire & Magma**: Crimson, Molten Orange, Blazing Gold, White-Hot Flare
- **Electric Ice**: Glacial Cyan, Deep Electric Blue, Ice Mint, Crystal White
- **Acid Techno**: Laser Lime, Acid Yellow, Flash White, Bright Emerald
- **Synthwave 80s**: Neon Fuchsia, Retro Purple, Miami Cyan, Sunset Gold
- **Pastel Dream**: Soft Lavender, Mint, Peach, Baby Blue, Pastel Rose
- **Monochrome Blitz**: Pure White, Silver, Dark Charcoal
