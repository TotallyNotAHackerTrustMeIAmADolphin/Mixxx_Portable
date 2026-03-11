# 🎧 Mixxx-Anywhere: Portable & Machine-Aware Sync

A robust solution for running a **Mixxx** DJ setup from a portable drive (USB/SSD) or a synced cloud folder (Dropbox/OneDrive) across multiple computers and operating systems (**Windows & Linux**) without losing track analysis, cues, playlists, or audio hardware settings.

---

## 🛠 The Problem vs. The Solution

### The Problem
1.  **Paths:** Mixxx uses absolute paths (e.g., `C:\Users\Name\Music\...`). Move to another computer or Linux, and your library "breaks."
2.  **Hardware:** Every computer has different soundcards and latency capabilities. A Windows ASIO config will crash a Linux machine, and a Laptop’s buffer settings will likely be too high/low for a Studio PC.

### The Solution
The **Smart Launcher** handles the "surgery" before Mixxx starts:
*   **Machine-Specific Hardware:** It detects the unique **Hostname** of the computer and loads/saves a dedicated hardware config for *that specific machine*.
*   **Path Reconstruction:** It rewrites the SQLite database in real-time to match the current drive letter or mount point.
*   **Rolling Backups:** It maintains a self-cleaning history of your database, tagged by machine name and timestamp.
*   **The Anchor System:** By keeping all music in a relative `/Music` folder, it ensures 100% portability.

---

## 📂 Folder Structure
```text
/Mixxx_Portable/
├── start_smart_win.bat   # Windows Entry Point
├── start_smart_lin.sh    # Linux Entry Point
├── Music/                # THE ANCHOR: Put all your audio files here
├── Mixxx_Data/           # Your settingsPath folder
│   ├── mixxxdb.sqlite    # The ACTIVE Library Database
│   ├── mixxx.cfg         # The ACTIVE config (overwritten on launch)
│   ├── Configs/          # Machine-specific hardware settings
│   │   ├── mixxx.cfg.win      # Windows Generic Template
│   │   ├── mixxx.cfg.lin      # Linux Generic Template
│   │   ├── mixxx.cfg.dj-lap   # Specific settings for "DJ-LAP"
│   │   └── mixxx.cfg.studio   # Specific settings for "STUDIO"
│   └── Backups/          # Rolling DB backups (e.g., mixxxdb_dj-lap_20240311.sqlite)
└── Scripts/              
    └── mixxx_path_fixer.py   # The logic engine
```

---

## 🚀 Setup Guide

### 1. Initial Preparation
1.  **Install Mixxx** on your machines (Windows/Linux).
2.  **Copy this Repository** to your portable drive or cloud folder.
3.  **Move your Music:** Place all your tracks inside the `/Music` folder.
4.  **Move existing data (Optional):** If you have an existing library, copy `mixxxdb.sqlite` into `Mixxx_Data/`.

### 2. The First Run
1.  Launch the script for your OS (`.bat` or `.sh`).
2.  Mixxx will open with a "blank" or "default" hardware config.
3.  **Configure your Hardware:** Go to Preferences -> Sound Hardware. Set up your Soundcard, Latency, and Controllers.
4.  **Set Music Folder:** When Mixxx asks, point the library to the `/Music` folder inside this portable directory.
5.  **Close Mixxx:** The script will automatically detect your computer's name and save your settings into `Mixxx_Data/Configs/mixxx.cfg.[your-hostname]`.

---

## 🎵 The "Golden Rule"
To ensure sync works, you **must** follow this rule:
> **All music files must stay inside the `/Music` folder on your portable drive.**

If you add a track from a computer's local "Downloads" or "Desktop" folder, the script cannot "fix" it. When you switch to another computer, that track will be missing. 

---

## 🔄 Daily Workflow

1.  **Plug in** your drive.
2.  **Launch** via `start_smart_win.bat` or `start_smart_lin.sh`.
3.  **The Script will:**
    *   Create a timestamped backup in `/Backups`.
    *   Identify your machine and swap in your saved hardware config from `/Configs`.
    *   Fix all file paths in the database to match the current drive.
4.  **DJ Session:** Play, analyze tracks, and create playlists as usual.
5.  **Close Mixxx:** The launcher will save any hardware changes (new MIDI maps, latency tweaks) back to your machine-specific config file.

---

## ⚠️ Important Rules

*   **Rescan on Startup:** Keep "Rescan on Startup" **OFF** in Mixxx preferences. Let the script finish its work before Mixxx scans. If you added new music, use **Right Click Tracks -> Rescan Library**.
*   **Closing Mixxx:** Always let the terminal window (the script) finish its "Saving" process after you close Mixxx before unplugging your drive.
*   **Linux Permissions:** On Linux, ensure the script is executable: `chmod +x start_smart_lin.sh`.

---

## Future Plans & Work in Progress

### 🛡️ Improvement Suggestions (Stability & Safety)

1.  **macOS Support (The Missing Link):**
    *   **The Suggestion:** You have Windows and Linux covered (and our new backup system is already future-proofed to tag `mac` files!). Adding a `start_smart_mac.sh` would make this truly universal. 
    *   **Technical Tip:** macOS usually mounts external drives under `/Volumes/DRIVE_NAME/`. Your path-rewriting logic needs to account for this specific prefix.

2.  **Graceful Error Handling for "Locked" Databases:**
    *   **The Problem:** If Mixxx didn't close properly, the `.sqlite-journal` file might exist, and your script might fail to open the DB.
    *   **The Fix:** Add logic to check for journal files and warn the user (or wait for them to clear) before attempting the path-swap.

3.  **Expanded Logging & Transparency:**
    *   **The Suggestion:** The script currently prints path reconstruction success and backup timestamps. Expanding this to show exactly how many tracks were updated would be a great UX boost.
    *   *Example Output:* `[SUCCESS] Updated 1,240 track paths | Swapped to Windows ASIO config.`

---

### ✨ Feature Requests (New Functionality)

1.  **"Pre-Flight" Path Validator:**
    *   **The Feature:** A script that scans the database and warns the user if any tracks are located **outside** the `/Music` anchor folder.
    *   **Why:** This prevents users from accidentally adding a song from their "Downloads" folder, which will break the next time they use a different computer.

2.  **Relative Pathing for Playlists (M3U Export):**
    *   **The Feature:** An option to export all Mixxx playlists to standard `.m3u` files with relative paths within the portable folder.
    *   **Why:** This allows the user to play their music in other apps (like VLC or a phone) directly from the same USB drive.

3.  **Binary Download Helper:**
    *   **The Feature:** A `setup_binaries.py` script.
    *   **Why:** Since you can't distribute the Mixxx `.exe` easily via GitHub due to size/licensing, a script that fetches the latest stable ZIP from Mixxx.org and extracts it into a `/bin` folder would make the "Zero-Install" experience much smoother.

4.  **"Dry Run" Mode:**
    *   **The Feature:** A flag (e.g., `start_smart_win.bat --debug`) that shows what paths *would* be rewritten without actually changing the database.
    *   **Why:** Extremely helpful for users trying to debug why their library isn't syncing correctly on a new Linux distro.

5.  **Cloud-Sync Status Checker:**
    *   **The Feature:** If the user is using Dropbox/OneDrive, the script checks if `mixxxdb.sqlite` is currently "Syncing" (locked by the cloud client) before launching.
    *   **Why:** Prevents "Conflicted Copy" files which can result in lost DJ sets/history.

---

## 📜 License
This project is licensed under the **GPL-3.0**. 

> 🐬 *Trust me, I'm a dolphin. Your database is in safe fins.*

