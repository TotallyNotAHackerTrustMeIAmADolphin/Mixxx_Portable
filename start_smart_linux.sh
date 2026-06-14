#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DATA_DIR="$DIR/Mixxx_Data"
SCRIPT_DIR="$DIR/Scripts"

clear
echo "=========================================="
echo "    MIXXX SMART LAUNCHER (LINUX)         "
echo "=========================================="

# 1. Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ ERROR: Python 3 is not installed."
    echo "Fix: Run 'sudo apt update && sudo apt install python3'"
    read -p "Press Enter to exit..."
    exit 1
fi

# 2. Find Mixxx
MIXXX_CMD=""
if command -v mixxx &> /dev/null; then
    MIXXX_CMD="mixxx"
elif command -v flatpak &> /dev/null && flatpak list | grep -q org.mixxx.Mixxx; then
    MIXXX_CMD="flatpak run org.mixxx.Mixxx"
fi

if [ -z "$MIXXX_CMD" ]; then
    echo "❌ ERROR: Mixxx is not installed on this system."
    echo "Fix: Run 'sudo apt update && sudo apt install mixxx' or install via Flatpak."
    read -p "Press Enter to exit..."
    exit 1
fi

# 3. Prepare Environment
python3 "$SCRIPT_DIR/mixxx_path_fixer.py" "$DATA_DIR" "linux" "load"

if [ $? -eq 0 ]; then
    # 4. Launch Mixxx
    $MIXXX_CMD --settingsPath "$DATA_DIR"
    
    # 5. Save session settings
    echo "Saving machine settings..."
    python3 "$SCRIPT_DIR/mixxx_path_fixer.py" "$DATA_DIR" "linux" "save"
fi
