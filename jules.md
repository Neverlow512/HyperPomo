# Jules' Development Notes
This file will track the development progress, decisions, and any challenges encountered while implementing new features for HyperPomo.

## Project Setup & Initial Documentation
*Date: Approx. 2024-06-01*
*   **Implemented:**
    *   Created this `jules.md` file to track development notes.
    *   Updated `README.md` to include a new section "Upcoming Features (Under Development)" listing planned enhancements like interactive task lists, GUI customization, Gemini integration, TTS, voice input, YouTube music, expanded sounds, and advanced time tracking.
    *   Added placeholder comments in `requirements.txt` for libraries anticipated for future features (Gemini SDK, SpeechRecognition, PyAudio, pyttsx3, cefpython3/tkhtmlview).
*   **Decisions:**
    *   `jules.md` chosen as the name for the development log.
    *   Standardized on using relative paths for sound files in `config_manager.py`.
*   **Challenges:**
    *   Initial `ls()` and `read_files()` calls sometimes used incorrect casing for `README.md` (e.g., `README.md` vs `readme.md`), requiring correction. This highlighted the need to be precise with file names.

## GUI Framework Refactor for Customization
*Date: Approx. 2024-06-02*
*   **Implemented:**
    *   Refactored color management in `app.py`. Hardcoded color hex codes were removed from class attributes.
    *   Centralized theme color definitions in `config_manager.py` under a "theme" dictionary in `DEFAULT_SETTINGS`.
    *   `app.py` now loads these colors into instance attributes via a new `_load_theme_colors()` method.
    *   All UI elements and ttk styles in `app.py` were updated to reference these instance attributes (e.g., `self.COLOR_BG`).
    *   Added a read-only display of current theme colors in the settings window (`open_settings` method in `app.py`). This involved creating a scrollable frame to list color names, hex values, and visual swatches.
*   **Decisions:**
    *   Theme colors are loaded into instance variables in `PomodoroApp` for direct access.
    *   Fallback default color values were provided in `_load_theme_colors` in case a color key is missing from the configuration.
    *   The settings window's color display is read-only for now, with editing planned for a later stage.
*   **Challenges:**
    *   Ensuring all direct color references throughout `app.py` (UI setup, dialogs, dynamic style changes) were updated to use the new instance variables was a detailed process.
    *   The `replace_with_git_merge_diff` tool had some initial issues with diff format (e.g., `<<<<<<< HEAD` markers), which required careful reformatting of the diff blocks.

## Notification Sound Library
*Date: Approx. 2024-06-03*
*   **Implemented:**
    *   Updated `config_manager.py`:
        *   Added `"notification_sounds"` list to `DEFAULT_SETTINGS` (list of dicts with `name` and `path`).
        *   Changed `work_end_sound` and `break_end_sound` to store paths selected from this library.
        *   Updated `_load_settings` to initialize and migrate these settings.
    *   Updated `app.py`'s settings window (`open_settings`):
        *   Replaced `ttk.Entry` for sound paths with `ttk.Combobox` widgets, populated with names from the `notification_sounds` library.
        *   Implemented an "Add Custom Sound" feature:
            *   Uses `filedialog.askopenfilename` to select sound files (.mp3, .wav).
            *   Uses `simpledialog.askstring` to get a display name.
            *   Copies selected files to the `sounds/` directory (creating it if needed) with unique filenames (timestamp-based).
            *   Updates the `notification_sounds` list in `config_manager` and refreshes the Comboboxes in the settings window.
    *   Ensured `_play_sound` correctly uses `resource_path()` for playback.
*   **Decisions:**
    *   Custom sounds are copied into a local `sounds/` directory to ensure portability and avoid reliance on external file paths after initial selection.
    *   Relative paths (e.g., `sounds/custom_sound.mp3`) are stored in the configuration.
    *   Comboboxes in settings are set to `readonly` to enforce selection from the managed library.
*   **Challenges:**
    *   Dynamically updating the Combobox values after adding a new sound required passing the Combobox instances to the `_add_custom_sound` method.
    *   Ensuring paths were handled correctly (relative for config, absolute for playback/copying using `resource_path`) was important.

## Task List Enhancements (Drag and Drop - Phase 1)
*Date: Approx. 2024-06-04*
*   **Implemented:**
    *   Added basic visual drag-and-drop reordering for tasks within the `ttk.Treeview` in `app.py`.
    *   Initialized `self.dragging_task_id = None` in `PomodoroApp.__init__`.
    *   Bound `<ButtonPress-1>`, `<B1-Motion>`, and `<ButtonRelease-1>` events on `self.task_tree` to new methods: `on_task_drag_start`, `on_task_drag_motion`, and `on_task_drag_release`.
    *   `on_task_drag_start`: Identifies the clicked task and stores its ID (from Treeview tags).
    *   `on_task_drag_motion`: Changes the mouse cursor to "hand2" for visual feedback.
    *   `on_task_drag_release`: Determines the target position and uses `self.task_tree.move()` to visually reorder the task. Handles dropping on other items or in empty space (end of list).
