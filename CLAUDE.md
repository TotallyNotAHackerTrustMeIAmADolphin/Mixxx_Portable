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
- **Config migration**: `mixxx.cfg`'s `Directory`/`RecordingDirectory` lines are unconditionally overwritten to the current root on every `load` — there's exactly one correct value for each, so no old-value detection is needed. A missing key is inserted into the existing `[Library]` section if one exists, or a new section is appended if not.
- **Hardware profiles**: `mixxx.cfg` is machine-specific (audio hardware/latency), so the active config is swapped from `Mixxx_Data/Configs/mixxx.cfg.<hostname>` on `load` and saved back there on `save`. If no per-machine config exists yet, it falls back to `mixxx.cfg.<os prefix>` as an OS-level template.
- **Cloud-sync safety ("dirty flag")**: `Mixxx_Data/.mixxx_is_active` stores the hostname that last opened the DB. On `load`, if a *different* hostname is found, the user is warned that the other machine may still be mid-sync before proceeding (prevents cloud-sync race conditions clobbering the DB). The lock is written at the start of `load` and removed at the end of `save` — an interrupted session (crash, force-quit) leaves the lock behind and will warn on the next `load` from any machine, including the same one.
- **External track handling**: tracks in the DB outside the portable `Music/` root are split into *reachable* (exists on this filesystem — offered for copy-in to `Music/_Imported/`) vs *missing* (not present here — likely lives only on another host, offered for DB removal). This runs interactively (`input()`) during `save`, and read-only (`validate_library`, warning only) during `load`.
- **Backups & integrity**: `load` takes a timestamped snapshot into `Mixxx_Data/Backups/` before migrating, keeping the last 10 per hostname (`mixxxdb_<hostname>_*.sqlite`), and runs `PRAGMA integrity_check`, offering restore-from-backup on corruption. `save` runs `PRAGMA optimize` + `VACUUM`.
- **Process guard**: `load` refuses to proceed if a `mixxx`/`mixxx.exe` process is already running (`pgrep`/`tasklist`), to avoid two processes writing the same portable DB concurrently.

## Conventions

- All music files must live under `Music/` at the portable root — this is the anchor path resolution and DB rewriting depend on.
- Always normalize paths through `mixxx_normalize_path()` before writing them to the DB or config; never write raw `os.path` output on Windows-style paths.
- Use the module-level `log()` helper (not bare `print`) for anything user-facing — it mirrors output to `Mixxx_Data/launcher_log.txt` when `data_dir` is passed.
- SQLite connections should use a timeout of at least 15s (cloud-sync backends can hold file locks briefly); follow the existing pattern of explicit `conn.close()` rather than leaving connections open.
