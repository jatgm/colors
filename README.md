# colors - Dual Monitor and Multi-Computer Audio Visualizer

[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-blue)](https://github.com/jatgm/colors)
[![Python](https://img.shields.io/badge/python-3.8%2B-brightgreen)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## Description

colors is a high-performance, real-time desktop audio visualizer that transforms monitors, peripherals, and connected computers into a dynamic music-synchronized strobe light display. Powered by Fast Fourier Transform (FFT) spectral analysis, real-time onset detection, and Dynamic Automatic Gain Control (AGC), colors captures audio directly from system output (Spotify, YouTube, browser, media players) or microphone inputs and drives immersive multi-monitor visuals.

The application includes multi-computer synchronization over Bluetooth and local Wi-Fi/LAN networks (Host and Client architecture), zero-dependency direct USB HID control for Razer Chroma peripherals, Bluetooth BLE room lighting control, and visual customization options ranging from intense stroboscopic party effects to gentle ambient rave pulses.

### Tags

`audio-visualizer` `real-time-audio` `fft` `beat-detection` `music-visualizer` `pygame` `soundcard` `strobe` `light-show` `multi-monitor` `dual-monitor` `bluetooth-sync` `lan-sync` `razer-chroma` `cross-platform` `macos` `windows` `linux`

---

## Detection Engines: colors2.0 vs colors1.0

colors provides two distinct, switchable audio detection architectures:

### 1. colors2.0 (Smart Rhythm Engine)
- **Phase-Locked Loop (PLL) Tempo Grid**: Internal rhythm oscillator locks phase and frequency to the musical tempo grid (quarter notes, eighths, sixteenths), predicting exactly when downbeats land.
- **Bayesian Prior Expectation**: When an audio burst arrives on-grid, threshold sensitivity is boosted, rewarding rhythmic consistency and suppressing off-beat background chatter or noise.
- **808 Attack Transient vs Sustain Tail Isolation**: Isolates the sharp initial attack strike of an 808 sub-bass hit and suppresses false re-triggering during the prolonged decaying rumble tail.
- **Snare and Clap Backbeat Prior**: Dedicated frequency detection for snares (200-500 Hz) and claps (1000-3000 Hz) aligning with backbeats (beats 2 and 4), producing high-contrast secondary accent flashes.
- **Decoupled from Light Mode**: Switching engines preserves active solid ambient lighting mode without disruption.
- **Prominent Header Badge**: Prominently displayed in the HUD header as `[ colors2.0 ]`. Clicking the badge or pressing **`2`** or **`W`** toggles engines.

### 2. colors1.0 (Classic Rapid Strobe Engine)
- **100% Unconstrained Raw Strobe**: Preserves the ultra-rapid, instantaneous peak detection mode.
- **Instant Micro-Transient Reaction**: Fires immediate flashes on any raw amplitude peak exceeding threshold without tempo locking or prior quantization.
- **Prominent Header Badge**: Prominently displayed in the HUD header as `[ colors1.0 ]`. Clicking the badge or pressing **`3`** or **`E`** engages colors1.0.

---

## Real-Time Logic & Math Telemetry Console Log (Hotkey ~ / F12 / G)

colors includes a built-in, cyber-studio real-time telemetry console that exposes the behind-the-scenes mathematics and trigger decision logic in live execution:

- **Live Math Matrix**:
  - **Kick Trigger Math**: Current bass flux vs dynamic threshold with exact ratio and trigger indicator (e.g. `KICK: flux 0.82 / th 0.54 (1.52x) [TRIG]`).
  - **Snare Transient Math**: High-band flux vs snare threshold with trigger ratio.
  - **808 Sub-Bass Math**: Deep sub flux vs sub-bass threshold.
  - **PLL Grid Multiplier**: Quantized tempo grid multiplier and phase alignment status (`ON-GRID BOOST` vs `OFF-BEAT SUPPRESS`).
  - **808 Envelope Status**: Real-time identification of `ATTACK IMPACT` vs `SUSTAIN TAIL (GATED)`.
  - **Energy & AGC Gain**: Live RMS, peak amplitude, input sensitivity, and pre-amp boost readouts.
- **Live Decision Stream (Terminal Stream)**:
  - Color-coded scrolling terminal showing exact timestamps and trigger rationale:
    - `[KICK]` in neon green
    - `[808 SUB]` in neon purple
    - `[808 TAIL GATED]` in muted amber (sustain decay suppressed)
    - `[SNARE]` in electric yellow
    - `[HIHAT]` in pale ice cyan
    - `[DROP]` in vivid orange-red
    - `[SECTION]` in cyan (dynamic song section transitions: Verse, Buildup, Chorus)
    - `[PLL SYNC]` in electric lime
- **Instant Access**: Toggle anytime by pressing **`~`** (backquote/tilde), **`F12`**, **`G`**, or clicking **`CONSOLE LOG [~]`** in the HUD header.

---

## Cyber-Studio Dropdown UI & Automatic Music Detection

colors features a redesigned cyber-studio Heads-Up Display (HUD) with interactive dropdown selectors:
- **Interactive Dropdown Selectors**: Popover menus for Mode, Palette, Audio Source, Style, Dual FX, and Display arrangements.
- **Prominent Engine Selection**: Header badge clearly distinguishes `[ colors2.0 ]` from `[ colors1.0 ]` with click-to-toggle support.
- **Independent Light Mode Indicator**: Ambient solid color lighting displays a separate badge (`[LIGHT: <COLOR>]`) that never hides or collides with engine status.
- **Streamlined HUD Surface**: Height optimized (~282px) giving full priority to high-impact screen strobe visuals while keeping all essential controls immediately accessible.
- **Automatic Spotify Detection**: Automatically detects when Spotify is running and isolates pure Spotify audio output from background noise.
- **Default Album Cover Art Synchronization**: Launches directly in Album Cover Art mode, capturing live track artwork and extracting dominant 5-color palettes in real-time.
- **Consolidated Control Deck**: Sensitivity, Preamp Gain, and Decay Rate sliders consolidated side-by-side into a single 3-column row with real-time numeric readouts.

---

## Hardware Peripheral Synchronization

colors features zero-latency direct hardware integration across peripherals and smart lighting:

### Razer Chroma Keyboards & Mice (Hotkey C)
- **Zero-Dependency Native Control**: Communicates directly through Windows native `hid.dll` and `setupapi.dll` using custom 90-byte Razer HID feature reports without requiring Synapse or third-party background software.
- **Razer Viper Mouse Synchronization**: Direct PID identification (`0x0078`) and dual volatile/non-volatile feature report transmission (`0x0F, 0x02, 0x09` with `VARSTORE`), routing mouse lighting commands with priority for zero-lag reactivity.
- **Razer Ornata V2 / Chroma Keyboards**:
  - **Function Row Real-Time Spectrum Analyzer (Row 0)**: 22-column live equalizer animated across function keycaps.
  - **Spacebar Kick Epicenter Flare**: White-hot epicenter flare detonating from the spacebar on kick drum impacts with supersonic shockwave propagation outward across typing rows.
  - **Sub-Bass 808 Bottom-Row Vibration**: Rumble effect along bottom row during sustained sub-bass.
  - **Snare Lateral Accent Wave**: Rapid horizontal sweep across typing rows in contrasting secondary accent hue.
  - **Instant Zero-Lag Blackout Cut**: Sub-millisecond hardware blackout reports synchronized with visualizer strobe cuts.

### HappyLighting Bluetooth BLE Room LED Strips (Hotkey L)
- **Eliminated Timing Jitter & Lag**: Optimized asynchronous BLE streaming loop with queue pre-checks to bypass sleep delays, delivering tight, synchronized room flashes that strike on the exact audio transient.

### Lenovo Legion Gaming Desktop PC RGB (Hotkey K)
- **Direct PC Case RGB Sync**: Direct motherboard and case lighting integration synchronized to audio transients and strobe cuts.

---

## Crazy Overdrive Mode (Hotkey X)

Turn displays into a high-intensity festival strobe rig:
- **Stroboscopic Burst Trains (Machine-Gun Multi-Flash)**: Rapid train of 3 to 5 micro-flashes at 35Hz on every major beat.
- **All-Frequency Multi-Band Triggering**:
  - **Kicks (Sub-Bass)**: Detonate deep color blasts with screen impact shake.
  - **Snares & Claps**: Fire high-brightness phosphor-white accent explosions.
  - **Hi-Hats & Cymbals**: Fire ultra-fast 30-40Hz stroboscopic micro-sparkles on rolls and triplets.
  - **Heavy Drops**: Trigger full blinding-white inverted lightning storms.
- **Hyper-Fast Cooldowns**: Drops refractory cooldown to 0.035s (~28 beats/sec), catching rapid-fire 16th/32nd note drum rolls.

---

## Multi-Computer Bluetooth and Network Sync

Run colors across multiple PCs and laptops in the same space to synchronize all screens to the exact same beat over Bluetooth or Local Area Network (LAN).

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

---

## Static Solid Color Lighting Mode (Hotkeys O / 5 / Z)

colors includes a dedicated static lighting system that transforms displays and peripherals into continuous ambient room lighting:
- **1-Click Music vs Solid Toggle**: Click `[LIGHT] SOLID` / `[LIGHT] MUSIC` on the HUD or press **`O`** to immediately toggle between static illumination and audio-reactive strobe mode.
- **Interactive Color Swatches Bar**: 14 hand-crafted vibrant color chips directly on the HUD (Pure Red, Orange Neon, Amber Gold, Electric Yellow, Lime Green, Mint Cyan, Sky Blue, Deep Blue, Violet, Magenta Pink, Hot Pink, Warm White, Pure White).
- **Decoupled Detection Engine**: Engaging or disengaging light mode does not alter or reset your underlying `colors2.0` or `colors1.0` engine selection.
- **Continuous Peripheral Illumination**: Peripherals and room LED strips remain steadily lit without flickering, fading, or strobe blackout cuts.

---

## Controls and Shortcuts

| Key | Action | Description |
| :--- | :--- | :--- |
| **`ESC`** | **Exit / Close Modal** | Closes telemetry console or active modal, or exits the application safely. |
| **`~`**, **`F12`**, or **`G`** | **Toggle Telemetry Console** | Opens / closes real-time logic and math telemetry HUD console log. |
| **`2`** or **`W`** | **colors2.0 Engine** | Selects or toggles colors2.0 Smart Rhythm engine (PLL Grid + 808 isolation). |
| **`3`** or **`E`** | **colors1.0 Engine** | Selects or toggles colors1.0 Classic Rapid strobe engine (unconstrained raw peaks). |
| **`5`**, **`O`**, or **`Z`** | **Toggle Solid Color Light** | Toggles between ambient room illumination and music-reactive strobing. |
| **`1`** or **`Q`** | **Toggle Bass Only Mode** | Toggles pure bass strobe (only reacts to kicks, 808s, and sub-bass). |
| **`4`** or **`R`** | **Toggle Red Only Mode** | Toggles pure crimson red strobe flashes on all beats. |
| **`A`** | **Toggle Album Art Mode** | Toggles strobe mode & palette sync to currently playing album cover art. |
| **`X`** | **Toggle CRAZY OVERDRIVE** | Instantly toggles Crazy Overdrive strobe on/off. |
| **`C`** | **Toggle Razer Chroma** | Toggles hardware RGB lighting sync for Razer keyboards & mice. |
| **`L`** | **Toggle Room Lights** | Toggles Bluetooth BLE room light strip synchronization (HappyLighting). |
| **`K`** | **Toggle Legion PC RGB** | Toggles Lenovo Legion gaming desktop PC RGB lighting. |
| **`N`** | **Bluetooth Sync Modal** | Opens the Multi-Computer Host & Client sync panel. |
| **`F`** or **`F11`** | **Display Mode** | Cycles: Dual Monitor Fullscreen to Monitor 1 to Monitor 2 to Windowed. |
| **`B`** | **Dual FX Scheme** | Cycles: Dual Synced to Ping-Pong Alternating to Complementary Contrast to Panoramic. |
| **`H`** or **`TAB`** | **Toggle HUD** | Shows or hides the control overlay (HUD auto-fades after 3.5s of mouse inactivity). |
| **`M`** | **Cycle Strobe Mode** | Cycles through strobe modes. |
| **`P`** | **Cycle Palette / Solid Color** | Cycles palettes in music mode, or cycles solid colors when solid lighting is active. |
| **`V`** | **Cycle Visual Style** | Solid Fullscreen to Radial Shockwave to Horizon Pulse. |
| **`D`** | **Switch Audio Source** | Cycles between System Audio Loopback, Monitors, and Microphones. |
| **`S`** | **Safe Mode Toggle** | Toggles gentle pulsing glow vs intense hard strobe. |
| **`T`** | **Demo Mode Toggle** | Synthesizes an electronic beat to test visuals without music. |
| **`UP` / `DOWN`** | **Sensitivity** | Increases or decreases beat detection sensitivity. |
| **`[` / `]`** or **`PgUp` / `PgDn`** | **Pre-Amp Boost** | Adjusts input AGC gain multiplier (0.5x to 8.0x) for soft/loud audio sources. |
| **`RIGHT` / `LEFT`** | **Decay Speed** | Adjusts how fast flashes fade out (snappy strobe vs lingering rave glow). |
| **`SPACE`** | **Manual Flash** | Forces an instant kick beat flash. |
