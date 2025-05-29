#!/bin/bash

# --- Configuration ---
APP_NAME="HyperPomo"
APP_COMMENT="Pomodoro Timer and Task Planner"
APP_EXECUTABLE_NAME="HyperPomo" 

# Source directory from PyInstaller output
PYINSTALLER_BUNDLE_DIR_NAME="${APP_NAME}" # e.g., HyperPomo (the folder name inside dist)
SOURCE_APP_ROOT_DIR="$(pwd)/dist/${PYINSTALLER_BUNDLE_DIR_NAME}"

# Relative path to the Misc folder *within the PyInstaller bundle*
# This is the crucial part based on your observation
RELATIVE_MISC_DIR="_internal/Misc" 

SOURCE_ICON_FILE="${SOURCE_APP_ROOT_DIR}/${RELATIVE_MISC_DIR}/HyperPomo.png"

# Target installation directory for the application files
INSTALL_ROOT_DIR="$HOME/.local/share/${APP_NAME}App" 
INSTALL_APP_EXECUTABLE_PATH="${INSTALL_ROOT_DIR}/${APP_EXECUTABLE_NAME}"
# The icon will be located at INSTALL_ROOT_DIR/RELATIVE_MISC_DIR/HyperPomo.png
INSTALL_ICON_FULL_PATH="${INSTALL_ROOT_DIR}/${RELATIVE_MISC_DIR}/HyperPomo.png"

# Desktop file configuration
DESKTOP_FILE_NAME="${APP_NAME,,}.desktop" 
DESKTOP_FILE_DIR="$HOME/.local/share/applications"

# --- Helper Functions ---
echo_info() {
    echo "INFO: $1"
}
echo_error() {
    echo "ERROR: $1" >&2
}

# --- Installation Steps ---
echo_info "Starting installation of ${APP_NAME}..."

# 1. Check source files
if [ ! -d "${SOURCE_APP_ROOT_DIR}" ]; then
    echo_error "PyInstaller output directory ${SOURCE_APP_ROOT_DIR} not found. Build first."
    exit 1
fi
if [ ! -f "${SOURCE_APP_ROOT_DIR}/${APP_EXECUTABLE_NAME}" ]; then
    echo_error "Executable ${APP_EXECUTABLE_NAME} not found in ${SOURCE_APP_ROOT_DIR}."
    exit 1
fi
if [ ! -f "${SOURCE_ICON_FILE}" ]; then 
    echo_error "Icon file not found at expected bundled location: ${SOURCE_ICON_FILE}."
    echo_error "Verify PyInstaller bundles 'Misc/HyperPomo.png' into an '${RELATIVE_MISC_DIR}' subdirectory of its output."
    exit 1
fi

# 2. Create target installation directory
echo_info "Creating/ensuring installation directory: ${INSTALL_ROOT_DIR}"
mkdir -p "${INSTALL_ROOT_DIR}" || { echo_error "Failed to create ${INSTALL_ROOT_DIR}."; exit 1; }

# 3. Copy application files
echo_info "Copying application files to ${INSTALL_ROOT_DIR}..."
rsync -a --delete "${SOURCE_APP_ROOT_DIR}/" "${INSTALL_ROOT_DIR}/" || { echo_error "Failed to copy files."; exit 1; }

# 4. Set execute permissions
echo_info "Setting execute permissions for ${INSTALL_APP_EXECUTABLE_PATH}"
chmod +x "${INSTALL_APP_EXECUTABLE_PATH}" || echo_error "Failed to set execute permission on executable."


# 5. Create .desktop file
echo_info "Creating desktop file: ${DESKTOP_FILE_DIR}/${DESKTOP_FILE_NAME}"
mkdir -p "${DESKTOP_FILE_DIR}" || { echo_error "Failed to create ${DESKTOP_FILE_DIR}."; exit 1; }

cat > "${DESKTOP_FILE_DIR}/${DESKTOP_FILE_NAME}" << EOF
[Desktop Entry]
Version=1.0
Name=${APP_NAME}
Comment=${APP_COMMENT}
Exec=${INSTALL_APP_EXECUTABLE_PATH}
Icon=${INSTALL_ICON_FULL_PATH}
Terminal=false
Type=Application
Categories=Utility;Office;Productivity;
StartupWMClass=${APP_NAME} 
EOF

if [ $? -ne 0 ]; then # Check if cat command succeeded (though it rarely fails here)
    echo_error "Failed to write .desktop file."
    # exit 1 # Continue to chmod and update-desktop-database
fi
chmod +x "${DESKTOP_FILE_DIR}/${DESKTOP_FILE_NAME}" || echo_error "Failed to chmod .desktop file."

# 6. Update desktop database
echo_info "Updating desktop application database..."
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "${DESKTOP_FILE_DIR}"
else
    echo_info "update-desktop-database command not found. May need logout/login for menu update."
fi

echo_info ""
echo_info "${APP_NAME} installation complete!"
echo_info "Installed to: ${INSTALL_ROOT_DIR}"
echo_info "Desktop file at: ${DESKTOP_FILE_DIR}/${DESKTOP_FILE_NAME}"
echo_info "Try logging out and back in if the icon doesn't appear in your menu."
exit 0
