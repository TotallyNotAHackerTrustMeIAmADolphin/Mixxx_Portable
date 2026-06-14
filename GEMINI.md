# 🎧 Mixxx-Anywhere: Project Context

Mixxx-Anywhere is a portable, logic-driven wrapper for the [Mixxx DJ software](https://mixxx.org). It enables a fully synced DJ setup across Windows, Linux, and macOS by dynamically reconstructing absolute paths and managing machine-specific hardware configurations.

## 🏗 Project Overview

*   **Goal:** Allow Mixxx to run from a portable drive or cloud-synced folder without track path breakage or hardware conflicts.
*   **Core Technology:** Python 3 (Logic Engine), SQLite (Database manipulation), and OS-specific launcher scripts.
*   **Key Logic:** The `mixxx_path_fixer.py` script identifies the current mount point/drive letter and updates the Mixxx database and configuration files in real-time before launch.

## 📂 Architecture & Key Files

### 🚀 Entry Points
*   `start_smart_win.bat`: Windows launcher. Detects `mixxx.exe` in common installation paths and uses portable Python if available.
*   `start_smart_lin.sh`: Linux launcher. Requires system-wide `python3` and `mixxx` installations.
*   `start_smart_mac.sh`: macOS launcher (Untested).

### 🧠 Logic Engine (`Scripts/`)
*   `mixxx_path_fixer.py`: The heart of the project.
    *   **Path Resolution:** Normalizes paths across different operating systems.
    *   **DB Migration:** Rewrites `location` and `directory` columns in `track_locations`, `LibraryHashes`, and `directories` tables.
    *   **Hardware Profiling:** Saves and restores `mixxx.cfg` based on the current machine's hostname.
    *   **Safety Guards:** Prevents multiple instances and warns about cloud-sync "dirty" states.
    *   **External Track Ingestion:** Detects tracks outside the portable folder and offers to copy them to `Music/_Imported/` or remove them from the database on exit.
    *   **Backups:** Maintains 10 rolling SQLite backups per machine.

### 📊 Data Storage (`Mixxx_Data/`)
*   `mixxxdb.sqlite`: The active Mixxx library database.
*   `mixxx.cfg`: The active configuration file (swapped dynamically).
*   `Configs/`: Stores machine-specific hardware profiles (`mixxx.cfg.<hostname>`).
*   `Backups/`: Stores rolling database backups.
*   `.mixxx_is_active`: A lock file containing the hostname of the current user to prevent sync conflicts.

### 🎵 Media Anchor (`Music/`)
*   All music files **must** be stored here to ensure relative path reconstruction works correctly.
*   `Music/_Imported/`: The default destination for external tracks ingested via the launcher's cleanup process.

## 🛠 Building and Running

This is a wrapper project; it does not "build" in the traditional sense but relies on the host having Mixxx installed.

### Launching
*   **Windows:** Run `start_smart_win.bat`.
*   **Linux:** Run `./start_smart_lin.sh`.
*   **macOS:** Run `./start_smart_mac.sh`.

### Troubleshooting Commands
*   `python3 Scripts/mixxx_path_fixer.py Mixxx_Data [os] load`: Manually trigger the pre-launch path fixing logic.
*   `python3 Scripts/mixxx_path_fixer.py Mixxx_Data [os] save`: Manually trigger the post-close cleanup and optimization.

## 📜 Development Conventions

*   **Pathing:** Always use `mixxx_normalize_path` in Python to ensure cross-platform compatibility (forward slashes, consistent drive letter casing).
*   **SQLite Operations:** Use context managers or ensure connections are closed. Set appropriate timeouts (15s+) to handle potential cloud-sync locks.
*   **Logging:** Use the internal `log()` function to ensure events are captured in `Mixxx_Data/launcher_log.txt`.
*   **Hardware Scrubbing:** When a new machine is detected, the script allows Mixxx to generate a fresh hardware config, which is then saved for that machine upon exit.
