#!/bin/bash

# --- Configuration (Should match install.sh) ---
APP_NAME="HyperPomo"

# Target installation directory (where the application files were copied)
INSTALL_ROOT_DIR="$HOME/.local/share/${APP_NAME}App"

# Desktop file configuration
DESKTOP_FILE_NAME="${APP_NAME,,}.desktop" # e.g., hyperpomo.desktop
DESKTOP_FILE_PATH="$HOME/.local/share/applications/${DESKTOP_FILE_NAME}"

# --- Helper Functions ---
echo_info() {
    echo "INFO: $1"
}

echo_warning() {
    echo "WARNING: $1"
}

echo_error() {
    echo "ERROR: $1" >&2
}

# --- Uninstallation Steps ---

echo_info "Starting uninstallation of ${APP_NAME}..."

# 1. Ask for confirmation
read -p "Are you sure you want to uninstall ${APP_NAME}? This will remove all its files from ${INSTALL_ROOT_DIR} and the application menu entry. (y/N): " confirmation
if [[ "$confirmation" != "y" && "$confirmation" != "Y" ]]; then
    echo_info "Uninstallation cancelled by user."
    exit 0
fi

# 2. Remove the application directory
if [ -d "${INSTALL_ROOT_DIR}" ]; then
    echo_info "Removing application directory: ${INSTALL_ROOT_DIR}..."
    rm -rf "${INSTALL_ROOT_DIR}"
    if [ $? -ne 0 ]; then
        echo_error "Failed to remove application directory. You may need to remove it manually."
        # Continue to try and remove other parts
    else
        echo_info "Application directory removed."
    fi
else
    echo_warning "Application directory ${INSTALL_ROOT_DIR} not found. Skipping."
fi

# 3. Remove the .desktop file
if [ -f "${DESKTOP_FILE_PATH}" ]; then
    echo_info "Removing desktop file: ${DESKTOP_FILE_PATH}..."
    rm -f "${DESKTOP_FILE_PATH}"
    if [ $? -ne 0 ]; then
        echo_error "Failed to remove .desktop file. You may need to remove it manually."
    else
        echo_info "Desktop file removed."
    fi
else
    echo_warning "Desktop file ${DESKTOP_FILE_PATH} not found. Skipping."
fi

# 4. Update the desktop database
# It's good practice to run this even if files were not found,
# in case there were remnants or if the database needs cleaning.
echo_info "Updating desktop application database..."
if command -v update-desktop-database &> /dev/null; then
    if [ -d "$HOME/.local/share/applications" ]; then # Only run if the directory exists
        update-desktop-database "$HOME/.local/share/applications"
        if [ $? -ne 0 ]; then
            echo_warning "update-desktop-database reported an issue, but uninstallation steps were attempted."
        fi
    fi
else
    echo_warning "update-desktop-database command not found. Menu changes might require a logout/login or desktop restart."
fi

echo_info ""
echo_info "${APP_NAME} uninstallation complete."
echo_info "If the application icon/entry persists in your menu, try logging out and logging back in, or restarting your desktop environment."

exit 0

