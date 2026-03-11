# 🎧 Mixxx-Anywhere: Portable & Machine-Aware Sync

A robust, professional-grade solution for running a **Mixxx** DJ setup from a portable drive (USB/SSD) or a synced cloud folder (Dropbox/OneDrive) across multiple computers and operating systems (**Windows & Linux**). 

This project ensures that your track analysis, cues, playlists, and even specific audio hardware settings (latency, soundcard IDs) follow you everywhere without "Missing Track" errors or database corruption.

---

## 🛠 The Problem vs. The Solution

### The Problem
*   **Absolute Paths:** Mixxx stores track locations as absolute paths (e.g., `C:\Users\Name\Music\...`). If your USB drive letter changes or you move to Linux, your library breaks.
*   **Hardware Conflicts:** Every computer has different audio hardware. Loading a Windows ASIO config on a Linux machine (ALSA/Pulse) often causes Mixxx to crash or reset your settings.
*   **Human Error:** It’s easy to accidentally add a song from your "Downloads" folder, which then goes missing when you change machines.

### The Solution
The **Smart Launcher** acts as a "logic bridge" that prepares your environment before Mixxx opens:
*   **Machine-Specific Hardware:** Identifies your computer by its **Hostname** and swaps in a dedicated hardware configuration.
*   **Path Reconstruction:** Rewrites the SQLite database and `mixxx.cfg` in real-time to match the current drive's mount point.
*   **Safety Net:** Detects database locks (from crashes) and validates that all your music is actually on the portable drive.

---

## 📂 Folder Structure
```text
/Mixxx_Portable/
├── start_smart_win.bat   # Windows Entry Point
├── start_smart_lin.sh    # Linux Entry Point
├── Music/                # THE ANCHOR: Put ALL your audio files here
├── Mixxx_Data/           # Your settingsPath folder
│   ├── mixxxdb.sqlite    # The ACTIVE Library Database
│   ├── mixxx.cfg         # The ACTIVE config (swapped per session)
│   ├── Configs/          # Machine-specific hardware backups
│   │   ├── mixxx.cfg.win      # Windows Generic Template
│   │   ├── mixxx.cfg.lin      # Linux Generic Template
│   │   ├── mixxx.cfg.dj-lap   # Specific settings for machine "DJ-LAP"
│   │   └── mixxx.cfg.studio   # Specific settings for machine "STUDIO"
│   └── Backups/          # Rolling DB backups (10 per machine)
└── Scripts/              
    └── mixxx_path_fixer.py   # The Python logic engine
```

---

## 🚀 Setup Guide

### 1. Initial Preparation
1.  **Install Mixxx** normally on your Windows and Linux machines.
2.  **Clone/Copy this Repo** to your portable drive.
3.  **Move your Music:** Place all your tracks inside the `/Music` folder.
4.  **Initial Setup:** On the first run on a new machine, launch via the `.bat` or `.sh` file. Configure your **Sound Hardware** (Latency, Soundcards) and **Library Location** (point it to the `/Music` folder).
5.  **Save:** When you close Mixxx, the script will automatically save those settings into `Mixxx_Data/Configs/` using that computer's name.

---

## 🛡️ Smart Features

### 1. The "Pre-Flight" Validator
Before Mixxx launches, the script scans your database. If it finds tracks located on the host computer (e.g., `C:\Users\Admin\Desktop`) instead of your portable folder, it displays a high-visibility warning in the terminal. This allows you to fix your library *before* you get to a gig.

### 2. Lock & Crash Detection
If Mixxx crashed previously, SQLite "lock" files (`.journal` or `.wal`) might remain. The script detects these and warns you, preventing the corruption that happens when writing to a locked database.

### 3. Detailed Logging
The script provides transparency, reporting exactly how many database rows were updated and how many configuration lines were fixed to match the current drive.

### 4. Rolling Backups
The script maintains the last **10 versions** of your database *per machine*. If your database ever gets corrupted, you can easily restore a recent version from the `/Backups` folder.

---

## 🎵 The "Golden Rule"
To ensure your library stays synced, you **must** follow this rule:
> **All music files must stay inside the `/Music` folder on your portable drive.**

If you add music from your computer's local folders, the script cannot "fix" them for other machines.

---

## 🔄 Daily Workflow
1.  **Plug in** your drive.
2.  **Launch** via `start_smart_win.bat` or `start_smart_lin.sh`.
3.  **The Script** identifies your machine, swaps your hardware settings, fixes your paths, and checks for errors.
4.  **Mixxx opens.** Use it as normal.
5.  **Close Mixxx.** The script saves your updated hardware settings back to your machine-specific config file in `/Configs`.

---

## 🛠 Future Plans & WIP

*   **macOS Support:** Adding logic for `/Volumes/` pathing and a Mac-specific launcher.
*   **Controller Mapping Sync:** A dedicated folder to manage and sync custom `.xml` and `.js` MIDI mappings across machines.
*   **Cloud-Sync Status Checker:** A feature to detect if a cloud client (like Dropbox) is currently uploading the database to prevent "Conflicted Copy" data loss.
*   **Binary Download Helper:** A script to download a portable Mixxx executable directly to the drive for a true "zero-install" experience.

---

## 📜 License
This project is licensed under the **GPL-3.0**. 

> 🐬 *Trust me, I'm a dolphin. Your database is in safe fins.*