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

## Cyber-Studio Dropdown UI & Automatic Music Detection

Beat Strobe features a completely redesigned, cyber-studio Heads-Up Display (HUD) with interactive dropdown selectors:
- **Interactive Dropdown Selectors**: Replaced flat cycling buttons with dedicated popover dropdown menus:
  - **Mode Dropdown**: Interactive drop-up menu listing all 13 strobe modes with instant single-click selection and active checkmarks.
  - **Palette Dropdown**: Lists all color palettes with live 4-color swatch preview chips drawn beside each palette name.
  - **Audio Source Dropdown**: Direct selection of isolated Spotify audio, system loopback, and physical microphones.
  - **Style Dropdown**: Instant selection between Solid Fullscreen, Radial Shockwave, and Horizon Pulse.
  - **Dual FX Dropdown**: Quick selection of Dual Synced, Ping-Pong Alternating, Complementary Contrast, and Panoramic schemes.
  - **Display Dropdown**: Direct windowed, single-monitor, and dual-monitor arrangement selection.
- **Maximized Screen Real Estate**: Streamlined HUD height (~282px) giving full priority to high-impact screen strobe visuals while keeping all essential controls immediately accessible.
- **Automatic Spotify Detection**: Automatically detects when Spotify is running and isolates pure Spotify audio output from noisy background applications (with seamless fallback to System Audio loopback).
- **Default Album Cover Art Synchronization**: Launches directly in Album Cover Art mode, capturing live track artwork and extracting dominant 5-color palettes in real-time.
- **Consolidated Horizontal Control Deck**: Sensitivity, Preamp Gain, and Decay Rate sliders consolidated side-by-side into a single 3-column row with real-time numeric readouts.
- **Modular Studio Surface**: Cleanly divided into master audio telemetry, 80px waveform scrub deck, precision mixers, dropdown selectors, ambient solid color lighting bar, and quick hardware toggle pods.

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

## Detection Engines: Smart Rhythm PLL vs. Classic Rapid

Beat Strobe provides two distinct, switchable audio detection architectures:

### 1. Smart Rhythm Engine (Default: Phase-Locked Loop Grid & Bayesian Prior)
- **Phase-Locked Loop (PLL) Tempo Grid**: Internal rhythm oscillator locks phase and frequency to the musical tempo grid (quarter notes, eighths, sixteenths), predicting exactly when downbeats land.
- **Bayesian Prior Expectation**: When an audio burst arrives on-grid, threshold sensitivity is lowered, rewarding rhythmic consistency and filtering out off-beat chatter or random noise.
- **808 Attack Transient vs Sustain Tail Isolation**: Detects the sharp initial strike of an 808 sub-bass kick without re-triggering 10 to 15 false flashes during the rumbling bass tail decay.
- **Snare and Clap Backbeat Prior**: Dedicated frequency detection for snares (200-500 Hz) and claps (1000-3000 Hz) that align on backbeats (beats 2 and 4), producing high-contrast secondary accent flashes.
- **Live HUD Engine Status Badge**: Displays `ENG: SMART PLL` with glowing cyan status pip. Clicking the badge or pressing **`2`** toggles between Smart PLL and Classic engines.

### 2. Classic Rapid Strobe Engine (Hotkey 3 or E)
- **100% Unconstrained Raw Strobe**: Preserves the ultra-rapid, instantaneous peak detection mode from previous versions.
- **Instant Micro-Transient Reaction**: Fires immediate flashes on any raw amplitude peak exceeding threshold without tempo locking or prior quantization.
- **Live HUD Engine Status Badge**: Displays `ENG: CLASSIC` with bright orange status pip.

---

## Razer Chroma Keyboard Per-Key RGB Matrix Engine (Hotkey C)

Beat Strobe connects directly to connected Razer Keyboards and Mice to drive custom 6x22 per-key matrix animations and strobe lighting in real-time synchronization with the screen:

- **Zero-Dependency Native Control**: Communicates directly through Windows native `hid.dll` and `setupapi.dll` using custom 90-byte Razer HID feature reports without requiring Synapse or third-party SDKs.
- **Supported Hardware**:
  - **Keyboards**: Razer Ornata V2, BlackWidow series, Huntsman series, Cynosa, DeathStalker, etc. (Full 6-row x 22-column addressable key matrix).
  - **Mice**: Razer Viper series, DeathAdder series, Basilisk series, Cobra, Naga, etc. (Logo and scroll wheel lighting).
  - **Accessories**: Firefly mousepads, Chroma headsets, and ARGB controllers.
