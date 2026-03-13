import sqlite3
import os
import sys
import shutil
import datetime
import glob
import socket
import time

def mixxx_normalize_path(path_str):
    path_str = path_str.replace('\\', '/')
    if len(path_str) >= 2 and path_str[1] == ':':
        path_str = path_str[0].upper() + path_str[1:]
    return path_str

def robust_open(file_path, mode, encoding='utf-8', retries=5, delay=0.2):
    """Try to open a file multiple times to bypass cloud-sync locks."""
    for i in range(retries):
        try:
            return open(file_path, mode, encoding=encoding, errors='ignore')
        except (OSError, IOError) as e:
            if i == retries - 1:
                raise e
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
        if choice != 'y':
            sys.exit(1)

def validate_library(db_path, current_root):
    if not os.path.exists(db_path): return
    try:
        conn = sqlite3.connect(db_path, timeout=15.0)
        cur = conn.cursor()
        # Find any tracks in the database that DO NOT start with the exact current portable root
        cur.execute("SELECT location FROM track_locations WHERE location NOT LIKE ?", (f"{current_root}%",))
        external_tracks = cur.fetchall()
        if external_tracks:
            print("\n" + "!"*60)
            print("⚠️  WARNING: NON-PORTABLE TRACKS DETECTED")
            print(f"Found {len(external_tracks)} tracks outside your portable drive.")
            print("!"*60)
            for (path,) in external_tracks[:5]: print(f" -> {path}")
            print("!"*60 + "\n")
        conn.close()
    except Exception: pass

def fix_paths(data_dir, to_os, mode="load"):
    data_dir = os.path.abspath(data_dir)
    portable_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    db_path = os.path.join(data_dir, "mixxxdb.sqlite")
    cfg_active = os.path.join(data_dir, "mixxx.cfg")
    config_dir = os.path.join(data_dir, "Configs")
    backup_dir = os.path.join(data_dir, "Backups")
    db_state_file = os.path.join(data_dir, ".portable_root") # NEW: Remembers the previous folder path
    
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(backup_dir, exist_ok=True)

    hostname = socket.gethostname().lower()
    current_root = mixxx_normalize_path(portable_root)
    current_music_dir = current_root + "/Music"
    
    os_ext = to_os[:3].lower()
    machine_cfg_store = os.path.join(config_dir, f"mixxx.cfg.{hostname}")
    os_template_store = os.path.join(config_dir, f"mixxx.cfg.{os_ext}") 

    print(f"--- Mixxx Sync[{to_os.upper()} | Machine: {hostname}] ---")

    if mode == "save":
        if os.path.exists(cfg_active):
            shutil.copy2(cfg_active, machine_cfg_store)
            print(f"Hardware settings saved to: Configs/mixxx.cfg.{hostname}")
        return

    # --- LOAD MODE ---
    if os.path.exists(db_path):
        check_db_lock(db_path)

    if os.path.exists(machine_cfg_store):
        print(f"Found specific config for {hostname}. Restoring...")
        shutil.copy2(machine_cfg_store, cfg_active)
    elif os.path.exists(os_template_store):
        print(f"No machine-specific config. Using {to_os} template...")
        shutil.copy2(os_template_store, cfg_active)

    # Database Backup
    try:
        MAX_BACKUPS = 10
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if os.path.exists(db_path):
            db_backup = os.path.join(backup_dir, f"mixxxdb_{hostname}_{timestamp}.sqlite")
            shutil.copy2(db_path, db_backup)
        db_backups = sorted(glob.glob(os.path.join(backup_dir, f"mixxxdb_{hostname}_*.sqlite")))
        if len(db_backups) > MAX_BACKUPS:
            for old_db in db_backups[:-MAX_BACKUPS]: os.remove(old_db)
    except Exception as e: print(f"Backup Error: {e}")

    # Determine the old root path for dynamic substitution
    if os.path.exists(db_state_file):
        with open(db_state_file, "r") as f:
            old_root = f.read().strip()
    else:
        # Fallback for users migrating from the previous script version
        old_root = "Mixxx_Portable"

    # Path Reconstruction
    total_updated = 0
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path, timeout=15.0)
            cur = conn.cursor()
            cur.execute("DELETE FROM track_locations WHERE id IN (SELECT location FROM library WHERE mixxx_deleted = 1)")
            cur.execute("DELETE FROM library WHERE mixxx_deleted = 1")
            
            targets =[
                ("track_locations", "location", "id"), ("track_locations", "directory", "id"),
                ("library", "location", "id"), ("library", "folder", "id"),
                ("LibraryHashes", "directory_path", "directory_path"),
                ("directories", "directory", "directory")
            ]

            # Determine if we are matching an exact absolute path or just a substring (fallback)
            is_absolute = ("/" in old_root or ":" in old_root)
            search_like = f"{old_root}%" if is_absolute else f"%{old_root}%"

            for table, col, pkey in targets:
                cur.execute(f"PRAGMA table_info({table})")
                if any(col == c[1] for c in cur.fetchall()):
                    cur.execute(f"SELECT {pkey}, {col} FROM {table} WHERE {col} LIKE ?", (search_like,))
                    rows = cur.fetchall()
                    
                    updates =[]
                    for pk, old_path in rows:
                        if not old_path: continue
                        clean_old = old_path.replace("\\", "/")
                        
                        new_path = None
                        if is_absolute:
                            if clean_old.startswith(old_root):
                                new_path = current_root + clean_old[len(old_root):]
                        else:
                            if f"{old_root}/" in clean_old:
                                sub_path = clean_old.split(f"{old_root}/")[-1].lstrip("/")
                                new_path = f"{current_root}/{sub_path}".rstrip("/")
                                
                        if new_path and clean_old != new_path:
                            updates.append((new_path, pk))
                    
                    if updates:
                        cur.executemany(f"UPDATE {table} SET {col} = ? WHERE {pkey} = ?", updates)
                        total_updated += len(updates)
                        
            conn.commit()
            conn.close()
            print(f"[SUCCESS] Database: Updated {total_updated} file path entries.")
        except Exception as e: print(f"Database Error: {e}")

    # Config File Reconstruction
    if os.path.exists(cfg_active):
        try:
            with robust_open(cfg_active, 'r') as f:
                lines = f.readlines()
            
            new_lines =[]
            cfg_fixes = 0
            for line in lines:
                clean_line = line.replace("\\", "/")
                
                if is_absolute:
                    if old_root in clean_line:
                        new_val = clean_line.replace(old_root, current_root)
                        if line != new_val: cfg_fixes += 1
                        new_lines.append(new_val)
                    else:
                        new_lines.append(line)
                else:
                    if f"{old_root}/" in clean_line:
                        key = clean_line.split(" ", 1)[0]
                        sub_path = clean_line.split(f"{old_root}/")[-1].strip()
                        new_val = f"{key} {current_root}/{sub_path}\n"
                        if line != new_val: cfg_fixes += 1
                        new_lines.append(new_val)
                    else: 
                        new_lines.append(line)
            
            with robust_open(cfg_active, 'w') as f:
                f.writelines(new_lines)
            print(f"[SUCCESS] Config: Applied {cfg_fixes} path updates.")
        except Exception as e: print(f"Config Error: {e}")

    # Save the current state so you can infinitely rename the folder in the future
    try:
        with open(db_state_file, "w") as f:
            f.write(current_root)
    except Exception as e: pass

    validate_library(db_path, current_root)

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        fix_paths(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "load")