*   **Decisions:**
    *   For Phase 1, reordering is visual only and does not persist in `task_manager.py` or `settings.json`. This simplifies the initial implementation.
    *   The task ID stored in `dragging_task_id` is the application's internal UUID for the task, which is then used to find the corresponding Treeview item ID for the `move` operation.
    *   Cursor change is the primary visual feedback.
*   **Challenges:**
    *   `ttk.Treeview` lacks native drag-and-drop. The custom implementation requires careful handling of event coordinates and Treeview item identification.
    *   Distinguishing between the application's task ID (stored in tags) and Tkinter's internal item ID for the `move` operation was a key detail.

## Gemini Integration - Core API Setup
*Date: Approx. 2024-06-05*
*   **Implemented:**
    *   Added settings in `config_manager.py` (`DEFAULT_SETTINGS` and `_load_settings` logic) for:
        *   `gemini_api_key` (string, user-provided)
        *   `gemini_model` (string, e.g., "gemini-pro", with a default)
        *   `gemini_enabled` (boolean, to toggle the feature)
        *   `gemini_models_available` (list of strings for model selection dropdown)
    *   Updated the settings UI in `app.py` (`open_settings` method) to include:
        *   A `ttk.LabelFrame` for "Gemini Assistant Settings".
        *   A `ttk.Checkbutton` for enabling/disabling Gemini.
        *   A `ttk.Entry` (with `show="*"`) for the API key.
        *   A `ttk.Combobox` (read-only) for model selection, populated from `gemini_models_available`.
    *   Created `src/gemini_assistant.py` with the `GeminiAssistant` class. This class includes:
        *   `__init__` to store API key and model name.
        *   `_configure` method to initialize `google.generativeai` with the API key and create a `GenerativeModel` instance. Basic error handling included.
        *   `send_message` method (currently non-streaming) to send prompts to the Gemini model and return the text response, with error handling for API key issues, quota errors, and general communication problems.
    *   Added `google-generativeai` to `requirements.txt`.
*   **Decisions:**
    *   API key stored as plain text in `settings.json`, a common approach for client-side applications where the user provides their own key. The UI obscures the key.
    *   A default list of common Gemini models is provided for user convenience.
    *   The `GeminiAssistant` class encapsulates API interaction logic.
*   **Challenges:**
    *   Ensuring all new config keys were correctly handled in `_load_settings` in `config_manager.py`.

## Gemini Integration - Basic Chat Interface
*Date: Approx. 2024-06-06*
*   **Implemented:**
    *   In `app.py`, added UI elements for a Gemini chat interface within the `right_pane_frame`:
        *   A `ttk.LabelFrame` titled "Gemini Assistant".
        *   A `scrolledtext.ScrolledText` widget (`self.gemini_chat_history`) for displaying chat messages, configured with custom background/foreground colors and text tags ("user", "gemini", "error", "info") for styling.
        *   An input `ttk.Entry` (`self.gemini_chat_input`) for users to type messages, bound to `<Return>` key.
        *   A "Send" `ttk.Button` (`self.gemini_send_button`).
    *   Implemented `_initialize_gemini_assistant()` in `app.py`:
        *   Instantiates `GeminiAssistant` if enabled and API key is provided.
        *   Posts initial status messages (e.g., "Gemini Assistant initialized", "API key missing", "Disabled") to the chat history.
        *   Manages the initial state of the "Send" button (enabled/disabled).
        *   This method is called at app startup and after settings are saved.
    *   Implemented `_add_message_to_chat_history(message, tag)` helper method to append messages to the chat display with appropriate styling and auto-scrolling.
    *   Implemented `on_send_gemini_message(event=None)`:
        *   Retrieves user input.
        *   Adds user message to history.
        *   Calls `self.gemini_assistant.send_message()`.
        *   Adds Gemini's response (or error) to history with appropriate styling.
        *   Manages "Send" button state during processing.
*   **Decisions:**
    *   The chat interface is placed in the right pane for now.
    *   Specific colors from the theme are used for styling user and Gemini messages.
    *   Error messages from Gemini or about its configuration are also displayed in the chat history.
*   **Challenges:**
    *   Ensuring the `_initialize_gemini_assistant` method was called at the right times (after UI setup, after settings save) to correctly reflect the current state.
    *   Properly managing the state of the "Send" button based on Gemini's availability and API key status.

