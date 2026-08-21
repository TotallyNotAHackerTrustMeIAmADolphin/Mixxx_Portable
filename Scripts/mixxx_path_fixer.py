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

def is_mixxx_running():
    try:
        if sys.platform == "win32":
            cmd = 'tasklist /FI "IMAGENAME eq mixxx.exe" /FO CSV /NH'
            output = subprocess.check_output(cmd, shell=True).decode('utf-8', 'ignore')
            return "mixxx.exe" in output.lower()
        else:
            result = subprocess.run(['pgrep', '-x', 'mixxx'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return result.returncode == 0
    except: return False

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
        for (path_str,) in rows:
            if not path_str: continue
            p = path_str.replace('\\', '/')
            if p.endswith('/Music'): return p[:-6]
    except Exception: pass
    return None

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
            WHERE tl.location NOT LIKE ?
        """
        cur.execute(query, (f"{current_root}%",))
        external = cur.fetchall()
        conn.close()
    except Exception: pass
    return external

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
            try:
                conn = sqlite3.connect(db_path, timeout=30.0)
                cur = conn.cursor()
                for tl_id, artist, title, old_path in reachable:
                    filename = os.path.basename(old_path)
                    new_path = os.path.join(import_dir, filename)
                    
                    # Handle collisions
                    if os.path.exists(new_path):
                        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        name, ext = os.path.splitext(filename)
                        new_path = os.path.join(import_dir, f"{name}_{ts}{ext}")
                    
                    log(f"🚚 Copying: {filename}...", data_dir)
                    shutil.copy2(old_path, new_path)
                    
                    # Update DB
                    norm_new_path = mixxx_normalize_path(new_path)
                    norm_new_dir = mixxx_normalize_path(os.path.dirname(new_path))
                    cur.execute("UPDATE track_locations SET location = ?, directory = ? WHERE id = ?", 
                               (norm_new_path, norm_new_dir, tl_id))
                conn.commit()
                conn.close()
                log("✅ Ingest complete. Database updated.", data_dir)
            except Exception as e:
                log(f"❌ Error during import: {e}", data_dir)

    # 2. Cleanup (Remove) - Re-fetch list to prevent stale data
    external = get_external_tracks(db_path, current_root)
    if external:
        log(f"\nℹ️  The following {len(external)} tracks are still external or missing:", data_dir)
        for _, artist, title, path in external:
            log(f"   - {artist or 'Unknown'} - {title or 'Unknown'} ({path})", data_dir)
            
        choice = input(f"\nRemove these {len(external)} entries from the database? (y/N): ").lower()
        if choice == 'y':
            try:
                conn = sqlite3.connect(db_path, timeout=30.0)
                cur = conn.cursor()
                for tl_id, _, _, _ in external:
                    cur.execute("DELETE FROM library WHERE location = ?", (tl_id,))
                    cur.execute("DELETE FROM track_locations WHERE id = ?", (tl_id,))
                conn.commit()
                conn.close()
                log("✅ Database entries removed.", data_dir)
            except Exception as e:
                log(f"❌ Error removing tracks: {e}", data_dir)

def validate_library(db_path, current_root, data_dir):
    external = get_external_tracks(db_path, current_root)
    if not external: return

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

# --- MAIN ENGINE ---

def fix_paths(data_dir, to_os, mode="load"):
    data_dir = os.path.abspath(data_dir)
    os.makedirs(data_dir, exist_ok=True)
    
    # Process Protection
    if mode == "load" and is_mixxx_running():
        log("\n❌ ERROR: MIXXX IS ALREADY RUNNING!\n")
        input("Press Enter to exit...")
        sys.exit(1)

    # Cloud-Sync Protection (The Dirty Flag)
    sync_lock = os.path.join(data_dir, ".mixxx_is_active")
    hostname = socket.gethostname().lower()

    if mode == "load" and os.path.exists(sync_lock):
        with open(sync_lock, "r") as f: last_machine = f.read().strip()
        if last_machine != hostname:
            log("\n" + "!"*60)
            log(f"⚠️  CLOUD-SYNC WARNING")
            log(f"The database was last used on: {last_machine}")
            log("If that machine is still syncing, you may lose data!")
            log("!"*60)
            if input("Proceed anyway? (y/N): ").lower() != 'y': sys.exit(1)

    # Path Resolution
    portable_root_abs = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    current_root = mixxx_normalize_path(portable_root_abs)
    current_music_dir = f"{current_root}/Music"
    
    db_path = os.path.join(data_dir, "mixxxdb.sqlite")
    cfg_active = os.path.join(data_dir, "mixxx.cfg")
    config_dir = os.path.join(data_dir, "Configs")
    backup_dir = os.path.join(data_dir, "Backups")
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(backup_dir, exist_ok=True)

    log(f"--- Mixxx Sync [{to_os.upper()} | {hostname}] ---", data_dir)

    if mode == "save":
        if os.path.exists(cfg_active):
            shutil.copy2(cfg_active, os.path.join(config_dir, f"mixxx.cfg.{hostname}"))
        handle_external_tracks(db_path, current_root, data_dir)
        optimize_db(db_path, data_dir)
        if os.path.exists(sync_lock): os.remove(sync_lock)
        log(f"[SUCCESS] Session closed cleanly.", data_dir)
        return

    # Create lock file
    with open(sync_lock, "w") as f: f.write(hostname)

    # 1. Database Check
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        log("ℹ️  No database found. Mixxx will create a new one.", data_dir)
    elif not check_db_integrity(db_path, data_dir):
        log("❌ DATABASE CORRUPTION DETECTED", data_dir)
        backups = sorted(glob.glob(os.path.join(backup_dir, f"mixxxdb_{hostname}_*.sqlite")))
        if backups and input(f"Restore latest backup ({os.path.basename(backups[-1])})? (y/N): ").lower() == 'y':
            shutil.copy2(backups[-1], db_path)
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
            try: os.remove(old)
            except: pass

    # 4. Database Migration
    if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
        old_root = get_old_root_from_db(db_path)
        if old_root and old_root != current_root:
            log(f"Migrating DB: {old_root} -> {current_root}", data_dir)
            try:
                conn = sqlite3.connect(db_path, timeout=15.0)
                cur = conn.cursor()
                targets = [("track_locations", "location"), ("track_locations", "directory"),
                           ("LibraryHashes", "directory_path"), ("directories", "directory")]
                for table, col in targets:
                    cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                    if cur.fetchone():
                        cur.execute(f"UPDATE {table} SET {col} = ? || SUBSTR({col}, LENGTH(?) + 1) WHERE {col} LIKE ? || '%'", 
                                   (current_root, old_root, old_root))
                conn.commit()
                conn.close()
            except Exception as e: log(f"Database Error: {e}", data_dir)

    # 5. Config Migration
    if os.path.exists(cfg_active):
        try:
            with open(cfg_active, 'r', encoding='utf-8', errors='ignore') as f: lines = f.readlines()
            old_cfg_root = None
            for l in lines:
                if l.startswith("Directory ") and "/Music" in l:
                    p_root = l.replace("\\", "/").split("Directory ")[1].split("/Music")[0].strip()
                    if p_root != current_root:
                        old_cfg_root = p_root
                        break
            if old_cfg_root:
                with open(cfg_active, 'w', encoding='utf-8') as f:
                    f.writelines([l.replace(old_cfg_root, current_root) if old_cfg_root in l else l for l in lines])
                log("[SUCCESS] Config paths updated.", data_dir)
            elif not any(l.startswith("Directory ") for l in lines):
                with open(cfg_active, 'a', encoding='utf-8') as f:
                    f.write(f"\n[Library]\nDirectory {current_music_dir}\nRecordingDirectory {current_music_dir}\n")
        except: pass

    validate_library(db_path, current_root, data_dir)

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        fix_paths(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "load")