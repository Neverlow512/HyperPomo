# HyperPomo/src/config_manager.py
import json
import os

DEFAULT_SETTINGS = {
    "work_duration": 25,
    "short_break_duration": 5,
    "long_break_duration": 15,
    "pomodoros_per_long_break": 4,
    "auto_start_next_session": False,
    "sound_enabled": True,
    "notification_sounds": [
        {"name": "Default Work End", "path": "sounds/work_end.mp3"},
        # Assuming work_start.mp3 was intended for break_end based on previous structure
        {"name": "Default Break End", "path": "sounds/work_start.mp3"}
    ],
    "work_end_sound": "sounds/work_end.mp3",
    "break_end_sound": "sounds/work_start.mp3",
    "always_on_top": False,
    "tasks": [], 
    "user_name": "User",
    "gemini_api_key": "",
    "gemini_model": "gemini-pro",
    "gemini_enabled": False,
    "gemini_models_available": ["gemini-pro", "gemini-1.0-pro", "gemini-1.5-flash-latest", "gemini-1.5-pro-latest"],
    "gemini_tts_enabled": False,
    "theme": {
        "COLOR_BG": "#2D323B",
        "COLOR_FG": "#E0E0E0",
        "COLOR_ACCENT": "#FF8A65",
        "COLOR_WORK": "#81C784",
        "COLOR_SHORT_BREAK": "#64B5F6",
        "COLOR_LONG_BREAK_BG": "#FFD54F",
        "COLOR_LONG_BREAK_FG": "#2D323B",
        "COLOR_BUTTON": "#4A505A",
        "COLOR_BUTTON_HOVER": "#5C6370",
        "COLOR_BUTTON_TEXT": "#FFFFFF",
        "COLOR_DISABLED_BUTTON_TEXT": "#A0A0A0",
        "COLOR_ENTRY_BG": "#373C45",
        "COLOR_TREEVIEW_BG": "#333840",
        "COLOR_TREEVIEW_FG": "#E0E0E0",
        "COLOR_TREEVIEW_FIELD_BG": "#333840",
        "COLOR_TREEVIEW_HEADING_BG": "#4A505A",
        "COLOR_CURRENT_TASK_BG": "#373C45",
        "COLOR_CALENDAR_HEADER": "#4A505A",
        "COLOR_CALENDAR_WEEKEND": "#FF7070"
    }
}

