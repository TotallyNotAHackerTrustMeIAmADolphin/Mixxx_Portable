# 🎧 Mixxx-Anywhere: Professional Portable & Cloud Sync

**Mixxx-Anywhere** is a robust, logic-driven wrapper for the [Mixxx DJ software](https://mixxx.org). It allows you to run a fully synced DJ setup from a portable drive (USB/SSD) or a cloud-synced folder (Dropbox/OneDrive) across **Windows, Linux, and macOS** without ever seeing a "Missing Track" error or a database crash.

## 🌟 Why use this?

Mixxx traditionally stores paths as "Absolute Paths" (e.g., `C:\Users\DJ\Music\...`). If you move your drive to a different computer where the drive letter changes, or switch to Linux where paths look like `/media/dj/...`, your entire library breaks.

**Mixxx-Anywhere solves this by:**
1.  **Dynamic Path Reconstruction:** It identifies your current location and rewrites the SQLite database and `mixxx.cfg` in real-time before Mixxx opens.
2.  **Hardware Awareness:** It saves unique audio hardware settings (latency, soundcard IDs) for every computer you use, so you don't have to reconfigure your setup every time you switch machines.
3.  **Corruption Safeguards:** It includes a Process Guard (prevents multiple instances) and an Integrity Checker (safeguards against cloud-sync data corruption).

---

## 🚀 Key Features

*   **Structure-Based Detection:** You can rename your portable folder to anything you like. The script dynamically deduces the root by locating your `/Music` anchor.
*   **Smart Hardware Scrub:** If you launch on a brand-new computer, the script "scrubs" only the audio hardware section of the config to prevent OS crashes, while keeping your UI, mappings, and playlists intact.
*   **Rolling Backups:** Maintains the last 10 versions of your database *per machine*.
*   **Integrity Guard:** Automatically detects if Dropbox/OneDrive caused a database "Conflicted Copy" or corruption and offers an instant restoration from the last healthy backup.
*   **Process Guard:** Prevents launching a second instance of Mixxx, which is the leading cause of portable database corruption.

---

## 📂 Folder Structure

```text
/Your_Portable_Drive/
├── start_smart_win.bat   # Windows Entry Point
├── start_smart_lin.sh    # Linux Entry Point
├── start_smart_mac.sh    # macOS Entry Point (UNTESTED)
├── Music/                # THE ANCHOR: Put ALL your audio files here
├── Mixxx_Data/           # Your portable settingsPath folder
│   ├── mixxxdb.sqlite    # The ACTIVE Library Database
│   ├── mixxx.cfg         # The ACTIVE config (swapped per session)
│   ├── controllers/      # Your custom MIDI mappings
│   ├── Configs/          # Machine-specific hardware backups (.yoga, .studio-pc, etc)
│   └── Backups/          # Rolling DB backups (10 per machine)
└── Scripts/              
    ├── mixxx_path_fixer.py   # The Logic Engine
    └── python_win/           # (Optional) Portable Python for Windows
```

---

## 🛠 Prerequisites

### **Windows**
*   This repo usually includes a `python_win` folder. If not, install [Python 3](https://www.python.org/downloads/windows/) and ensure "Add to PATH" is checked.
*   Install Mixxx in the default location (`C:\Program Files\Mixxx`).

### **Linux (Ubuntu/Debian/Pop!_OS)**
*   Ensure Python 3 is installed: `sudo apt install python3`
*   Ensure Mixxx is installed: `sudo add-apt-repository ppa:mixxx/mixxx && sudo apt update && sudo apt install mixxx`

### **macOS**
*   **Permissions:** Go to *System Settings > Privacy & Security > Files and Folders* and ensure **Mixxx** has permission to access **Removable Volumes**.

---

## 🏃‍♂️ Quick Start

1.  **Copy this project** to your USB drive or Dropbox folder.
2.  **Move your tracks** into the `/Music` folder.
3.  **Launch** using the `start_smart` file for your current OS.
4.  **First Run:**
    *   Mixxx will open with a clean audio config.
    *   Set your **Sound Hardware** (latency, inputs/outputs).
    *   When you close Mixxx, the script will automatically save these settings for *this specific computer*.
5.  **Future Runs:** Just double-click the launcher. All your cues, loops, and hardware settings will be ready instantly.

---

## ⚠️ The "Golden Rule"

To keep your library 100% synced, you **must** follow this rule:
> **All music files must stay inside the `/Music` folder on your portable drive.**

If you add music from your computer's local "Downloads" or "Desktop" folders, the script will detect them as "External Tracks" and warn you, as they will not work when you move to another computer.

---

## 🔍 Troubleshooting

| Message | Meaning | Fix |
| :--- | :--- | :--- |
| `❌ ERROR: MIXXX IS ALREADY RUNNING` | You tried to open a second instance. | Close the other Mixxx window first. |
| `❌ DATABASE CORRUPTION DETECTED` | The database file is unreadable (often due to a sync error). | Choose 'y' when prompted to restore the latest backup. |
| `⚠️ EXTERNAL TRACKS DETECTED` | Some songs are stored on the host PC, not the USB. | Move those songs into the `/Music` folder on the USB and re-add them. |
| `Sanitizing hardware config...` | You are on a new PC or OS. | This is normal. Just set your soundcard settings once; they will be remembered for next time. |

---

## 📂 Manual Database Restoration

If the automated restoration fails, or if you simply want to roll back your library to a specific point in time (e.g., "how it looked last Tuesday"), you can manually restore a backup.

### **Restoration Steps:**

1.  **Close Mixxx:** Ensure Mixxx and the Smart Launcher are completely closed.
2.  **Locate your Backups:** 
    *   Navigate to the `/Mixxx_Data/Backups/` folder on your portable drive.
    *   Look for the file with the most recent date/time in the name: `mixxxdb_[MachineName]_[YYYYMMDD_HHMMSS].sqlite`.
3.  **Rename the "Broken" Database:** 
    *   Go back to the `/Mixxx_Data/` folder.
    *   Find the active `mixxxdb.sqlite` file and rename it to `mixxxdb.sqlite.old`. This is your safety net.
4.  **Restore the Backup:**
    *   Copy the backup file you chose in Step 2 from the `/Backups/` folder.
    *   Paste it into the main `/Mixxx_Data/` folder.
    *   Rename that file to exactly: **`mixxxdb.sqlite`**
5.  **Launch:**
    *   Run your `start_smart` launcher. The script will detect the "new" database and automatically update the paths to match your current computer.

> [!TIP]
> **Which backup should I choose?**
> The backups are named by **Hostname** (the computer name) and **Timestamp**. If you just had a crash on your laptop, look for the file starting with your laptop's name with the most recent time.

--- 

### **Why are there multiple backups?**
The script keeps the **last 10 backups for every machine** you use. This means if you use a Studio PC and a DJ Laptop, you will see 10 backups for each. This ensures that if a database gets corrupted on one machine and synced via Dropbox, you can still find a healthy version from either device.

---

## 📜 License
This project is licensed under the **GPL-3.0**. 

> 🐬 *Trust me, I'm a dolphin. Your database is in safe fins.*