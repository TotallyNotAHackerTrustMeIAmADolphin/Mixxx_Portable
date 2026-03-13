#!/bin/bash
# Move into the script directory
cd "$( dirname "${BASH_SOURCE[0]}" )"
DIR="$(pwd)"
DATA_DIR="$DIR/Mixxx_Data"
SCRIPT_DIR="$DIR/Scripts"

clear
echo "=========================================="
echo "    MIXXX SMART LAUNCHER (LINUX)         "
echo "=========================================="

# 1. Prepare Environment
python3 "$SCRIPT_DIR/mixxx_path_fixer.py" "$DATA_DIR" "linux" "load"

if [ $? -eq 0 ]; then
    # 2. Launch Mixxx
    mixxx --settingsPath "$DATA_DIR"
    
    # 3. Save session settings
    python3 "$SCRIPT_DIR/mixxx_path_fixer.py" "$DATA_DIR" "linux" "save"
else
    echo "Initialization failed. Mixxx will not start."
    read -p "Press Enter to exit..."
fi