class ConfigManager:
    def __init__(self, data_dir="data", filename="settings.json"):
        # data_dir is now expected to be an absolute path when bundled,
        # or a relative name like "data" during development if app.py doesn't use resource_path for it.
        # app.py now passes an absolute path via resource_path("data").
        self.data_dir = data_dir 
        self.filepath = os.path.join(self.data_dir, filename)
        self._ensure_data_dir_exists() # Call this before loading
        self.settings = self._load_settings()

    def _ensure_data_dir_exists(self):
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True) 

    def _load_settings(self):
        # _ensure_data_dir_exists() is called in __init__ before this now
        if not os.path.exists(self.filepath):
            # If settings file doesn't exist, create it with defaults
            current_settings = DEFAULT_SETTINGS.copy()
            try:
                with open(self.filepath, 'w', encoding='utf-8') as f:
                    json.dump(current_settings, f, indent=4)
                return current_settings
            except IOError:
                print(f"Error: Could not create default settings file at {self.filepath}")
                return DEFAULT_SETTINGS.copy() # Fallback to in-memory defaults

        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                loaded_settings = json.load(f)
                # Ensure all default keys are present in loaded settings
                updated = False
                for key, default_value in DEFAULT_SETTINGS.items():
                    if key not in loaded_settings:
                        loaded_settings[key] = default_value
                        updated = True
                    elif key == "theme" and isinstance(default_value, dict):
                        # Ensure all default theme colors are present
                        theme_updated = False
                        if not isinstance(loaded_settings.get(key), dict): # If theme is not a dict, overwrite with default
                            loaded_settings[key] = default_value.copy()
                            theme_updated = True
                        else:
                            for color_key, color_value in default_value.items():
                                if color_key not in loaded_settings[key]:
                                    loaded_settings[key][color_key] = color_value
                                    theme_updated = True
                        if theme_updated:
                            updated = True
                    elif key == "notification_sounds" and isinstance(default_value, list):
                        if not isinstance(loaded_settings.get(key), list) or \
                           not all(isinstance(item, dict) and "name" in item and "path" in item for item in loaded_settings[key]):
                            loaded_settings[key] = default_value[:] # Use a copy
                            updated = True

                # Migration/validation for work_end_sound and break_end_sound
                default_sounds_paths = [s['path'] for s in DEFAULT_SETTINGS["notification_sounds"]]
                if "work_end_sound" not in loaded_settings or loaded_settings["work_end_sound"] not in default_sounds_paths:
                    # If it's an old value or invalid, check if it exists in the current notification_sounds list (if any)
                    current_sound_paths = [s['path'] for s in loaded_settings.get("notification_sounds", []) if isinstance(s, dict)]
                    if loaded_settings.get("work_end_sound") not in current_sound_paths:
                        loaded_settings["work_end_sound"] = DEFAULT_SETTINGS["work_end_sound"]
                        updated = True

                if "break_end_sound" not in loaded_settings or loaded_settings["break_end_sound"] not in default_sounds_paths: # Check against default_sounds_paths
                    current_sound_paths = [s['path'] for s in loaded_settings.get("notification_sounds", []) if isinstance(s, dict)]
                    if loaded_settings.get("break_end_sound") not in current_sound_paths: # Check against current actual sounds
                        loaded_settings["break_end_sound"] = DEFAULT_SETTINGS["break_end_sound"]
                        updated = True

                # Ensure Gemini specific keys are present
                gemini_keys = ["gemini_api_key", "gemini_model", "gemini_enabled", "gemini_models_available", "gemini_tts_enabled"]
                for gk in gemini_keys:
                    if gk not in loaded_settings:
                        loaded_settings[gk] = DEFAULT_SETTINGS[gk]
                        updated = True
                # Ensure gemini_models_available is a list
                if not isinstance(loaded_settings.get("gemini_models_available"), list):
                    loaded_settings["gemini_models_available"] = DEFAULT_SETTINGS["gemini_models_available"][:] # Make a copy
                    updated = True
                # Ensure gemini_tts_enabled is a boolean
                if not isinstance(loaded_settings.get("gemini_tts_enabled"), bool):
                    loaded_settings["gemini_tts_enabled"] = DEFAULT_SETTINGS["gemini_tts_enabled"]
                    updated = True


                if updated: # If we added missing keys, theme colors, or sound settings, save back
                    self.save_settings(loaded_settings) # Pass the dict to save
                return loaded_settings
        except (json.JSONDecodeError, IOError):
            print(f"Warning: Could not load or parse {self.filepath}. Using default settings.")
            # Optionally, attempt to save defaults back to a potentially corrupted file or a new one
            current_settings = DEFAULT_SETTINGS.copy()
            try:
                with open(self.filepath, 'w', encoding='utf-8') as f: # Overwrite/create with defaults
                    json.dump(current_settings, f, indent=4)
            except IOError:
                print(f"Error: Could not write default settings to {self.filepath} after load failure.")
            return current_settings


    def save_settings(self, settings_to_save=None): # Allow passing specific dict to save
        self._ensure_data_dir_exists()
        data_to_write = settings_to_save if settings_to_save is not None else self.settings
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(data_to_write, f, indent=4)
        except IOError:
            print(f"Error: Could not save settings to {self.filepath}")

    def get(self, key, default=None):
        # Ensure self.settings is initialized
        if self.settings is None: # Should ideally not happen if __init__ is correct
             self.settings = DEFAULT_SETTINGS.copy()
        return self.settings.get(key, default if default is not None else DEFAULT_SETTINGS.get(key))


    def set(self, key, value):
        if self.settings is None: # Should not happen
             self.settings = DEFAULT_SETTINGS.copy()
        self.settings[key] = value
        self.save_settings() # This will save the entire self.settings dictionary

    def get_all_tasks(self):
        if self.settings is None: self.settings = DEFAULT_SETTINGS.copy()
        tasks = self.settings.get("tasks")
        return tasks if isinstance(tasks, list) else []


    def save_tasks(self, tasks):
        if self.settings is None: self.settings = DEFAULT_SETTINGS.copy()
        self.settings["tasks"] = tasks
        self.save_settings()

    def get_session_log_path(self):
        self._ensure_data_dir_exists()
        return os.path.join(self.data_dir, "session_log.json")

    def load_session_log(self):
        log_path = self.get_session_log_path()
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                print(f"Warning: Could not load session log {log_path}.")
                return []
        return []

    def save_session_log(self, log_data):
        log_path = self.get_session_log_path()
        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=4)
        except IOError:
            print(f"Error: Could not save session log to {log_path}")