## Gemini Integration - Text-to-Speech (TTS) for Responses
*Date: Approx. 2024-06-07*
*   **Implemented:**
    *   Added `pyttsx3` to `requirements.txt`.
    *   Added `gemini_tts_enabled` (boolean) to `DEFAULT_SETTINGS` in `config_manager.py` and updated `_load_settings`.
    *   In `app.py`:
        *   Imported `pyttsx3`.
        *   Initialized `self.tts_engine = None`.
        *   Implemented `_initialize_tts_engine()` to initialize `pyttsx3` if `gemini_tts_enabled` is true. Includes error handling and posts to chat history if TTS fails to load. This is called at startup and after settings save.
        *   Added a "Enable Text-to-Speech for Gemini responses" `ttk.Checkbutton` to the Gemini settings UI.
        *   Modified `on_send_gemini_message` to:
            *   Check if TTS is enabled and the engine is available.
            *   If so, use `self.tts_engine.say(response_text)` and `self.tts_engine.runAndWait()` to speak Gemini's non-error responses.
            *   Includes error handling for TTS playback.
*   **Decisions:**
    *   `pyttsx3.init()` is called only when TTS is enabled to avoid unnecessary resource usage.
    *   `runAndWait()` is used for simplicity in this phase; potential UI freeze for very long messages is noted as a point for future improvement (threading).
*   **Challenges:**
    *   Ensuring the TTS engine is correctly initialized/de-initialized when the setting is toggled. The `_initialize_tts_engine` also handles stopping the engine if it was previously active and is now being disabled.

## Gemini Integration - Task Management (Initial)
*Date: Approx. 2024-06-08*
*   **Implemented:**
    *   Defined `TASK_MANAGEMENT_PROMPT_INSTRUCTION` within `GeminiAssistant` in `src/gemini_assistant.py`. This system prompt instructs Gemini on how to parse user requests related to tasks, including:
        *   Creating new tasks with description, due date (optional), and estimated Pomodoros (optional).
        *   Responding with a structured format: `CREATE_TASK: DESCRIPTION: [desc]; DUE_DATE: [YYYY-MM-DD or ""]; POMODOROS: [number or ""]`.
        *   Added a note about ADHD to the prompt: "The user has ADHD, so task breakdown and clear, actionable steps are helpful."
    *   In `app.py` (`on_send_gemini_message`):
        *   Added parsing logic for the `CREATE_TASK:` response from Gemini.
        *   Extracts description, due_date (handling empty strings), and pomodoros (handling empty strings, defaulting to 1).
        *   Uses `self.task_manager.add_task()` to create the new task.
        *   Adds a confirmation message to the chat history (e.g., "Task '[desc]' created...").
        *   Refreshes the task list display.
        *   Implemented TTS for the confirmation message.
*   **Decisions:**
    *   A structured format (`CREATE_TASK:...`) was chosen for Gemini responses to make parsing more reliable.
    *   Default values (e.g., 1 Pomodoro if not specified) are handled in `app.py` after parsing.
    *   The "ADHD awareness" note is a first step towards tailoring Gemini's assistance.
*   **Challenges:**
    *   Designing a robust prompt that Gemini consistently follows for structured output. Multiple iterations might be needed.
    *   Parsing the date and Pomodoro values, especially handling cases where they might be missing or incorrectly formatted by the LLM, requires careful error handling (though current implementation might be basic).

## Gemini Integration - Calendar Scheduling
*Date: Approx. 2024-06-09*
*   **Implemented:**
    *   Extended `TASK_MANAGEMENT_PROMPT_INSTRUCTION` in `gemini_assistant.py` with new capabilities:
        *   `QUERY_TASKS_FOR_DATE: DATE: [YYYY-MM-DD]` for asking Gemini to list tasks for a specific date.
        *   `SCHEDULE_TASK: TASK_ID: [task_id or task_description]; DUE_DATE: [YYYY-MM-DD]` for asking Gemini to schedule an existing task.
    *   In `app.py` (`on_send_gemini_message`):
        *   Added parsing logic for `QUERY_TASKS_FOR_DATE:`:
            *   Extracts the date.
            *   Calls `self.task_manager.get_tasks_by_scheduled_date()` (or similar existing method, might need adjustment).
            *   Formats and displays the list of tasks in the chat.
            *   TTS for the task list summary.
        *   Added parsing logic for `SCHEDULE_TASK:`:
            *   Extracts task identifier (ID or description) and the new due date.
            *   If description is given, attempts to find the task ID (simple match for now, might need improvement for ambiguity).
            *   Calls `self.task_manager.update_task()` to set the new schedule date.
            *   Confirms in chat and via TTS. Refreshes task list.
*   **Decisions:**
    *   Task lookup for scheduling by description is a simple exact match for now. More sophisticated matching (e.g., fuzzy matching, or Gemini providing an ID if ambiguous) could be future enhancements.
    *   Gemini is instructed to use specific date formats.
*   **Challenges:**
    *   Reliably parsing task identifiers (ID vs. description) from Gemini's response for scheduling.
    *   Ensuring date parsing is robust.
    *   The prompt needs to be very clear to guide Gemini to use existing task IDs when possible for scheduling, or to ask for clarification if a description is ambiguous. Current implementation might be basic on this.
