# Beat Strobe - Dual Monitor and Multi-Computer Audio Visualizer

[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-blue)](https://github.com/jatgm/colors)
[![Python](https://img.shields.io/badge/python-3.8%2B-brightgreen)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## Description

Beat Strobe is a high-performance, real-time desktop audio visualizer that transforms monitors and connected computers into a dynamic music-synchronized strobe light display. Powered by Fast Fourier Transform (FFT) spectral analysis, real-time onset detection, and Dynamic Automatic Gain Control (AGC), Beat Strobe captures audio directly from system output (Spotify, YouTube, browser, media players) or microphone inputs and drives immersive multi-monitor visuals.

The application includes multi-computer synchronization over Bluetooth and local Wi-Fi/LAN networks (Host and Client architecture), zero-dependency direct USB HID control for Razer Chroma peripherals, and visual customization options ranging from intense stroboscopic party effects to gentle ambient rave pulses.

### Tags

`audio-visualizer` `real-time-audio` `fft` `beat-detection` `music-visualizer` `pygame` `soundcard` `strobe` `light-show` `multi-monitor` `dual-monitor` `bluetooth-sync` `lan-sync` `razer-chroma` `cross-platform` `macos` `windows` `linux`

---

## Crazy Overdrive Mode (Hotkey X)

Turn displays into a high-intensity festival strobe rig:
- **Stroboscopic Burst Trains (Machine-Gun Multi-Flash)**: Instead of a single pulse, each beat fires a rapid train of 3 to 5 micro-flashes at 35Hz.
- **All-Frequency Multi-Band Triggering**:
  - **Kicks (Sub-Bass)**: Detonate deep color blasts with screen impact shake.
  - **Snares & Claps**: Fire high-brightness phosphor-white accent explosions.
  - **Hi-Hats & Cymbals**: Fire ultra-fast 30-40Hz stroboscopic micro-sparkles on rolls and triplets.
  - **Heavy Drops**: Trigger full blinding-white inverted lightning storms.
- **Hyper-Fast Cooldowns**: Drops refractory cooldown to 0.035s (~28 beats/sec), catching rapid-fire 16th/32nd note drum rolls and techno drops.
- **Ping-Pong Alternating Blitz**: On dual monitors, left and right screens alternate micro-bursts at high speeds.

---

## Multi-Computer Bluetooth and Network Sync

Run Beat Strobe across multiple PCs and laptops in the same space to synchronize all screens to the exact same beat over Bluetooth or Local Area Network (LAN).

### Installation and Quick Start

1. Clone or download the repository:
   ```bash
   git clone https://github.com/jatgm/colors.git
   cd colors
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Launch:
   - On **macOS / Linux**: `./run.sh`
   - On **Windows**: `run.bat`
   - Or directly: `python main.py`

> **Note for macOS System Audio**: macOS does not have native system audio loopback in CoreAudio. Beat Strobe captures your physical microphone out-of-the-box. To capture desktop audio (Spotify, YouTube, browser, etc.) directly, install a free virtual loopback driver such as [BlackHole 2ch](https://github.com/ExistentialAudio/BlackHole) (`brew install blackhole-2ch`); Beat Strobe will automatically detect and prioritize it as `[System Audio]`.

---

### How Host and Client Mode Work

Press **`N`** (or click `Sync: [BT / Network]` on the HUD) to open the Multi-Computer Sync Panel:

#### 1. Host Mode (The DJ / Music Computer)
- Switch to the **Host** tab.
- Broadcasts beat pulses, color palettes, strobe modes, and BPM to all connected computers.
- Opens a direct **Bluetooth RFCOMM Server** (Channel 4) and a **Local Network Server** (Port 42424), broadcasting UDP discovery beacons every 1.5 seconds.
- Displays your computer's local Bluetooth address and number of connected computers.

#### 2. Client Mode (Any other laptop / PC)
- Switch to the **Client** tab.
- Automatically searches for nearby / paired Bluetooth Devices and Network Host Beacons.
- Click **Connect** on the detected Host (or click **Enter Host IP / MAC**).
- Local audio processing pauses on the client, and all screens on the client machine strobe in sub-millisecond lockstep with the Host.

---

## Multi-Monitor Setup (Dual Screens)

The program automatically detects all connected monitors (e.g. two 1920x1080 monitors) and defaults to **Dual Monitor Fullscreen (3840x1080)**.

### Dual-Monitor Visual Schemes (Press B or 2):
1. **Dual Synced**: Both monitors strobe identical vibrant colors in lockstep. Effects are centered individually on each screen to avoid bezel splits.
2. **Ping-Pong Alternating**: Left and right monitors take turns flashing on consecutive beats (Kick 1 hits Left, Kick 2 hits Right).
3. **Complementary Contrast**: Left monitor flashes Palette Color A while Right monitor flashes Palette Color B (e.g. Neon Pink on Left, Electric Cyan on Right).
4. **Panoramic Ultra-Wide**: Spans the entire canvas as one colossal ultra-wide display.

---

## Strobe Modes (Press M to Cycle)

1. **Psycho Overdrive (Ultra)**: Stroboscopic burst trains, rapid complementary neon flips, hi-hat sparkles, and drop blitzes.
2. **Machine-Gun Multi-Band**: Kicks, snares, and hi-hats excite independent strobe layers simultaneously.
3. **Hyper Strobe Blitz**: High-frequency concert strobe simulation with instantaneous blackouts.
4. **Hard Strobe (Classic Rave)**: Instant high-intensity color flash on every kick beat, decaying rapidly to pitch black.
5. **Kick + Snare Dual**: Bass kick fires primary palette color; snare/clap fires a bright lightning-white accent strobe.
6. **Smooth Rave Pulse**: Sinusoidal ambient glow that pulses gently with the music without harsh flickers.
7. **Audio Reactive Spectrum**: Real-time continuous color synthesis based on live audio frequencies.
8. **Chaos Blitz**: High-energy randomized neon color bursts on every transient drop.
9. **Monochrome Blitz**: Pure high-contrast black and white strobe flashes.

---

## Razer Chroma Hardware RGB Lighting (Hotkey C)

Beat Strobe connects directly to connected Razer Keyboards and Mice to flash and strobe their RGB lighting in real-time synchronization with the screen:

- **Zero-Dependency Native Control**: Communicates directly through Windows native `hid.dll` and `setupapi.dll` using custom 90-byte Razer HID feature reports without requiring Synapse or third-party SDKs.
- **Supported Hardware**:
  - **Keyboards**: Razer Ornata V2, BlackWidow series, Huntsman series, Cynosa, DeathStalker, etc.
  - **Mice**: Razer Viper series, DeathAdder series, Basilisk series, Cobra, Naga, etc.
  - **Accessories**: Firefly mousepads, Chroma headsets, and ARGB controllers.
- **Dual-Monitor Channel Splitting**:
  - In **Dual Synced** mode, both keyboard and mouse strobe the exact same colors as the screens.
  - In **Ping-Pong Alternating** or **Complementary Contrast** modes, the keyboard maps to the Left monitor and the mouse maps to the Right monitor, creating a physical light show where beats bounce between monitors, keyboard, and mouse.
- **Asynchronous Sub-Millisecond USB Dispatch**: Non-blocking background worker thread guarantees zero frame drops or lag on high-refresh-rate screen strobing.

---

## Controls and Shortcuts

| Key | Action | Description |
| :--- | :--- | :--- |
| **`ESC`** | **Exit / Close Modal** | Closes active modal or exits the application safely. |
| **`X`** | **Toggle CRAZY MODE** | Instantly toggles Crazy Overdrive strobe on/off. |
| **`C`** | **Toggle Razer Chroma** | Toggles hardware RGB lighting sync for Razer keyboards & mice. |
| **`N`** | **Bluetooth Sync Modal** | Opens the Multi-Computer Host & Client sync panel. |
| **`F`** or **`F11`** | **Display Mode** | Cycles: Dual Monitor Fullscreen $\to$ Monitor 1 $\to$ Monitor 2 $\to$ Windowed. |
| **`B`** or **`2`** | **Dual FX Scheme** | Cycles: Dual Synced $\to$ Ping-Pong Alternating $\to$ Complementary Contrast $\to$ Panoramic. |
| **`H`** or **`TAB`** | **Toggle HUD** | Shows or hides the control overlay (HUD auto-fades after 3.5s of mouse inactivity). |
| **`M`** | **Cycle Strobe Mode** | Cycles through 9 strobe modes. |
| **`P`** | **Cycle Palette** | Switches between 9 color palettes. |
| **`V`** | **Cycle Visual Style** | Solid Fullscreen $\leftrightarrow$ Radial Shockwave $\leftrightarrow$ Horizon Pulse. |
| **`D`** | **Switch Audio Source** | Cycles between System Audio Loopback, Monitors, and Microphones. |
| **`S`** | **Safe Mode Toggle** | Toggles gentle pulsing glow vs intense hard strobe. |
| **`T`** | **Demo Mode Toggle** | Synthesizes a 128 BPM electronic beat to test visuals without music. |
| **`UP` / `DOWN`** | **Sensitivity** | Increases or decreases beat detection sensitivity. |
| **`[` / `]`** or **`PgUp` / `PgDn`** | **Pre-Amp Boost** | Adjusts input AGC gain multiplier (0.5x to 8.0x) for soft/loud audio sources. |
| **`RIGHT` / `LEFT`** | **Decay Speed** | Adjusts how fast flashes fade out (snappy strobe vs lingering rave glow). |
| **`SPACE`** | **Manual Flash** | Forces an instant kick beat flash. |
