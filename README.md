# 🎧 Mixxx-Anywhere: Professional Portable & Cloud Sync

**Mixxx-Anywhere** is a robust, logic-driven wrapper for the [Mixxx DJ software](https://mixxx.org). It allows you to run a fully synced DJ setup from a portable drive (USB/SSD) or a cloud-synced folder (Dropbox/OneDrive) across **Windows, Linux, and macOS** without ever seeing a "Missing Track" error or a database crash.

## 🌟 Why use this?

Mixxx traditionally stores paths as "Absolute Paths" (e.g., `C:\Users\DJ\Music\...`). If you move your drive to a different computer where the drive letter changes, or switch to Linux where paths look like `/media/dj/...`, your entire library breaks.

**Mixxx-Anywhere solves this by:**
1.  **Dynamic Path Reconstruction:** Identifies your current location and rewrites the SQLite database and `mixxx.cfg` in real-time.
2.  **Hardware Awareness:** Saves unique audio hardware settings (latency, soundcard IDs) for every computer you use.
3.  **Corruption Safeguards:** Includes a Process Guard, an Integrity Checker, and a Multi-Device Sync Guard.

---

## 🚀 Key Features

*   **Structure-Based Detection:** Rename your portable folder to anything you like. The script dynamically deduces the root by locating your `/Music` anchor.
*   **Multi-Device Sync Guard:** Prevents "Conflicted Copy" disasters. If you try to open Mixxx while the database is still in use (or hasn't finished syncing) from another machine, the script will warn you.
*   **Lightning-Fast Library:** Automatically performs database maintenance (`VACUUM` and `ANALYZE`) every time you close Mixxx to keep search results instant.
*   **Smart Hardware Scrub:** On a brand-new computer, the script "scrubs" the audio hardware config to prevent OS crashes while keeping your UI, mappings, and playlists intact.
*   **Integrity Guard:** Detects database corruption and offers instant restoration from the last healthy backup.
*   **Session Logging:** Records every path migration and update in `launcher_log.txt` for easy troubleshooting.

---

## 📂 Folder Structure

```text
/Your_Portable_Drive/
├── start_smart_win.bat   # Windows Entry Point
├── start_smart_lin.sh    # Linux Entry Point
├── start_smart_mac.sh    # macOS Entry Point
├── Music/                # THE ANCHOR: Put ALL your audio files here
├── Mixxx_Data/           # Your portable settingsPath folder
│   ├── mixxxdb.sqlite    # The ACTIVE Library Database
│   ├── mixxx.cfg         # The ACTIVE config
│   ├── launcher_log.txt  # Activity log (migrations, updates, errors)
│   ├── .mixxx_is_active  # Sync Guard (hidden file)
│   ├── controllers/      # Your custom MIDI mappings
│   ├── Configs/          # Machine-specific hardware backups
│   └── Backups/          # Rolling DB backups (10 per machine)
└── Scripts/              
    ├── mixxx_path_fixer.py   # The Logic Engine
    └── python_win/           # (Optional) Portable Python for Windows
```

---

## 🏃‍♂️ Quick Start

1.  **Copy this project** to your USB drive or Dropbox folder.
2.  **Move your tracks** into the `/Music` folder.
3.  **Launch** using the `start_smart` file for your current OS.
4.  **First Run:**
    *   Mixxx will open with a clean audio config.
    *   Set your **Sound Hardware** (latency, inputs/outputs).
    *   When you close Mixxx, the script saves these settings specifically for *this* computer.

---

## ⚠️ The "Golden Rule"

To keep your library 100% synced, you **must** follow this rule:
> **All music files must stay inside the `/Music` folder on your portable drive.**

---

## 🔍 Troubleshooting

| Message | Meaning | Fix |
| :--- | :--- | :--- |
| `❌ ERROR: MIXXX IS ALREADY RUNNING` | You tried to open a second instance. | Close the other Mixxx window first. |
| `⚠️ CLOUD-SYNC WARNING` | The database was last used on a different machine and might still be syncing. | Ensure the other machine has finished uploading to Dropbox/OneDrive before clicking 'y'. |
| `❌ DATABASE CORRUPTION DETECTED` | The database file is unreadable. | Choose 'y' to restore the latest backup. |
| `⚡ Optimizing database...` | Maintenance mode. | This keeps your library fast. Let it finish before ejecting your drive. |
| `ℹ️ NO DATABASE FOUND` | You deleted the DB or this is a fresh install. | Normal. Mixxx will generate a new library on launch. |

---

## 📂 Manual Database Restoration

If you need to roll back your library to a specific point in time:

1.  **Close Mixxx** and the Smart Launcher.
2.  **Locate your Backups:** Navigate to `/Mixxx_Data/Backups/` and find the file with the desired timestamp.
3.  **Rename the Current DB:** Rename `/Mixxx_Data/mixxxdb.sqlite` to `mixxxdb.sqlite.old`.
4.  **Restore:** Copy your chosen backup into `/Mixxx_Data/` and rename it to **`mixxxdb.sqlite`**.
5.  **Launch:** Run your `start_smart` launcher. The script will automatically update the paths to match your current computer.

---

## 📜 License
This project is licensed under the **GPL-3.0**. 

> 🐬 *Trust me, I'm a dolphin. Your database is in safe fins.*