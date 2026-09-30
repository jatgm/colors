# ⚡ Beat Strobe - Dual Monitor & Multi-Computer Bluetooth Audio Visualizer

A high-performance real-time desktop application that turns your monitor(s) and connected computers into a dynamic music-synchronized strobe light show. It captures system audio (Spotify, YouTube, VLC, browser, games, etc.) or microphone input using WASAPI loopback, analyzes frequency bands and spectral flux with FFT, and strobes colors across **both monitors in seamless borderless fullscreen**, with **Bluetooth & Network Multi-Computer Synchronization** and **Extreme Overdrive Strobe Modes**.

---

## 🔥 CRAZY OVERDRIVE MODE (Hotkey `X`)

Turn your displays into an intense underground festival strobe rig:
- **Stroboscopic Burst Trains (Machine-Gun Multi-Flash)**: Instead of a single pulse, each beat fires a rapid train of 3 to 5 micro-flashes at 35Hz (like a professional Martin Atomic 3000 club strobe fixture).
- **All-Frequency Multi-Band Triggering**:
  - **Kicks (Sub-Bass)**: Detonate deep color blasts with screen impact shake!
  - **Snares & Claps**: Fire high-brightness phosphor-white accent explosions!
  - **Hi-Hats & Cymbals**: Fire ultra-fast 30-40Hz stroboscopic micro-sparkles on rolls and triplets!
  - **Heavy Drops**: Trigger full blinding-white inverted lightning storms!
- **Hyper-Fast Cooldowns**: Drops refractory cooldown to 0.035s (~28 beats/sec), catching rapid-fire 16th/32nd note drum rolls and techno drops!
- **Ping-Pong Alternating Blitz**: On dual monitors, left and right screens alternate micro-bursts at blistering speeds!

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
- Broadcasts beat pulses, color palettes, strobe modes, and BPM to all connected computers.
- Opens a direct **Bluetooth RFCOMM Server** (Channel 4) and a **Local Network Server** (Port 42424), broadcasting beacons every 1.5 seconds.
- Displays your computer's local Bluetooth address (e.g. `34:C9:3D:20:5D:40`) and number of connected computers.

#### 2. Client Mode (Any other laptop / PC)
- Switch to the **Client** tab.
- Automatically searches for nearby / paired **Bluetooth Devices** and **Network Host Beacons**.
- Click **Connect** on the detected Host (or click **`⌨ Enter Host IP / MAC`**).
- Local audio processing pauses on the client, and all screens on the client machine strobe in **sub-millisecond lockstep** with the Host!

---

## 🖥 Multi-Monitor Setup (Dual Screens)

The program automatically detects all connected monitors (e.g. two 1920x1080 monitors) and defaults to **Dual Monitor Fullscreen (3840x1080)**.

### 🎭 Dual-Monitor Visual Schemes (Press `B` or `2`):
1. **Dual Synced**: Both monitors strobe identical vibrant colors in lockstep. Effects are centered individually on each screen to avoid bezel splits.
2. **Ping-Pong Alternating**: Left and right monitors take turns flashing on consecutive beats (Kick 1 hits Left, Kick 2 hits Right).
3. **Complementary Contrast**: Left monitor flashes Palette Color A while Right monitor flashes Palette Color B (e.g. Neon Pink on Left, Electric Cyan on Right).
4. **Panoramic Ultra-Wide**: Spans the entire 3840x1080 canvas as one colossal ultra-wide rave display.

---

## 🎨 Strobe Modes (Press `M` to Cycle)

1. **🔥 Psycho Overdrive (Ultra)**: The craziest mode — machine-gun multi-flash bursts, rapid complementary neon flips, hi-hat sparkles, and drop blitzes!
2. **⚡ Machine-Gun Multi-Band**: Kicks, snares, and hi-hats all excite their own independent strobe layers simultaneously.
3. **💥 Hyper Strobe Blitz**: High-frequency concert strobe simulation with instantaneous blackouts.
4. **Hard Strobe (Classic Rave)**: Instant high-intensity color flash on every kick beat, decaying rapidly to pitch black.
5. **Kick + Snare Dual**: Bass kick fires primary palette color; snare/clap fires a bright lightning-white accent strobe.
6. **Smooth Rave Pulse**: Sinusoidal ambient glow that pulses gently with the music without harsh flickers.
7. **Audio Reactive Spectrum**: Real-time continuous color synthesis based on live audio frequencies.
8. **Chaos Blitz**: High-energy randomized neon color bursts on every transient drop.
9. **Monochrome Blitz**: Pure high-contrast black and white strobe flashes.

