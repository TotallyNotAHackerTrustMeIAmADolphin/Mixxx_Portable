import sqlite3
import os
import sys
import shutil
import datetime
import glob
import socket
import time

def mixxx_normalize_path(path_str):
    if not path_str: return ""
    path_str = path_str.replace('\\', '/')
    if len(path_str) >= 2 and path_str[1] == ':':
        path_str = path_str[0].upper() + path_str[1:]
    return path_str

def robust_open(file_path, mode, encoding='utf-8', retries=5, delay=0.2):
    for i in range(retries):
        try:
            return open(file_path, mode, encoding=encoding, errors='ignore')
        except (OSError, IOError) as e:
            if i == retries - 1: raise e
            time.sleep(delay)
    return open(file_path, mode, encoding=encoding)

def check_db_lock(db_path):
    journal = db_path + "-journal"
    wal = db_path + "-wal"
    if os.path.exists(journal) or os.path.exists(wal):
        print("\n" + "!"*60)
        print("⚠️  DATABASE IS LOCKED OR RECOVERING")
        print("Mixxx might still be running, or it didn't close properly.")
        print("!"*60)
        choice = input("Proceed anyway? (y/N): ").lower()
        if choice != 'y': sys.exit(1)

def get_old_root_from_db(db_path):
    try:
        conn = sqlite3.connect(db_path, timeout=15.0)
        cur = conn.cursor()
        cur.execute("SELECT directory FROM directories")
        rows = cur.fetchall()
        conn.close()
        for (path_str,) in rows:
            p = path_str.replace('\\', '/')
            if p.endswith('/Music'):
                return p[:-6]
    except Exception: pass
    return None

def validate_library(db_path, current_root):
    if not os.path.exists(db_path): return
    try:
        conn = sqlite3.connect(db_path, timeout=15.0)
        cur = conn.cursor()
        cur.execute("SELECT location FROM track_locations WHERE location NOT LIKE ?", (f"{current_root}%",))
        external = cur.fetchall()
        if external:
            print("\n" + "!"*60)
            print("⚠️  WARNING: NON-PORTABLE TRACKS DETECTED")
            print(f"Found {len(external)} tracks outside your portable drive root.")
            print("!"*60)
            for (path,) in external[:5]: print(f" -> {path[0]}")
            print("!"*60 + "\n")
        conn.close()
    except Exception: pass

def fix_paths(data_dir, to_os, mode="load"):
    data_dir = os.path.abspath(data_dir)
    portable_root_abs = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    current_root = mixxx_normalize_path(portable_root_abs)
    current_music_dir = f"{current_root}/Music"
    
    db_path = os.path.join(data_dir, "mixxxdb.sqlite")
    cfg_active = os.path.join(data_dir, "mixxx.cfg")
    config_dir = os.path.join(data_dir, "Configs")
    backup_dir = os.path.join(data_dir, "Backups")
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(backup_dir, exist_ok=True)

    hostname = socket.gethostname().lower()
    print(f"--- Mixxx Sync [{to_os.upper()} | {hostname}] ---")
    print(f"Current Path: {current_root}")

    if mode == "save":
        if os.path.exists(cfg_active):
            shutil.copy2(cfg_active, os.path.join(config_dir, f"mixxx.cfg.{hostname}"))
            print(f"[SUCCESS] Hardware settings saved.")
        return

    if os.path.exists(db_path):
        check_db_lock(db_path)

    # 1. Restore Hardware Config
    machine_cfg = os.path.join(config_dir, f"mixxx.cfg.{hostname}")
    os_template = os.path.join(config_dir, f"mixxx.cfg.{to_os[:3].lower()}")
    if os.path.exists(machine_cfg):
        shutil.copy2(machine_cfg, cfg_active)
    elif os.path.exists(os_template):
        shutil.copy2(os_template, cfg_active)
    elif os.path.exists(cfg_active):
        print("Scrubbing hardware...")
        try:
            with robust_open(cfg_active, 'r') as f: lines = f.readlines()
            safe_lines = []; in_hw = False
            for l in lines:
                if l.strip().startswith("[") and l.strip().endswith("]"): in_hw = (l.strip() == "[Soundcard]")
                if not in_hw: safe_lines.append(l)
            with robust_open(cfg_active, 'w') as f: f.writelines(safe_lines)
        except: pass

    # 2. Backup
    if os.path.exists(db_path):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(db_path, os.path.join(backup_dir, f"mixxxdb_{hostname}_{ts}.sqlite"))
        for old in sorted(glob.glob(os.path.join(backup_dir, f"mixxxdb_{hostname}_*.sqlite")))[:-10]: os.remove(old)

    # 3. Database Updates
    if os.path.exists(db_path):
        old_root = get_old_root_from_db(db_path)
        if old_root and old_root != current_root:
            print(f"Migrating paths: {old_root} -> {current_root}")
            try:
                conn = sqlite3.connect(db_path, timeout=15.0)
                cur = conn.cursor()
                # These are the only tables/columns that store string paths in Mixxx 2.3+
                targets = [
                    ("track_locations", "location"), 
                    ("track_locations", "directory"),
                    ("LibraryHashes", "directory_path"),
                    ("directories", "directory")
                ]
                total_updated = 0
                for table, col in targets:
                    # Safety Check: Verify column exists before updating
                    cur.execute(f"PRAGMA table_info({table})")
                    if any(col == c[1] for c in cur.fetchall()):
                        cur.execute(f"UPDATE {table} SET {col} = ? || SUBSTR({col}, LENGTH(?) + 1) WHERE {col} LIKE ? || '%'", 
                                   (current_root, old_root, old_root))
                        total_updated += cur.rowcount
                conn.commit()
                conn.close()
                print(f"[SUCCESS] Database updated ({total_updated} rows).")
            except Exception as e: print(f"Database Error: {e}")

    # 4. Config Updates
    if os.path.exists(cfg_active):
        try:
            with robust_open(cfg_active, 'r') as f: lines = f.readlines()
            old_cfg_root = None
            for l in lines:
                if l.startswith("Directory ") and "/Music" in l:
                    old_cfg_root = l.replace("\\", "/").split("Directory ")[1].split("/Music")[0].strip()
                    break
            if old_cfg_root and old_cfg_root != current_root:
                with robust_open(cfg_active, 'w') as f:
                    f.writelines([l.replace(old_cfg_root, current_root) for l in lines])
                print("[SUCCESS] Config updated.")
        except: pass

    validate_library(db_path, current_root)

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        fix_paths(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "load")