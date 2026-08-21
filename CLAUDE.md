# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mixxx-Anywhere is a portable, logic-driven wrapper for [Mixxx DJ software](https://mixxx.org). It lets a single Mixxx library run identically from a portable drive or cloud-synced folder (Dropbox/OneDrive) across Windows, Linux, and macOS by dynamically rewriting absolute paths and swapping machine-specific hardware configs before/after each launch.

There is no build system, package manager, or test suite — this is a thin OS-launcher + Python migration script around a third-party binary (Mixxx itself must be installed on the host).

## Commands

Run/launch:
- Linux: `./start_smart_linux.sh`
- Windows: `start_smart_windows.bat`
- macOS: `start_smart_macos.sh` (untested)

Manually invoke the path-fixing logic (useful for debugging without launching Mixxx):
- `python3 Scripts/mixxx_path_fixer.py Mixxx_Data linux load` — pre-launch: migrate DB/config paths, restore hardware profile, take a backup.
- `python3 Scripts/mixxx_path_fixer.py Mixxx_Data linux save` — post-close: ingest/cleanup external tracks, save hardware profile, optimize DB, clear the sync lock.

`load`/`save` are the only two modes; `to_os` is one of `windows`/`linux`/`macos` (only the first 3 characters are used, to match `mixxx.cfg.<os>` template filenames).

There are no linters or automated tests configured. Verify changes by running the `load`/`save` commands manually against a copy of `Mixxx_Data/mixxxdb.sqlite` and inspecting `Mixxx_Data/launcher_log.txt`.

## Architecture

Everything hinges on one script: `Scripts/mixxx_path_fixer.py`. Each OS launcher (`start_smart_*.{sh,bat}`) does the same three-step dance:
1. Verify Python 3 and Mixxx are installed on the host.
2. Call `mixxx_path_fixer.py <data_dir> <os> load` to prepare the environment.
3. Launch Mixxx with `--settingsPath` pointed at `Mixxx_Data/`.
4. On exit, call `mixxx_path_fixer.py <data_dir> <os> save` to persist machine-specific state.

Key mechanics inside `fix_paths()`:
- **Path resolution**: the portable root is derived from the script's own location (`dirname(dirname(__file__))`), not a hardcoded path — this is what makes the drive/folder renameable and relocatable. `mixxx_normalize_path()` is the single cross-platform normalizer (forward slashes, uppercase drive letters) and must be used for any path written to the DB or config.
- **Database path substitution**: `Mixxx_Data/.mixxx_last_root` is a sidecar file recording the exact root the DB was last resolved to — written on `load` (and again on `save`, as a redundant safety net). On the next `load`, `substitute_path_prefix()` reads that value back and rewrites the prefix (anchored at an exact match or a `/` boundary, in Python — not SQL `LIKE`) across `track_locations` (location, directory), `LibraryHashes` (directory_path), and `directories` (directory). No guessing involved, since the script wrote the value itself. `get_old_root_from_db()` survives only as a one-time bootstrap fallback for installs with no sidecar yet (pre-feature databases); it scans `directories` for rows ending in `/Music` and prefers the shortest/outermost candidate if more than one exists, but is never consulted again for that install once a sidecar-aware `load` succeeds.
- **Config migration**: `mixxx.cfg`'s `Directory`/`RecordingDirectory` lines are unconditionally overwritten on every `load` — there's exactly one correct value for each, so no old-value detection is needed. `Directory` points at `Music/`; `RecordingDirectory` points at a dedicated `Music/Recordings/` subfolder (created via `os.makedirs` alongside `Configs/`/`Backups/`), not the library root itself, so session recordings don't get mixed in with (and scanned as) real tracks. A missing key is inserted into the existing `[Library]` section if one exists, or a new section is appended if not.
- **Hardware profiles**: `mixxx.cfg` is machine-specific (audio hardware/latency), so the active config is swapped from `Mixxx_Data/Configs/mixxx.cfg.<hostname>` on `load` and saved back there on `save`. If no per-machine config exists yet, it falls back to `mixxx.cfg.<os prefix>` as an OS-level template.
- **Process guard + cloud-sync safety, one lock file**: `load` first checks `is_mixxx_running()` (`pgrep`/`tasklist`), then atomically claims `Mixxx_Data/.mixxx_is_active` via `acquire_session_lock()` (`os.O_CREAT|O_EXCL`). If the claim fails, the file's existing holder hostname decides what happens next — and that branch is the whole reason this is one file instead of two: whether a stale lock is safe to clear automatically depends entirely on whether the script *can* verify the claim is stale.
  - **Same hostname** (two near-simultaneous launches raced, e.g. a double-click, or a crash left a stale lock): locally verifiable via `is_mixxx_running()`, so it's safe to clear and retry once automatically.
  - **Different hostname** (another machine had this open last, its cloud sync might not have caught up): NOT locally verifiable — this script has no way to check a remote machine's sync state — so it always hard-stops with no "proceed anyway" prompt. A one-keystroke override next to a warning is easy to blow through on autopilot (this has caused real data loss); the only way past it is to manually delete the lock file after actually confirming the other machine is synced.
  
  The lock is claimed at the start of `load` and released at the end of `save` via `release_session_lock()`.
- **External track handling**: tracks in the DB outside the portable `Music/` root are split into *reachable* (exists on this filesystem — offered for copy-in to `Music/_Imported/`) vs *missing* (not present here — likely lives only on another host, offered for DB removal). This runs interactively (`input()`) during `save`, and read-only (`validate_library`, warning only) during `load`.
- **Missing in-library track handling**: separately, `get_missing_library_tracks()`/`handle_missing_library_tracks()` catch tracks *inside* `Music/` whose file no longer exists on this filesystem — a case `get_external_tracks()` never sees, since it only looks outside `Music/`. Because `Music/` is the cloud-synced folder itself, "missing" here is ambiguous (genuinely deleted vs. a Dropbox/OneDrive download still in flight), so like external tracks this is warn-only on `load` (folded into `validate_library`) and requires an explicit `y` on `save` before removing DB rows — never auto-deleted.
- **Backups & integrity**: `load` takes a timestamped snapshot into `Mixxx_Data/Backups/` before migrating, keeping the last 10 per hostname (`mixxxdb_<hostname>_*.sqlite`), and runs `PRAGMA integrity_check`, offering restore-from-backup on corruption. `save` runs `PRAGMA optimize` + `VACUUM`.

## Conventions

- All music files must live under `Music/` at the portable root — this is the anchor path resolution and DB rewriting depend on.
- Always normalize paths through `mixxx_normalize_path()` before writing them to the DB or config; never write raw `os.path` output on Windows-style paths.
- Use the module-level `log()` helper (not bare `print`) for anything user-facing — it mirrors output to `Mixxx_Data/launcher_log.txt` when `data_dir` is passed.
- SQLite connections should use a timeout of at least 15s (cloud-sync backends can hold file locks briefly); follow the existing pattern of explicit `conn.close()` rather than leaving connections open.
