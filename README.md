# 🎧 Mixxx-Anywhere: Professional Portable & Cloud Sync

**Mixxx-Anywhere** is a robust, logic-driven wrapper for the [Mixxx DJ software](https://mixxx.org). It allows you to run a fully synced DJ setup from a portable drive (USB/SSD) or a cloud-synced folder (Dropbox/OneDrive) across **Windows, Linux, and macOS** without ever seeing a "Missing Track" error or a database crash.

## 🌟 Why use this?

Mixxx traditionally stores paths as "Absolute Paths" (e.g., `C:\Users\DJ\Music\...`). If you move your drive to a different computer where the drive letter changes, or switch to Linux where paths look like `/media/dj/...`, your entire library breaks.

**Mixxx-Anywhere solves this by:**
1.  **Dynamic Path Reconstruction:** Identifies your current location and rewrites the SQLite database and `mixxx.cfg` in real-time.
2.  **Hardware Awareness:** Saves unique audio hardware settings (latency, soundcard IDs) for every computer you use.
3.  **Cloud-Sync Safety:** Prevents data loss caused by "Conflicted Copies" when Dropbox/OneDrive hasn't finished syncing between machines.

---

## 🚀 Key Features

*   **Structure-Based Detection:** Rename your portable folder to anything you like — the script locates itself on disk to determine the current root, then tracks the exact previous root via a small sidecar file (`.mixxx_last_root`), so there's never any guessing involved in the migration.
*   **Cloud-Sync "Dirty Flag":** Detects if the database was last used on a different machine, and refuses to open until you confirm it's safe by manually deleting the lock file — there's no "proceed anyway" keystroke to blow through by accident, since doing that can silently overwrite real work (cue points, hot cues, playlist edits) if the other machine's sync hasn't caught up yet.
*   **External Track Protection:** Detects tracks added from outside your portable drive. It distinguishes between tracks reachable on the current PC (offers to "ingest" them) and tracks "NOT PRESENT ON THIS PC" (zombie entries from other hosts).
*   **Performance Optimization:** Automatically triggers `VACUUM` and `PRAGMA optimize` on exit to keep library searches lightning-fast.
*   **Smart Hardware Scrub:** On brand-new computers, the script "scrubs" only the audio hardware section of the config to prevent OS crashes.
*   **Process Guard:** Prevents launching a second instance of Mixxx — the leading cause of portable database corruption — using both a running-process check and an atomic lock file, closing the gap between two near-simultaneous launches (e.g. a double-click).
*   **Session Logging:** Maintains a `launcher_log.txt` for easy debugging of path migrations.

---

## 📂 Folder Structure

```text
/Your_Portable_Drive/
├── start_smart_windows.bat   # Windows Entry Point
├── start_smart_linux.sh      # Linux Entry Point
├── start_smart_macos.sh      # macOS Entry Point
├── Music/                # THE ANCHOR: Put ALL your audio files here
│   └── _Imported/        # Auto-created for ingested external tracks
├── Mixxx_Data/           # Your portable settingsPath folder
│   ├── mixxxdb.sqlite    # The ACTIVE Library Database
│   ├── mixxx.cfg         # The ACTIVE config (swapped per session)
│   ├── launcher_log.txt  # History of path migrations
│   ├── .mixxx_is_active  # Hidden sync-protection flag
│   ├── .mixxx_launch.lock # Hidden lock preventing double-launches
│   ├── .mixxx_last_root  # Hidden sidecar tracking the exact last-used root
│   ├── controllers/      # Your custom MIDI mappings
│   ├── Configs/          # Machine-specific hardware backups
│   └── Backups/          # Rolling DB backups (10 per machine)
└── Scripts/              
    ├── mixxx_path_fixer.py   # The Logic Engine
    └── python_win/           # (Optional) Portable Python for Windows
```

---

## 🛠 Prerequisites

### **Windows**
*   Install Mixxx in the default location (`C:\Program Files\Mixxx`).
*   Ensure the `python_win` folder exists in `Scripts/` or install Python 3.

### **Linux (Ubuntu/Debian/Pop!_OS)**
*   **Install Python 3:** `sudo apt install python3`
*   **Install Mixxx:** `sudo add-apt-repository ppa:mixxx/mixxx && sudo apt update && sudo apt install mixxx`
*   **Permissions:** Open a terminal in your portable folder and run:
    `chmod +x start_smart_linux.sh`

### **macOS**
*   **Install Mixxx:** Download from [mixxx.org](https://mixxx.org/download/).
*   **Permissions:** Open a terminal in your portable folder and run:
    `chmod +x start_smart_macos.sh`
*   **System Privacy:** Go to *System Settings > Privacy & Security > Files and Folders* and ensure **Mixxx** has permission to access **Removable Volumes**.

---

## 🏃‍♂️ Quick Start

1.  **Copy this project** to your USB drive or Dropbox folder.
2.  **Move your tracks** into the `/Music` folder.
3.  **Launch** using the `start_smart` file for your current OS.
4.  **Select library** on the first start Mixxx prompts you to select a library folder. Select the `/Music`folder.
5.  **Use Mixxx as usual** Set your **Sound Hardware**. When you close Mixxx, the script saves these settings for *this specific computer*.

---

## ⚠️ The "Golden Rule"

To keep your library 100% synced, you **must** follow this rule:
> **All music files must stay inside the `/Music` folder on your portable drive.**

---

## 🔍 Troubleshooting

| Message | Meaning | Fix |
| :--- | :--- | :--- |
| `❌ ERROR: MIXXX IS ALREADY RUNNING` | A Mixxx process is already active. | Close all Mixxx windows. |
| `❌ ERROR: ANOTHER LAUNCH IS ALREADY IN PROGRESS` | Two launches were started at nearly the same time (e.g. a double-click), or a previous session crashed before closing cleanly. | Wait a moment and try again; if it persists after confirming Mixxx isn't actually running, delete `Mixxx_Data/.mixxx_launch.lock`. |
| `⚠️ CLOUD-SYNC WARNING` | Database was last used on [Machine X]. There is no "proceed anyway" prompt — this is intentional, since a quick keystroke here can silently overwrite recent work. | Confirm [Machine X] has fully finished uploading to the cloud (no pending sync), then manually delete `Mixxx_Data/.mixxx_is_active` and re-launch. |
| `❌ DATABASE CORRUPTION DETECTED` | The file is unreadable. | Choose 'y' to restore the latest backup. |
| `ℹ️ NO DATABASE FOUND` | You deleted the DB or this is a fresh install. | Mixxx will create a new one on launch. |
| `⚠️ TRACKS OUTSIDE DRIVE` | Reachable tracks found on the host PC. | Close Mixxx to trigger the Auto-Ingest prompt. |
| `⚠️ NOT PRESENT ON THIS PC` | Tracks from another host PC (missing here). | Close Mixxx to trigger the Cleanup prompt. |

---

## 📂 Manual Database Restoration

1.  **Close Mixxx** and the Smart Launcher.
2.  **Navigate to `/Mixxx_Data/Backups/`** and find the most recent healthy `.sqlite` file for your machine.
3.  **Copy it** into `/Mixxx_Data/`.
4.  **Delete the broken `mixxxdb.sqlite`** and rename your copy to `mixxxdb.sqlite`.
5.  **Launch** the script; it will automatically update the paths in the restored file.

---

## 🛠 Future Plans & WIP

*   **M3U Playlist Export:** Automatically generate portable relative-path playlists for use in VLC or mobile apps.
*   **Binary Download Helper:** A "Zero-Install" script to download portable Mixxx binaries directly to the drive.
*   **GUI Wrapper:** A simple visual interface to replace the terminal window.
*   **Automatic Offsite Backups:** Integration with Backblaze/S3 for secondary library protection.

---

## 📜 License
This project is licensed under the **GPL-3.0**. 

> 🐬 *Trust me, I'm a dolphin. Your database is in safe fins.*