---

## 🐍 Razer Chroma Hardware RGB Lighting (Hotkey `C`)

Beat Strobe connects directly to your connected **Razer Keyboards and Mice** to flash and strobe their RGB lighting in real-time synchronization with your screen!

- **Zero-Dependency Native Control**: Communicates directly through Windows native `hid.dll` and `setupapi.dll` using custom 90-byte Razer HID feature reports. **No Synapse installation or third-party SDK required!**
- **Supported Hardware**:
  - **Keyboards**: Razer Ornata V2, BlackWidow series, Huntsman series, Cynosa, DeathStalker, etc.
  - **Mice**: Razer Viper series, DeathAdder series, Basilisk series, Cobra, Naga, etc.
  - **Accessories**: Firefly mousepads, Chroma headsets, and ARGB controllers.
- **Dual-Monitor Channel Splitting**:
  - In **Dual Synced** mode, both your keyboard and mouse strobe the exact same colors as your screens.
  - In **Ping-Pong Alternating** or **Complementary Contrast** modes, your **keyboard maps to the Left monitor** and your **mouse maps to the Right monitor**—creating an astonishing physical light show on your desk where beats bounce between your monitors, keyboard, and mouse!
- **Asynchronous <1ms Sub-Millisecond USB Dispatch**: Non-blocking background worker thread guarantees zero frame drops or lag on your 120 FPS screen strobing.

---

## 🎮 Controls & Shortcuts

| Key | Action | Description |
| :--- | :--- | :--- |
| **`ESC`** | **Exit / Close Modal** | Closes active modal or exits the application safely. |
| **`X`** | **🔥 Toggle CRAZY MODE** | Instantly toggles Crazy Overdrive strobe on/off. |
| **`C`** | **🐍 Toggle Razer Chroma** | Toggles hardware RGB lighting sync for Razer keyboards & mice. |
| **`N`** | **Bluetooth Sync Modal** | Opens the Multi-Computer Host & Client Bluetooth panel. |
| **`F`** or **`F11`** | **Display Mode** | Cycles: *Dual Monitor Fullscreen (3840x1080)* $\to$ *Monitor 1* $\to$ *Monitor 2* $\to$ *Windowed*. |
| **`B`** or **`2`** | **Dual FX Scheme** | Cycles: *Dual Synced* $\to$ *Ping-Pong Alternating* $\to$ *Complementary Contrast* $\to$ *Panoramic*. |
| **`H`** or **`TAB`** | **Toggle HUD** | Shows or hides the control overlay (HUD auto-fades after 3.5s of mouse inactivity). |
| **`M`** | **Cycle Strobe Mode** | Cycles through 9 strobe modes. |
| **`P`** | **Cycle Palette** | Switches between 9 color palettes. |
| **`V`** | **Cycle Visual Style** | Solid Fullscreen $\leftrightarrow$ Radial Shockwave $\leftrightarrow$ Horizon Pulse. |
| **`D`** | **Switch Audio Source** | Cycles between System Audio Loopback, Monitors, and Microphones. |
| **`S`** | **Safe Mode Toggle** | Toggles gentle pulsing glow vs intense hard strobe. |
| **`T`** | **Demo Mode Toggle** | Synthesizes a 128 BPM electronic beat to test visuals without music. |
| **`↑` / `↓`** | **Sensitivity** | Increases or decreases beat detection sensitivity. |
| **`[` / `]`** or **`PgUp` / `PgDn`** | **Pre-Amp Boost** | Adjusts input AGC gain multiplier (0.5x to 8.0x) for soft/loud audio sources. |
| **`→` / `←`** | **Decay Speed** | Adjusts how fast flashes fade out (snappy strobe vs lingering rave glow). |
| **`SPACE`** | **Manual Flash** | Forces an instant kick beat flash. |

