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
    "work_end_sound": "sounds/work_end.mp3", # Default relative path
    "break_end_sound": "sounds/break_end.mp3", # Default relative path
    "always_on_top": False,
    "tasks": [], 
    "user_name": "User" 
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
                # This is a simple merge; more complex merging might be needed for nested dicts if any
                updated = False
                for key, value in DEFAULT_SETTINGS.items():
                    if key not in loaded_settings:
                        loaded_settings[key] = value
                        updated = True
                if updated: # If we added missing keys, save the updated settings back
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