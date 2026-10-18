# SoundClicker

[![Release](https://img.shields.io/badge/Release-v2.2-181B22?style=for-the-badge&logo=github)](https://github.com/Yoepan/SoundClicker/releases/tag/v2.2.0)
[![Platform](https://img.shields.io/badge/Platform-Windows-181B22?style=for-the-badge&logo=windows)](https://github.com/)
[![Python](https://img.shields.io/badge/Python-3.9+-181B22?style=for-the-badge&logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-181B22?style=for-the-badge)](LICENSE)

SoundClicker is an audio-activated automation utility for Windows. It monitors audio output from a target process using real-time FFT pattern recognition and triggers configured mouse actions whenever the target audio cue plays.

<p align="center">
   <img src="https://github.com/user-attachments/assets/8190b941-f269-47fd-a0e7-234ff4c73f60" width="48%" alt="Preview Menu">
   <img src="https://github.com/user-attachments/assets/8c2392a3-0946-4564-9529-a12d0c63cac1" width="48%" alt="Menu Preview Menu Action Macro & Logs">
</p>

## Key Capabilities

- Process Audio Isolation (PID Capture): Captures audio output strictly from the selected application process. Background noise, browser tabs, Discord voice chat, and music do not affect detection.
- Background Window Delivery: Dispatches clicks directly to the target window using native Win32 `PostMessage`. The target window receives inputs without stealing cursor focus or breaking Alt-Tab workflows.
- Visual Coordinate Picker: Click to select Point 1 and Point 2 on your screen. The application automatically resolves target window handles, process identifiers, and client coordinates.
- Multi-Action Macro Sequences: Supports single clicks, double clicks, and two-point sequences (Click 1 -> Delay -> Click 2) with customizable delays and cooldown intervals.
- Idle Auto-Click Fallback: Automatically triggers a fallback action if no click activity occurs for a user-specified duration (in minutes), seamlessly enforcing detection cooldown to prevent false audio re-triggers.
- Anti-Detection Jitter: Randomizes click duration (+/-35 ms) and coordinates (+/-3 px) to prevent identical repeat patterns.
- Hotkey Control: Global shortcut `F6` toggles active listening from within fullscreen or windowed games.
- Pure Monochrome UI: Minimalist dark interface built on CustomTkinter with collapsible controls and optional telemetry logging.

## Quick Start

### Running from Python

1. Clone this repository:
   ```bash
   git clone https://github.com/your-username/SoundClicker.git
   cd SoundClicker
   ```
2. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```
3. Launch the application:
   ```bash
   python main.py
   ```
   Alternatively, run `run.bat` on Windows.

### Workflow

1. Select Sound Cue:
   - Click **Auto-Capture Cue**, switch to your target game, and trigger the sound. The application records the spike, trims silence, and saves the pattern.
   - Or click **Import Audio** to load an existing `.wav` file.
2. Select Window and Position:
   - Click **Pick Point 1**, then click on your target game window.
   - SoundClicker automatically binds the target window handle and assigns PID audio isolation.
3. Configure Macro:
   - Choose action type (Sequence, Single Click, or Double Click).
   - Set delay, cooldown, and optional idle auto-click timeout sliders as needed.
4. Start Detection:
   - Press `F6` or click **START LISTENING (F6)**.

## Compiling to Standalone Executable (.exe)

To compile SoundClicker into a standalone binary:

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Execute the build script:
   ```cmd
   build_exe.bat
   ```
3. The compiled application will be generated in `dist\SoundClicker\SoundClicker.exe` with all audio sample assets copied automatically.

## Project Structure

```text
soundclicker/
├── clicker_engine.py    # Win32 PostMessage input dispatch and click mechanics
├── main.py              # CustomTkinter interface and application coordination
├── sounddetector.py     # Real-time FFT audio cross-correlation and PID capture
├── window_helper.py     # Win32 window enumeration and coordinate resolution
├── build_exe.bat        # Automated PyInstaller build script
├── run.bat              # Quick launch batch script
├── requirements.txt     # Python package dependencies
├── splash_sample.wav    # Sample audio cue
└── LICENSE              # MIT License
```

## System Requirements

- Windows 10 or 11 (64-bit)
- Python 3.9 or higher

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