- **Per-Key & Per-Row Matrix Animations**:
  - **Function Row Real-Time EQ Spectrum Analyzer (Row 0: Esc through Pause)**: Maps live audio frequency energy across all 22 columns of the function key row, creating an animated equalizer directly on your keyboard keycaps.
  - **Spacebar Kick & 808 Radial Shockwaves**: On every kick or drop, an explosive radial shockwave detonates from the Spacebar (Row 5, Col 8) and ripples outward across rows 4, 3, 2, 1, 0, leaving an afterglow trailing towards the screen.
  - **Snare / Clap Lateral Accent Wave**: Horizontal sweeps burst outward across typing rows 2, 3, 4 with high-contrast secondary accent hues.
  - **Hi-Hat Micro-Sparkles**: Dynamic diamond-white keycap sparkles dancing across the number and QWERTY rows on cymbal transients.
  - **Spatial Dual-Monitor Screen Matching**: In dual monitor mode, keyboard columns 0-10 track the Left monitor and room BLE lights, while columns 11-21 track the Right monitor and mouse.
  - **Instant Zero-Lag Blackout Cut**: Instantaneous hardware blackout report (<0.5ms) synchronized with visualizer strobe cuts.
  - **Static Solid Color Illumination**: In solid color mode, all 132 keys continuously illuminate in the selected solid color without strobing.
- **Sub-Millisecond Non-Blocking USB HID Performance**: Pre-allocated ctypes buffers with in-place byte writes, transmitting only changed rows for smooth, stutter-free 60-90 FPS hardware updates.

---

## Strobe Modes (Press M to Cycle)

1. **Smart Rhythm (PLL Sync)**: Intelligent tempo grid tracking, 808 transient isolation, melody progression, and musical downbeat synchronization.
2. **Classic Rapid Strobe**: Raw unconstrained rapid-fire strobe matching original instant peak triggering.
3. **Psycho Overdrive (Ultra)**: Stroboscopic burst trains, rapid complementary neon flips, hi-hat sparkles, and drop blitzes.
4. **Red Only (Pure Red Strobe)**: High-intensity pure red strobe flashes (RGB 255, 0, 0) on every beat with absolute pitch-black cutoffs between strikes.
5. **Bass Only (Pure Low-End Strobe)**: Strictly reacts to kicks, 808s, and heavy sub-bass beats with absolute blackouts between hits (completely ignores snares, hi-hats, mids, and vocals).
6. **Cover Art Sync**: Real-time sync with dominant colors extracted from Windows Media playback album covers.
7. **Machine-Gun Multi-Band**: Kicks, snares, and hi-hats excite independent strobe layers simultaneously.
8. **Hyper Strobe Blitz**: High-frequency concert strobe simulation with instantaneous blackouts.
9. **Hard Strobe (Classic Rave)**: Instant high-intensity color flash on every kick beat, decaying rapidly to pitch black.
10. **Kick + Snare Dual**: Bass kick fires primary palette color; snare/clap fires a bright lightning-white accent strobe.
11. **Smooth Rave Pulse**: Sinusoidal ambient glow that pulses gently with the music without harsh flickers.
12. **Audio Reactive Spectrum**: Real-time continuous color synthesis based on live audio frequencies.
13. **Chaos Blitz**: High-energy randomized neon color bursts on every transient drop.
14. **Monochrome Blitz**: Pure high-contrast black and white strobe flashes.

---

---

## Native Album Cover Art Sync (Hotkey A)

Beat Strobe connects directly to the native Windows Runtime (`Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager`) to automatically detect media currently playing across Windows media players (Spotify, Apple Music, Tidal, Chrome, Edge, YouTube Music, etc.):

- **Native Cover Art Capture**: Streams the album artwork image bytes directly from the active media session's thumbnail reference without web scraping or third-party API keys.
- **Intelligent Palette Extraction**: Samples and analyzes the cover artwork in HSV color space, extracting the 5 most vibrant, contrasting dominant colors while filtering out dark mud and washed-out tones.
- **Dynamic Real-Time Track Updates**: When tracks change, Beat Strobe extracts the new artwork palette on-the-fly and seamlessly transitions strobe colors.
- **Hardware Peripheral Lockstep**: Screen strobes, Razer Chroma keyboards & mice (`razer_mgr`), HappyLighting BLE room LED strips (`happylighting_mgr`), and Lenovo Legion gaming desktop PC RGB (`lenovo_mgr`) all flash and pulse in perfect sync with the album cover art colors.
- **HUD Now Playing Card**: Displays a 40x40 thumbnail of the actual album cover, track title, artist name, and 5 color swatch chips on the Heads-Up Display. Clicking the card or pressing **`A`** immediately engages Album Art mode.

---

## Static Solid Color Lighting Mode (Hotkeys O / 4 / Z)

Beat Strobe includes a dedicated static lighting system that transforms displays and peripherals into continuous ambient room lighting:

