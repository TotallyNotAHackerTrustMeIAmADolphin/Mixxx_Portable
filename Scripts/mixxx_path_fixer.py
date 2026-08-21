import sqlite3
import os
import sys
import shutil
import datetime
import glob
import socket
import time
import subprocess

# --- UTILITIES ---

def log(message, data_dir=None):
    """Prints to console and appends to a log file."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] {message}"
    print(message)
    if data_dir:
        log_file = os.path.join(data_dir, "launcher_log.txt")
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(formatted_msg + "\n")
        except: pass

def mixxx_normalize_path(path_str):
    if not path_str: return ""
    path_str = path_str.replace('\\', '/')
    if len(path_str) >= 2 and path_str[1] == ':':
        path_str = path_str[0].upper() + path_str[1:]
    return path_str

def read_last_root(data_dir):
    """Reads the portable root recorded by write_last_root() on a previous run, or None if no sidecar exists yet."""
    path = os.path.join(data_dir, ".mixxx_last_root")
    try:
        with open(path, "r", encoding="utf-8") as f:
            root = f.read().strip()
        return root or None
    except Exception:
        return None

def write_last_root(data_dir, root):
    """Records the current portable root, so the next run knows exactly what to substitute without guessing."""
    path = os.path.join(data_dir, ".mixxx_last_root")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(root + "\n")
    except Exception:
        pass

def is_mixxx_running(data_dir=None):
    try:
        if sys.platform == "win32":
            cmd = 'tasklist /FI "IMAGENAME eq mixxx.exe" /FO CSV /NH'
            output = subprocess.check_output(cmd, shell=True).decode('utf-8', 'ignore')
            return "mixxx.exe" in output.lower()
        else:
            # Exact-name match for a native install.
            result = subprocess.run(['pgrep', '-x', 'mixxx'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                return True
            # Full-command-line match on the Flatpak app ID (not the bare
            # word "mixxx") for the sandboxed case, e.g. "flatpak run
            # org.mixxx.Mixxx". Matching on 'mixxx' alone here would also
            # match this very script's own process, since its command line
            # is "python3 .../mixxx_path_fixer.py ..." — a false positive
            # that would block every single launch.
            result = subprocess.run(['pgrep', '-f', 'org.mixxx.Mixxx'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return result.returncode == 0
    except Exception as e:
        # Fail open (assume not running) so a transient pgrep/tasklist error
        # doesn't hard-block every launch, but at least leave a trace of why
        # the process guard couldn't actually verify anything this time.
        log(f"⚠️  Could not verify whether Mixxx is already running: {e}", data_dir)
        return False

def acquire_session_lock(data_dir, hostname):
    """Atomically claims Mixxx_Data/.mixxx_is_active. Returns (True, None) if
    claimed, or (False, holder_hostname) if another session already holds it.

    One file, one atomic claim, serves two purposes depending on who holds
    it: a same-hostname holder means two near-simultaneous launches raced
    (or a crash left a stale lock behind) — verifiable locally via
    is_mixxx_running(), so safe to auto-heal. A different-hostname holder
    means another machine had this open last and its cloud sync might not
    have caught up — NOT verifiable locally, so this always requires a
    deliberate manual decision (see the load-time caller). os.O_CREAT|O_EXCL
    is atomic, so two near-simultaneous claims can't both succeed.
    """
    lock_path = os.path.join(data_dir, ".mixxx_is_active")
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w") as f:
            f.write(f"{hostname}\n{datetime.datetime.now().isoformat()}\n")
        return True, None
    except FileExistsError:
        try:
            with open(lock_path, "r") as f:
                holder = f.readline().strip()
        except Exception:
            holder = None
        return False, holder

def release_session_lock(data_dir):
    lock_path = os.path.join(data_dir, ".mixxx_is_active")
    if os.path.exists(lock_path):
        try: os.remove(lock_path)
        except: pass

# --- DATABASE LOGIC ---

def check_db_integrity(db_path, data_dir):
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0: return True
    try:
        conn = sqlite3.connect(db_path, timeout=15.0)
        res = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
        return res[0] == "ok"
    except: return False

def optimize_db(db_path, data_dir):
    """Performs maintenance to keep the library fast."""
    log("⚡ Optimizing database for performance...", data_dir)
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.execute("PRAGMA optimize")
        conn.execute("VACUUM")
        conn.close()
        log("✅ Optimization complete.", data_dir)
    except Exception as e:
        log(f"⚠️ Optimization skipped: {e}", data_dir)

def get_old_root_from_db(db_path):
    """LEGACY FALLBACK ONLY — used at most once per install, when no
    .mixxx_last_root sidecar is found (see read_last_root()). Heuristically
    infers the old root by scanning 'directories' rows ending in '/Music'.
    If more than one candidate exists (e.g. a nested folder also happens to
    be named 'Music'), the shortest/outermost candidate is preferred, since
    a genuinely nested Music-named subfolder always produces a longer path
    than the true library root."""
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0: return None
    try:
        conn = sqlite3.connect(db_path, timeout=15.0)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='directories'")
        if not cur.fetchone():
            conn.close()
            return None
        cur.execute("SELECT directory FROM directories")
        rows = cur.fetchall()
        conn.close()
        candidates = []
        for (path_str,) in rows:
            if not path_str: continue
            p = path_str.replace('\\', '/')
            if p.endswith('/Music'): candidates.append(p[:-6])
        if candidates:
            return min(candidates, key=len)
    except Exception: pass
    return None

def substitute_path_prefix(db_path, old_prefix, new_prefix, data_dir):
    """Replace old_prefix with new_prefix across all path columns, anchored
    at an exact match or a '/' boundary (never a bare substring match).
    Pure Python row-by-row comparison — no SQL LIKE, so no wildcard-escaping
    surface regardless of what old_prefix/new_prefix contain. Returns the
    number of rows changed."""
    if not old_prefix or old_prefix == new_prefix or not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        return 0
    total = 0
    boundary_prefix = old_prefix + "/"
    targets = [("track_locations", "location"), ("track_locations", "directory"),
               ("LibraryHashes", "directory_path"), ("directories", "directory")]
    try:
        conn = sqlite3.connect(db_path, timeout=15.0)
        cur = conn.cursor()
        for table, col in targets:
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            if not cur.fetchone():
                continue
            cur.execute(f"SELECT rowid, {col} FROM {table}")
            updates = []
            for rowid, val in cur.fetchall():
                if not val:
                    continue
                if val == old_prefix:
                    updates.append((new_prefix, rowid))
                elif val.startswith(boundary_prefix):
                    updates.append((new_prefix + val[len(old_prefix):], rowid))
            if updates:
                cur.executemany(f"UPDATE {table} SET {col} = ? WHERE rowid = ?", updates)
                total += len(updates)
        conn.commit()
        conn.close()
    except Exception as e:
        log(f"Database Error during path substitution: {e}", data_dir)
    return total

def get_external_tracks(db_path, current_root):
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0: return []
    external = []
    try:
        conn = sqlite3.connect(db_path, timeout=15.0)
        cur = conn.cursor()
        # Check if tables exist
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='track_locations'")
        if not cur.fetchone():
            conn.close()
            return []

        query = """
            SELECT tl.id, l.artist, l.title, tl.location
            FROM track_locations tl
            LEFT JOIN library l ON l.location = tl.id
        """
        cur.execute(query)
        # Filter in Python rather than SQL LIKE: current_root can contain
        # '_' or '%' (both SQL wildcards), which would otherwise make LIKE
        # match paths that merely resemble the portable root instead of
        # actually being inside it (e.g. ".../My_Drive" matching
        # ".../MyXDrive" since '_' matches any single character).
        prefix = current_root + "/"
        external = [row for row in cur.fetchall() if not (row[3] or "").startswith(prefix)]
        conn.close()
    except Exception: pass
    return external

def get_missing_library_tracks(db_path, current_root):
    """Tracks whose path is INSIDE the portable Music/ root but whose file
    does not exist on this filesystem. Distinct from get_external_tracks(),
    which only ever looks at paths outside Music/ — a file deleted (or not
    yet synced down by Dropbox/OneDrive) from inside Music/ never shows up
    there and would otherwise go completely undetected."""
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0: return []
    missing = []
    try:
        conn = sqlite3.connect(db_path, timeout=15.0)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='track_locations'")
        if not cur.fetchone():
            conn.close()
            return []
        query = """
            SELECT tl.id, l.artist, l.title, tl.location
            FROM track_locations tl
            LEFT JOIN library l ON l.location = tl.id
        """
        cur.execute(query)
        prefix = current_root + "/Music/"
        for row in cur.fetchall():
            loc = row[3] or ""
            if loc.startswith(prefix) and not os.path.exists(loc):
                missing.append(row)
        conn.close()
    except Exception: pass
    return missing

def handle_missing_library_tracks(db_path, current_root, data_dir):
    missing = get_missing_library_tracks(db_path, current_root)
    if not missing: return

    log(f"\n⚠️  Found {len(missing)} tracks inside Music/ that no longer exist on disk:", data_dir)
    for _, artist, title, path in missing:
        log(f"   - {artist or 'Unknown'} - {title or 'Unknown'} ({path})", data_dir)
    log("\n💡 A file shows up here if it was deleted, OR if a cloud-sync backend", data_dir)
    log("   (Dropbox/OneDrive) hasn't finished downloading it to this machine yet.", data_dir)
    log("   Only remove entries you're sure are actually gone, not just still syncing.", data_dir)

    choice = input(f"\nRemove these {len(missing)} entries from the database? (y/N): ").lower()
    if choice == 'y':
        try:
            conn = sqlite3.connect(db_path, timeout=30.0)
            cur = conn.cursor()
            for tl_id, _, _, _ in missing:
                cur.execute("DELETE FROM library WHERE location = ?", (tl_id,))
                cur.execute("DELETE FROM track_locations WHERE id = ?", (tl_id,))
            conn.commit()
            conn.close()
            log("✅ Database entries removed.", data_dir)
        except Exception as e:
            log(f"❌ Error removing tracks: {e}", data_dir)

def handle_external_tracks(db_path, current_root, data_dir):
    external = get_external_tracks(db_path, current_root)
    if not external: return

    reachable = [t for t in external if os.path.exists(t[3])]
    missing = [t for t in external if t not in reachable]

    if missing:
        log(f"\n⚠️  Found {len(missing)} tracks NOT PRESENT ON THIS PC (other host or deleted):", data_dir)
        for _, artist, title, path in missing:
            log(f"   - {artist or 'Unknown'} - {title or 'Unknown'} ({path})", data_dir)

    if reachable:
        log(f"\n⚠️  Found {len(reachable)} tracks located outside the portable drive on this PC:", data_dir)
        for _, artist, title, path in reachable:
            log(f"   - {artist or 'Unknown'} - {title or 'Unknown'} ({path})", data_dir)

    # 1. Ingest (Copy) - Only for reachable tracks
    if reachable:
        choice = input(f"\nCopy {len(reachable)} reachable tracks to portable Music/_Imported/? (y/N): ").lower()
        if choice == 'y':
            import_dir = os.path.join(current_root, "Music", "_Imported")
            os.makedirs(import_dir, exist_ok=True)
            conn = sqlite3.connect(db_path, timeout=30.0)
            copied = 0
            try:
                cur = conn.cursor()
                for tl_id, artist, title, old_path in reachable:
                    filename = os.path.basename(old_path)
                    new_path = os.path.join(import_dir, filename)

                    # Handle collisions: keep trying suffixes until the name
                    # is free, so 3+ colliding files can't clobber each other
                    # (a fixed one-shot timestamp suffix could still collide
                    # if multiple files are processed within the same second).
                    if os.path.exists(new_path):
                        name, ext = os.path.splitext(filename)
                        counter = 1
                        while os.path.exists(new_path):
                            new_path = os.path.join(import_dir, f"{name}_{counter}{ext}")
                            counter += 1

                    log(f"🚚 Copying: {filename}...", data_dir)
                    shutil.copy2(old_path, new_path)

                    # Update DB and commit immediately, so a failure on a
                    # later track can't leave an already-copied file with a
                    # stale DB pointer still stuck on the old external path.
                    norm_new_path = mixxx_normalize_path(new_path)
                    norm_new_dir = mixxx_normalize_path(os.path.dirname(new_path))
                    cur.execute("UPDATE track_locations SET location = ?, directory = ? WHERE id = ?",
                               (norm_new_path, norm_new_dir, tl_id))
                    conn.commit()
                    copied += 1
                log(f"✅ Ingest complete. {copied}/{len(reachable)} tracks imported.", data_dir)
            except Exception as e:
                log(f"❌ Error during import ({copied}/{len(reachable)} completed before failure): {e}", data_dir)
            finally:
                conn.close()

    # 2. Cleanup (Remove) - Re-fetch list to prevent stale data.
    # Only offer removal for tracks NOT reachable on this PC (zombie entries
    # from another host or genuinely deleted files). Reachable tracks the
    # user just declined to ingest still exist on disk and must be left
    # alone, or their Mixxx metadata (cues, ratings, play history) would be
    # destroyed even though the file itself is fine.
    external = get_external_tracks(db_path, current_root)
    missing = [t for t in external if not os.path.exists(t[3])]
    if missing:
        log(f"\nℹ️  The following {len(missing)} tracks are still not present on this PC:", data_dir)
        for _, artist, title, path in missing:
            log(f"   - {artist or 'Unknown'} - {title or 'Unknown'} ({path})", data_dir)

        choice = input(f"\nRemove these {len(missing)} entries from the database? (y/N): ").lower()
        if choice == 'y':
            try:
                conn = sqlite3.connect(db_path, timeout=30.0)
                cur = conn.cursor()
                for tl_id, _, _, _ in missing:
                    cur.execute("DELETE FROM library WHERE location = ?", (tl_id,))
                    cur.execute("DELETE FROM track_locations WHERE id = ?", (tl_id,))
                conn.commit()
                conn.close()
                log("✅ Database entries removed.", data_dir)
            except Exception as e:
                log(f"❌ Error removing tracks: {e}", data_dir)

def validate_library(db_path, current_root, data_dir):
    external = get_external_tracks(db_path, current_root)
    missing_in_library = get_missing_library_tracks(db_path, current_root)
    if not external and not missing_in_library: return

    reachable = [t for t in external if os.path.exists(t[3])]
    missing = [t for t in external if t not in reachable]

    if missing:
        log(f"\n⚠️  WARNING: {len(missing)} tracks are NOT PRESENT ON THIS PC (on another machine or deleted):", data_dir)
        for _, artist, title, path in missing:
            log(f"   - {artist or 'Unknown'} - {title or 'Unknown'} ({path})", data_dir)

    if reachable:
        log(f"\n⚠️  WARNING: {len(reachable)} tracks are located outside the portable drive found on this PC:", data_dir)
        for _, artist, title, path in reachable:
            log(f"   - {artist or 'Unknown'} - {title or 'Unknown'} ({path})", data_dir)
        log("\n💡 Tip: Close Mixxx and run 'save' to fix reachable tracks automatically.\n", data_dir)

    if missing_in_library:
        log(f"\n⚠️  WARNING: {len(missing_in_library)} tracks inside Music/ no longer exist on disk:", data_dir)
        for _, artist, title, path in missing_in_library:
            log(f"   - {artist or 'Unknown'} - {title or 'Unknown'} ({path})", data_dir)
        log("\n💡 Could be a deleted file, or a cloud-sync backend still catching up.", data_dir)
        log("   Close Mixxx and run 'save' if you want to remove confirmed-deleted entries.\n", data_dir)

# --- MAIN ENGINE ---

def fix_paths(data_dir, to_os, mode="load"):
    data_dir = os.path.abspath(data_dir)
    os.makedirs(data_dir, exist_ok=True)
    
    # Process Protection + Cloud-Sync Protection ("The Dirty Flag")
    #
    # One atomic lock file (Mixxx_Data/.mixxx_is_active) serves both jobs,
    # branching on WHO holds it — because that's what determines whether a
    # stale lock is safe to clear automatically:
    #   - Same hostname: either two near-simultaneous launches on this
    #     machine raced (e.g. a double-click), or a crash left a stale lock
    #     behind. Locally verifiable via is_mixxx_running(), so safe to
    #     auto-heal.
    #   - Different hostname: another machine had this open last and its
    #     cloud sync might not have caught up yet. NOT locally verifiable —
    #     this script has no way to know a remote machine's sync state — so
    #     it always requires a deliberate manual decision. No keystroke
    #     override: a one-key "proceed anyway" next to a warning is exactly
    #     the kind of prompt people blow through on autopilot, and doing so
    #     here can silently clobber real work (cue points, hot cues,
    #     playlist edits).
    hostname = socket.gethostname().lower()
    sync_lock = os.path.join(data_dir, ".mixxx_is_active")

    if mode == "load":
        if is_mixxx_running(data_dir):
            log("\n❌ ERROR: MIXXX IS ALREADY RUNNING!\n")
            input("Press Enter to exit...")
            sys.exit(1)

        claimed, holder = acquire_session_lock(data_dir, hostname)
        if not claimed:
            if holder == hostname:
                if is_mixxx_running(data_dir):
                    log("\n❌ ERROR: MIXXX IS ALREADY RUNNING!\n")
                    input("Press Enter to exit...")
                    sys.exit(1)
                release_session_lock(data_dir)
                claimed, holder = acquire_session_lock(data_dir, hostname)
                if not claimed:
                    log("\n❌ ERROR: ANOTHER LAUNCH IS ALREADY IN PROGRESS!\n")
                    input("Press Enter to exit...")
                    sys.exit(1)
            else:
                log(f"⚠️  Locked by: {holder}", data_dir)
                log(f"Delete {sync_lock} once you've confirmed it's synced, then relaunch.", data_dir)
                sys.exit(1)

    # Path Resolution
    portable_root_abs = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    current_root = mixxx_normalize_path(portable_root_abs)
    current_music_dir = f"{current_root}/Music"
    # A dedicated subfolder, not the library root itself — recordings are
    # session captures, not library tracks, and dumping them directly into
    # Music/ would mix them in with (and get them scanned as) real tracks.
    current_recordings_dir = f"{current_music_dir}/Recordings"

    db_path = os.path.join(data_dir, "mixxxdb.sqlite")
    cfg_active = os.path.join(data_dir, "mixxx.cfg")
    config_dir = os.path.join(data_dir, "Configs")
    backup_dir = os.path.join(data_dir, "Backups")
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(backup_dir, exist_ok=True)
    os.makedirs(os.path.join(current_root, "Music", "Recordings"), exist_ok=True)

    log(f"--- Mixxx Sync [{to_os.upper()} | {hostname}] ---", data_dir)

    if mode == "save":
        if os.path.exists(cfg_active):
            shutil.copy2(cfg_active, os.path.join(config_dir, f"mixxx.cfg.{hostname}"))
        handle_external_tracks(db_path, current_root, data_dir)
        handle_missing_library_tracks(db_path, current_root, data_dir)
        optimize_db(db_path, data_dir)
        write_last_root(data_dir, current_root)
        release_session_lock(data_dir)
        log(f"[SUCCESS] Session closed cleanly.", data_dir)
        return

    # 1. Database Check
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        log("ℹ️  No database found. Mixxx will create a new one.", data_dir)
    elif not check_db_integrity(db_path, data_dir):
        log("❌ DATABASE CORRUPTION DETECTED", data_dir)
        backups = sorted(glob.glob(os.path.join(backup_dir, f"mixxxdb_{hostname}_*.sqlite")))
        if backups and input(f"Restore latest backup ({os.path.basename(backups[-1])})? (y/N): ").lower() == 'y':
            shutil.copy2(backups[-1], db_path)
            if not check_db_integrity(db_path, data_dir):
                log("❌ Restored backup also failed the integrity check. Aborting.", data_dir)
                input("Press Enter to exit...")
                sys.exit(1)
        else: sys.exit(1)

    # 2. Hardware Restore
    machine_cfg = os.path.join(config_dir, f"mixxx.cfg.{hostname}")
    os_template = os.path.join(config_dir, f"mixxx.cfg.{to_os[:3].lower()}")
    if os.path.exists(machine_cfg):
        shutil.copy2(machine_cfg, cfg_active)
    elif os.path.exists(os_template):
        shutil.copy2(os_template, cfg_active)

    # 3. Session Backup
    if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(db_path, os.path.join(backup_dir, f"mixxxdb_{hostname}_{ts}.sqlite"))
        for old in sorted(glob.glob(os.path.join(backup_dir, f"mixxxdb_{hostname}_*.sqlite")))[:-10]:
            try:
                os.remove(old)
            except Exception as e:
                log(f"⚠️ Could not prune old backup {os.path.basename(old)}: {e}", data_dir)

    # 4. Database Migration
    if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
        old_root = read_last_root(data_dir)
        if not old_root:
            # No sidecar yet: brand-new DB, or a legacy (pre-feature) install
            # that hasn't been through a sidecar-aware run before. One-time
            # bootstrap only — the moment this load succeeds, the sidecar is
            # written below and this fallback is never needed again.
            old_root = get_old_root_from_db(db_path)
            if old_root:
                log(f"No path-tracking sidecar found; inferred old root from DB: {old_root}", data_dir)

        if old_root and old_root != current_root:
            rows_changed = substitute_path_prefix(db_path, old_root, current_root, data_dir)
            log(f"Migrating DB: {old_root} -> {current_root} ({rows_changed} path(s) updated)", data_dir)

    write_last_root(data_dir, current_root)

    # 5. Config Migration
    # mixxx.cfg has exactly one Directory value and one RecordingDirectory
    # value, so unlike the DB there's nothing ambiguous to infer — just
    # unconditionally set both to the current root. This also fixes a
    # separate bug the old detect-then-replace approach had: it applied
    # `l.replace(old_cfg_root, current_root) if old_cfg_root in l else l`
    # to EVERY line in the file, so any unrelated value that happened to
    # contain the old root as a substring got silently corrupted too.
    if os.path.exists(cfg_active):
        try:
            with open(cfg_active, 'r', encoding='utf-8', errors='ignore') as f: lines = f.readlines()
            new_lines, has_dir, has_rec, changed = [], False, False, False
            library_header_idx = None
            for l in lines:
                if l.startswith("Directory "):
                    new_line = f"Directory {current_music_dir}\n"
                    changed = changed or new_line != l
                    new_lines.append(new_line); has_dir = True
                elif l.startswith("RecordingDirectory "):
                    new_line = f"RecordingDirectory {current_recordings_dir}\n"
                    changed = changed or new_line != l
                    new_lines.append(new_line); has_rec = True
                else:
                    new_lines.append(l)
                    if l.strip() == "[Library]":
                        library_header_idx = len(new_lines) - 1
            if not has_dir or not has_rec:
                changed = True
                missing = []
                if not has_dir: missing.append(f"Directory {current_music_dir}\n")
                if not has_rec: missing.append(f"RecordingDirectory {current_recordings_dir}\n")
                if library_header_idx is not None:
                    # Insert into the existing [Library] section instead of
                    # appending a second one, which would otherwise create a
                    # duplicate header every time exactly one key is missing.
                    insert_at = library_header_idx + 1
                    new_lines[insert_at:insert_at] = missing
                else:
                    if new_lines and not new_lines[-1].endswith("\n"):
                        new_lines.append("\n")
                    new_lines.append("\n[Library]\n")
                    new_lines.extend(missing)
            if changed:
                with open(cfg_active, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
                log("[SUCCESS] Config paths updated.", data_dir)
        except Exception as e:
            log(f"⚠️ Config path update skipped: {e}", data_dir)

    validate_library(db_path, current_root, data_dir)

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        fix_paths(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "load")