- **1-Click Music vs Solid Toggle**: Click the prominent `[LIGHT] SOLID` / `[LIGHT] MUSIC` button on the HUD to immediately toggle between static illumination and audio-reactive strobe mode.
- **Interactive Color Swatches Bar**: 14 hand-crafted vibrant color chips directly on the HUD (Pure Red, Orange Neon, Amber Gold, Electric Yellow, Lime Green, Mint Cyan, Sky Blue, Deep Blue, Violet, Magenta Pink, Hot Pink, Warm White, Pure White). Clicking any swatch instantly illuminates screens and hardware with that exact color.
- **Continuous Hardware Illumination**: All hardware peripherals (Razer Chroma keyboards & mice, HappyLighting Bluetooth room light strips, and Lenovo Legion gaming desktop RGB) stay steadily lit with zero flickering, fading, or blackout strobe cuts.
- **Hotkey Controls**: Press **`O`**, **`4`**, or **`Z`** to toggle between solid color mode and music strobing. When solid lighting is active, pressing **`P`** cycles through the solid color presets.

---

## Controls and Shortcuts

| Key | Action | Description |
| :--- | :--- | :--- |
| **`ESC`** | **Exit / Close Modal** | Closes active modal or exits the application safely. |
| **`5`**, **`O`**, or **`Z`** | **Toggle Solid Color Lighting** | Toggles between static room illumination and music-reactive strobing. |
| **`1`** or **`Q`** | **Toggle Bass Only Mode** | Toggles pure bass strobe (only reacts to kicks, 808s, and sub-bass). |
| **`2`** or **`W`** | **Toggle Engine (Smart vs Classic)** | Toggles between Smart Rhythm (PLL Grid) and Classic Raw strobe engines. |
| **`3`** or **`E`** | **Toggle Classic Rapid Strobe** | Toggles Classic Rapid Strobe mode (unconstrained raw peak triggering). |
| **`4`** or **`R`** | **Toggle Red Only Mode** | Toggles pure crimson red strobe flashes on all beats. |
| **`A`** | **Toggle Album Art Mode** | Toggles strobe mode & palette sync to currently playing album cover art. |
| **`X`** | **Toggle CRAZY OVERDRIVE** | Instantly toggles Crazy Overdrive strobe on/off. |
| **`C`** | **Toggle Razer Chroma** | Toggles hardware RGB lighting sync for Razer keyboards & mice. |
| **`L`** | **Toggle Room Lights** | Toggles Bluetooth BLE room light strip synchronization (HappyLighting). |
| **`K`** | **Toggle Legion PC RGB** | Toggles Lenovo Legion gaming desktop PC RGB lighting. |
| **`N`** | **Bluetooth Sync Modal** | Opens the Multi-Computer Host & Client sync panel. |
| **`F`** or **`F11`** | **Display Mode** | Cycles: Dual Monitor Fullscreen $\to$ Monitor 1 $\to$ Monitor 2 $\to$ Windowed. |
| **`B`** | **Dual FX Scheme** | Cycles: Dual Synced $\to$ Ping-Pong Alternating $\to$ Complementary Contrast $\to$ Panoramic. |
| **`H`** or **`TAB`** | **Toggle HUD** | Shows or hides the control overlay (HUD auto-fades after 3.5s of mouse inactivity). |
| **`M`** | **Cycle Strobe Mode** | Cycles through strobe modes (including [BASS] Bass Only and [ALBUM] Cover Art). |
| **`P`** | **Cycle Palette / Solid Color** | Cycles palettes in music mode, or cycles solid colors when solid lighting is active. |
| **`V`** | **Cycle Visual Style** | Solid Fullscreen $\leftrightarrow$ Radial Shockwave $\leftrightarrow$ Horizon Pulse. |
| **`D`** | **Switch Audio Source** | Cycles between System Audio Loopback, Monitors, and Microphones. |
| **`S`** | **Safe Mode Toggle** | Toggles gentle pulsing glow vs intense hard strobe. |
| **`T`** | **Demo Mode Toggle** | Synthesizes a 128 BPM electronic beat to test visuals without music. |
| **`UP` / `DOWN`** | **Sensitivity** | Increases or decreases beat detection sensitivity. |
| **`[` / `]`** or **`PgUp` / `PgDn`** | **Pre-Amp Boost** | Adjusts input AGC gain multiplier (0.5x to 8.0x) for soft/loud audio sources. |
| **`RIGHT` / `LEFT`** | **Decay Speed** | Adjusts how fast flashes fade out (snappy strobe vs lingering rave glow). |
| **`SPACE`** | **Manual Flash** | Forces an instant kick beat flash. |
