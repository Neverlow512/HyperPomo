# HyperPomo/src/app.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog, scrolledtext, PanedWindow
import time
import os
import datetime
import sys
import shutil # Added for file operations
import pyttsx3 # For Text-to-Speech

from .config_manager import ConfigManager
from .task_manager import TaskManager, Task
from .gemini_assistant import GeminiAssistant # Import GeminiAssistant

TKCALENDAR_AVAILABLE = False
try:
    from tkcalendar import Calendar, DateEntry
    TKCALENDAR_AVAILABLE = True
except ImportError:
    print("Warning: 'tkcalendar' module not found. Calendar features will be disabled.")

PLAYSOUND_AVAILABLE = False
try:
    from playsound import playsound
    PLAYSOUND_AVAILABLE = True
except ImportError:
    print("Warning: 'playsound' module not found. Sound notifications will be disabled.")

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Not running in a PyInstaller bundle
        # Path relative to this app.py file (which is in src/)
        # We want the parent of src/, which is the application root (HyperPomo/)
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    return os.path.join(base_path, relative_path)

class PomodoroApp:
    WORK = "Work"
    SHORT_BREAK = "Short Break"
    LONG_BREAK = "Long Break"

    # Color definitions are now loaded from config_manager

    def __init__(self, root):
        self.root = root
        self.root.title("HyperPomo") 
        
        # self.base_dir is now effectively what resource_path("") would return if needed elsewhere
        # For consistency, if other parts of code need the app's root path and are not calling resource_path directly
        # for specific assets, you could define it:
        # self.app_root_path = resource_path("") # Gets the root bundle/script directory

        self.config_manager = ConfigManager(data_dir=resource_path("data"))
        self._load_theme_colors() # Load theme colors after config_manager is ready

        self.root.configure(bg=self.COLOR_BG) # Configure root bg after theme is loaded

        self.task_manager = TaskManager(self.config_manager)
        self.session_log = self.config_manager.load_session_log()

        self.current_session_type = self.WORK
        self.pomodoros_completed_cycle = 0
        self.is_running = False
        self.paused = False
        self.time_left = self.config_manager.get("work_duration") * 60
        self.timer_id = None
        self.current_task_id = None
        self.always_on_top_var = tk.BooleanVar(value=self.config_manager.get("always_on_top", False))
        self.selected_calendar_date = datetime.date.today() 
        self.dragging_task_id = None # For task drag-and-drop
        self.gemini_assistant = None # Initialize Gemini Assistant instance
        self.tts_engine = None # Initialize TTS engine instance

        self._apply_initial_settings()
        self._setup_styles()
        self._setup_ui() 
        self._initialize_gemini_assistant() # Initialize after UI is set up, so chat history widget exists
        self._initialize_tts_engine() # Initialize TTS engine
        self.update_timer_display()
        self.refresh_task_list_and_daily_summary() 
        self.update_always_on_top()
        self._bind_shortcuts()
        self.update_current_datetime_display() 

    def _load_theme_colors(self):
        theme_colors = self.config_manager.get("theme")
        # Fallbacks are to the original hardcoded values, just in case config is corrupted or a key is missing
        self.COLOR_BG = theme_colors.get("COLOR_BG", "#2D323B")
        self.COLOR_FG = theme_colors.get("COLOR_FG", "#E0E0E0")
        self.COLOR_ACCENT = theme_colors.get("COLOR_ACCENT", "#FF8A65")
        self.COLOR_WORK = theme_colors.get("COLOR_WORK", "#81C784")
        self.COLOR_SHORT_BREAK = theme_colors.get("COLOR_SHORT_BREAK", "#64B5F6")
        self.COLOR_LONG_BREAK_BG = theme_colors.get("COLOR_LONG_BREAK_BG", "#FFD54F")
        self.COLOR_LONG_BREAK_FG = theme_colors.get("COLOR_LONG_BREAK_FG", "#2D323B")
        self.COLOR_BUTTON = theme_colors.get("COLOR_BUTTON", "#4A505A")
        self.COLOR_BUTTON_HOVER = theme_colors.get("COLOR_BUTTON_HOVER", "#5C6370")
        self.COLOR_BUTTON_TEXT = theme_colors.get("COLOR_BUTTON_TEXT", "#FFFFFF")
        self.COLOR_DISABLED_BUTTON_TEXT = theme_colors.get("COLOR_DISABLED_BUTTON_TEXT", "#A0A0A0")
        self.COLOR_ENTRY_BG = theme_colors.get("COLOR_ENTRY_BG", "#373C45")
        self.COLOR_TREEVIEW_BG = theme_colors.get("COLOR_TREEVIEW_BG", "#333840")
        self.COLOR_TREEVIEW_FG = theme_colors.get("COLOR_TREEVIEW_FG", "#E0E0E0")
        self.COLOR_TREEVIEW_FIELD_BG = theme_colors.get("COLOR_TREEVIEW_FIELD_BG", "#333840")
        self.COLOR_TREEVIEW_HEADING_BG = theme_colors.get("COLOR_TREEVIEW_HEADING_BG", "#4A505A")
        self.COLOR_CURRENT_TASK_BG = theme_colors.get("COLOR_CURRENT_TASK_BG", "#373C45")
        self.COLOR_CALENDAR_HEADER = theme_colors.get("COLOR_CALENDAR_HEADER", "#4A505A")
        self.COLOR_CALENDAR_WEEKEND = theme_colors.get("COLOR_CALENDAR_WEEKEND", "#FF7070")

    def _apply_initial_settings(self):
        self.root.attributes('-topmost', self.always_on_top_var.get())

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure("TFrame", background=self.COLOR_BG) 
        style.configure("LongBreak.TFrame", background=self.COLOR_LONG_BREAK_BG)
        style.configure("Normal.TFrame", background=self.COLOR_BG) 

        style.configure("TLabel", background=self.COLOR_BG, foreground=self.COLOR_FG, font=("Segoe UI", 10))
        style.configure("Accent.TLabel", background=self.COLOR_BG, foreground=self.COLOR_ACCENT, font=("Segoe UI", 10, "bold"))
        style.configure("DateTime.TLabel", background=self.COLOR_BG, foreground=self.COLOR_FG, font=("Segoe UI", 9))

        style.configure("Work.Session.TLabel", background=self.COLOR_BG, foreground=self.COLOR_WORK, font=("Segoe UI", 18, "bold"))
        style.configure("Work.Timer.TLabel", background=self.COLOR_BG, foreground=self.COLOR_WORK, font=("Segoe UI", 60, "bold"))
        style.configure("Work.PomodoroCount.TLabel", background=self.COLOR_BG, foreground=self.COLOR_FG, font=("Segoe UI", 10))

        style.configure("ShortBreak.Session.TLabel", background=self.COLOR_BG, foreground=self.COLOR_SHORT_BREAK, font=("Segoe UI", 18, "bold"))
        style.configure("ShortBreak.Timer.TLabel", background=self.COLOR_BG, foreground=self.COLOR_SHORT_BREAK, font=("Segoe UI", 60, "bold"))
        style.configure("ShortBreak.PomodoroCount.TLabel", background=self.COLOR_BG, foreground=self.COLOR_FG, font=("Segoe UI", 10))
        
        style.configure("LongBreak.Session.TLabel", background=self.COLOR_LONG_BREAK_BG, foreground=self.COLOR_LONG_BREAK_FG, font=("Segoe UI", 18, "bold"))
        style.configure("LongBreak.Timer.TLabel", background=self.COLOR_LONG_BREAK_BG, foreground=self.COLOR_LONG_BREAK_FG, font=("Segoe UI", 60, "bold"))
        style.configure("LongBreak.PomodoroCount.TLabel", background=self.COLOR_LONG_BREAK_BG, foreground=self.COLOR_LONG_BREAK_FG, font=("Segoe UI", 10))

        style.configure("TButton", background=self.COLOR_BUTTON, foreground=self.COLOR_BUTTON_TEXT, font=("Segoe UI", 9, "bold"), borderwidth=1, relief=tk.FLAT, padding=(8,4))
        style.map("TButton",
                  background=[('active', self.COLOR_BUTTON_HOVER), ('pressed', self.COLOR_ACCENT), ('disabled', self.COLOR_BUTTON)],
                  foreground=[('disabled', self.COLOR_DISABLED_BUTTON_TEXT)],
                  relief=[('pressed', tk.SUNKEN), ('!pressed', tk.RAISED)])
        style.configure("CurrentTask.TLabel", background=self.COLOR_CURRENT_TASK_BG, foreground=self.COLOR_FG, padding=5, font=("Segoe UI", 9, "italic"), relief=tk.SOLID, borderwidth=1, bordercolor=self.COLOR_BUTTON)
        style.configure("Treeview", background=self.COLOR_TREEVIEW_BG, foreground=self.COLOR_TREEVIEW_FG, fieldbackground=self.COLOR_TREEVIEW_FIELD_BG, rowheight=25, font=("Segoe UI", 9))
        style.map("Treeview", background=[('selected', self.COLOR_ACCENT)], foreground=[('selected', self.COLOR_BG)]) # Note: COLOR_BG for selected text
        style.configure("Treeview.Heading", background=self.COLOR_TREEVIEW_HEADING_BG, foreground=self.COLOR_FG, font=('Segoe UI', 9, 'bold'), padding=4, relief=tk.FLAT)
        style.configure("TLabelframe", background=self.COLOR_BG, bordercolor=self.COLOR_ACCENT, padding=8, relief=tk.GROOVE)
        style.configure("TLabelframe.Label", background=self.COLOR_BG, foreground=self.COLOR_ACCENT, font=("Segoe UI", 10, "bold"))
        style.configure("TEntry", fieldbackground=self.COLOR_ENTRY_BG, foreground=self.COLOR_FG, insertcolor=self.COLOR_FG, font=("Segoe UI", 10), borderwidth=1, relief=tk.FLAT)
        style.configure("TSpinbox", fieldbackground=self.COLOR_ENTRY_BG, foreground=self.COLOR_FG, insertcolor=self.COLOR_FG, arrowcolor=self.COLOR_FG, background=self.COLOR_BUTTON, font=("Segoe UI", 10), relief=tk.FLAT)
        style.configure("TSash", background=self.COLOR_ACCENT, sashthickness=6)


    def _setup_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main_paned_window = PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=5, bg=self.COLOR_ACCENT) # Sash color
        main_paned_window.pack(fill=tk.BOTH, expand=True)

        left_pane_frame = ttk.Frame(main_paned_window, padding=5) # Style "TFrame" will apply COLOR_BG
        left_pane_frame.columnconfigure(0, weight=1)
        left_pane_frame.rowconfigure(1, weight=1) 
        main_paned_window.add(left_pane_frame, minsize=450)

        self.timer_controls_frame = ttk.Frame(left_pane_frame) # Style will apply based on session
        self.timer_controls_frame.grid(row=0, column=0, sticky="ew", pady=(0,10))
        self.timer_controls_frame.columnconfigure(0, weight=1)

        self.session_label = ttk.Label(self.timer_controls_frame, text=self.current_session_type, anchor="center") # Style will apply based on session
        self.session_label.pack(pady=(0,2), fill=tk.X)
        self.timer_label = ttk.Label(self.timer_controls_frame, text="25:00", anchor="center") # Style will apply based on session
        self.timer_label.pack(pady=2, fill=tk.X)
        self.pomodoro_count_label = ttk.Label(self.timer_controls_frame, text=f"Cycle: 0 / {self.config_manager.get('pomodoros_per_long_break')}", anchor="center") # Style will apply based on session
        self.pomodoro_count_label.pack(pady=(0,5), fill=tk.X)
        
        self.current_task_display_label = ttk.Label(self.timer_controls_frame, text="Current Task: None", style="CurrentTask.TLabel", anchor="center", wraplength=400) # Uses specific style
        self.current_task_display_label.pack(pady=(5,5), fill=tk.X, padx=10)

        self.controls_grid_frame = ttk.Frame(self.timer_controls_frame) # Style will apply based on session
        self.controls_grid_frame.pack(pady=5)
        self.start_button = ttk.Button(self.controls_grid_frame, text="Start", command=self.start_timer, width=12)
        self.start_button.grid(row=0, column=0, padx=3)
        self.pause_button = ttk.Button(self.controls_grid_frame, text="Pause", command=self.pause_timer, width=12, state=tk.DISABLED)
        self.pause_button.grid(row=0, column=1, padx=3)
        self.reset_button = ttk.Button(self.controls_grid_frame, text="Reset", command=self.reset_current_session, width=12)
        self.reset_button.grid(row=0, column=2, padx=3)
        self.skip_button = ttk.Button(self.controls_grid_frame, text="Skip Break", command=self.skip_break, width=12, state=tk.DISABLED)
        self.skip_button.grid(row=0, column=3, padx=3)

        task_section_frame = ttk.LabelFrame(left_pane_frame, text="Task Management") # Style "TLabelframe"
        task_section_frame.grid(row=1, column=0, sticky="nsew", pady=5)
        task_section_frame.columnconfigure(0, weight=1) 
        task_section_frame.rowconfigure(1, weight=1) 

        task_input_frame = ttk.Frame(task_section_frame) # Style "TFrame"
        task_input_frame.grid(row=0, column=0, sticky="ew", pady=5, padx=5)
        task_input_frame.columnconfigure(0, weight=1)
        self.task_entry = ttk.Entry(task_input_frame, width=30) # Style "TEntry"
        self.task_entry.grid(row=0, column=0, sticky="ew", padx=(0,5))
        self.task_entry.bind("<Return>", lambda event: self.add_task_gui())
        self.task_pomodoro_est_label = ttk.Label(task_input_frame, text="Est:") # Style "TLabel"
        self.task_pomodoro_est_label.grid(row=0, column=1, padx=(5,0))
        self.task_pomodoro_est_spinbox = ttk.Spinbox(task_input_frame, from_=1, to=20, width=3, justify=tk.CENTER) # Style "TSpinbox"
        self.task_pomodoro_est_spinbox.set("1")
        self.task_pomodoro_est_spinbox.grid(row=0, column=2, padx=(0,5))
        self.add_task_button = ttk.Button(task_input_frame, text="Add Task", command=self.add_task_gui) # Style "TButton"
        self.add_task_button.grid(row=0, column=3)

        task_display_notebook = ttk.Notebook(task_section_frame) # Default ttk.Notebook styles apply
        task_display_notebook.grid(row=1, column=0, sticky="nsew", pady=5, padx=5)

        tasks_tab_frame = ttk.Frame(task_display_notebook) # Style "TFrame"
        tasks_tab_frame.columnconfigure(0, weight=1)
        tasks_tab_frame.rowconfigure(0, weight=1)
        task_display_notebook.add(tasks_tab_frame, text="Scheduled Tasks")

        self.task_tree = ttk.Treeview(tasks_tab_frame, columns=("text", "est", "done_p"), show="headings", selectmode="browse") # Style "Treeview"
        self.task_tree.heading("text", text="Task (for selected date)")
        self.task_tree.heading("est", text="Est.")
        self.task_tree.heading("done_p", text="Done")
        self.task_tree.column("text", width=250, stretch=tk.YES)
        self.task_tree.column("est", width=40, anchor="center")
        self.task_tree.column("done_p", width=50, anchor="center")
        self.task_tree.grid(row=0, column=0, sticky="nsew")
        self.task_tree.bind("<<TreeviewSelect>>", self.on_task_select)
        self.task_tree.bind("<ButtonPress-1>", self.on_task_drag_start)
        self.task_tree.bind("<B1-Motion>", self.on_task_drag_motion)
        self.task_tree.bind("<ButtonRelease-1>", self.on_task_drag_release)
        
        task_tree_scrollbar = ttk.Scrollbar(tasks_tab_frame, orient="vertical", command=self.task_tree.yview) # Default ttk.Scrollbar styles
        self.task_tree.configure(yscrollcommand=task_tree_scrollbar.set)
        task_tree_scrollbar.grid(row=0, column=1, sticky="ns")

        notes_tab_frame = ttk.Frame(task_display_notebook) # Style "TFrame"
        notes_tab_frame.columnconfigure(0, weight=1)
        notes_tab_frame.rowconfigure(0, weight=1)
        task_display_notebook.add(notes_tab_frame, text="Notes")
        self.task_notes_text = scrolledtext.ScrolledText(notes_tab_frame, wrap=tk.WORD, height=5, width=30,
                                                         bg=self.COLOR_ENTRY_BG, fg=self.COLOR_FG, insertbackground=self.COLOR_FG, # Direct color assignment for ScrolledText
                                                         font=("Segoe UI", 9), relief=tk.FLAT, borderwidth=2)
        self.task_notes_text.pack(expand=True, fill=tk.BOTH, padx=2, pady=2)
        self.task_notes_text.bind("<FocusOut>", self.save_task_notes_auto)
        self.task_notes_text.config(state=tk.DISABLED)

        task_button_frame = ttk.Frame(task_section_frame) # Style "TFrame"
        task_button_frame.grid(row=2, column=0, sticky="ew", pady=5, padx=5)
        self.select_work_task_button = ttk.Button(task_button_frame, text="Work on", command=self.set_current_work_task, state=tk.DISABLED, width=10) # Style "TButton"
        self.select_work_task_button.pack(side=tk.LEFT, padx=2)
        self.mark_done_button = ttk.Button(task_button_frame, text="Done", command=self.toggle_task_done_gui, state=tk.DISABLED, width=8) # Style "TButton"
        self.mark_done_button.pack(side=tk.LEFT, padx=2)
        self.edit_task_button = ttk.Button(task_button_frame, text="Edit", command=self.edit_task_gui, state=tk.DISABLED, width=8) # Style "TButton"
        self.edit_task_button.pack(side=tk.LEFT, padx=2)
        self.delete_task_button = ttk.Button(task_button_frame, text="Delete", command=self.delete_task_gui, state=tk.DISABLED, width=8) # Style "TButton"
        self.delete_task_button.pack(side=tk.LEFT, padx=2)
        self.schedule_task_button = ttk.Button(task_button_frame, text="Schedule", command=self.open_schedule_dialog_for_selected_task, state=tk.DISABLED, width=10) # Style "TButton"
        self.schedule_task_button.pack(side=tk.LEFT, padx=2)

        right_pane_frame = ttk.Frame(main_paned_window, padding=5) # Style "TFrame"
        right_pane_frame.columnconfigure(0, weight=1)
        right_pane_frame.rowconfigure(1, weight=1) 
        main_paned_window.add(right_pane_frame, minsize=350)

        self.datetime_label = ttk.Label(right_pane_frame, text="", style="DateTime.TLabel", anchor="e") # Specific style
        self.datetime_label.grid(row=0, column=0, sticky="ew", pady=(0,5), padx=5)

        calendar_outer_frame = ttk.LabelFrame(right_pane_frame, text="Calendar") # Style "TLabelframe"
        calendar_outer_frame.grid(row=1, column=0, sticky="new", pady=5, padx=5)
        calendar_outer_frame.columnconfigure(0, weight=1)

        if TKCALENDAR_AVAILABLE:
            # tkcalendar.Calendar does not use ttk styles, so colors are set directly
            self.cal = Calendar(calendar_outer_frame, selectmode='day', date_pattern='yyyy-mm-dd',
                                year=self.selected_calendar_date.year, month=self.selected_calendar_date.month, day=self.selected_calendar_date.day,
                                background=self.COLOR_CALENDAR_HEADER, foreground='white', # Using theme colors
                                headersbackground=self.COLOR_CALENDAR_HEADER, headersforeground='white',
                                bordercolor=self.COLOR_ACCENT, weekendbackground=self.COLOR_BG, weekendforeground=self.COLOR_CALENDAR_WEEKEND,
                                othermonthbackground=self.COLOR_ENTRY_BG, othermonthwebackground=self.COLOR_ENTRY_BG, 
                                othermonthforeground='gray60', othermonthweforeground='gray50',
                                normalbackground=self.COLOR_TREEVIEW_BG, normalforeground='white', # Normal day bg/fg
                                selectedbackground=self.COLOR_ACCENT, selectedforeground=self.COLOR_BG, # Selected day bg/fg (using COLOR_BG for text on accent)
                                font=("Segoe UI", 9), firstweekday='monday')
            self.cal.pack(fill="x", expand=True, padx=5, pady=5)
            self.cal.bind("<<CalendarSelected>>", self.on_calendar_date_selected)
        else:
            ttk.Label(calendar_outer_frame, text="Calendar feature disabled (tkcalendar not found).", foreground="orange").pack(padx=5, pady=10) # Style "TLabel"

        self.daily_summary_labelframe = ttk.LabelFrame(right_pane_frame, text=f"Summary for {self.selected_calendar_date.strftime('%Y-%m-%d')}") # Style "TLabelframe"
        self.daily_summary_labelframe.grid(row=2, column=0, sticky="nsew", pady=5, padx=5)
        self.daily_summary_labelframe.columnconfigure(0, weight=1)
        self.daily_summary_labelframe.rowconfigure(0, weight=1)
        right_pane_frame.rowconfigure(2, weight=1)

        self.daily_summary_text = scrolledtext.ScrolledText(self.daily_summary_labelframe, wrap=tk.WORD, height=8,
                                                            bg=self.COLOR_ENTRY_BG, fg=self.COLOR_FG, # Direct color assignment
                                                            font=("Segoe UI", 9), relief=tk.FLAT, borderwidth=1)
        self.daily_summary_text.pack(expand=True, fill=tk.BOTH, padx=2, pady=2)
        self.daily_summary_text.config(state=tk.DISABLED)

        bottom_controls_frame = ttk.Frame(right_pane_frame) # Style "TFrame"
        bottom_controls_frame.grid(row=3, column=0, sticky="ew", pady=(10,0), padx=5)
        bottom_controls_frame.columnconfigure(1, weight=1)

        self.reset_cycle_button = ttk.Button(bottom_controls_frame, text="Reset Cycle Count", command=self.reset_pomodoro_cycle_count, width=18) # Style "TButton"
        self.reset_cycle_button.grid(row=0, column=0, sticky="w", padx=(0,10))
        
        settings_button = ttk.Button(bottom_controls_frame, text="⚙️ Settings", command=self.open_settings, width=12) # Style "TButton"
        settings_button.grid(row=0, column=2, sticky="e")

        # --- Gemini Chat Frame ---
        gemini_chat_frame = ttk.LabelFrame(right_pane_frame, text="Gemini Assistant")
        gemini_chat_frame.grid(row=4, column=0, sticky="nsew", pady=(10,5), padx=5) # Ensure row index is correct
        right_pane_frame.rowconfigure(4, weight=1) # Allow chat frame to expand
        gemini_chat_frame.columnconfigure(0, weight=1)
        gemini_chat_frame.rowconfigure(0, weight=1) # Allow ScrolledText to expand

        self.gemini_chat_history = scrolledtext.ScrolledText(
            gemini_chat_frame, wrap=tk.WORD, height=10, state=tk.DISABLED,
            bg=self.COLOR_ENTRY_BG, fg=self.COLOR_FG,
            font=("Segoe UI", 9), relief=tk.FLAT, borderwidth=1
        )
        self.gemini_chat_history.pack(pady=5, padx=5, expand=True, fill=tk.BOTH)
        # Alternative grid layout for ScrolledText if preferred:
        # self.gemini_chat_history.grid(row=0, column=0, sticky="nsew", pady=5, padx=5)


        # Define tags for chat styling
        self.gemini_chat_history.tag_configure("user", foreground=self.COLOR_ACCENT)
        self.gemini_chat_history.tag_configure("gemini", foreground=self.COLOR_SHORT_BREAK)
        self.gemini_chat_history.tag_configure("error", foreground=self.COLOR_CALENDAR_WEEKEND)
        self.gemini_chat_history.tag_configure("info", foreground="gray")

        chat_input_frame = ttk.Frame(gemini_chat_frame)
        chat_input_frame.pack(pady=(0,5), padx=5, fill=tk.X)
        # chat_input_frame.grid(row=1, column=0, sticky="ew", pady=(0,5), padx=5) # if using grid for ScrolledText
        chat_input_frame.columnconfigure(0, weight=1)

        self.gemini_chat_input = ttk.Entry(chat_input_frame, font=("Segoe UI", 10))
        self.gemini_chat_input.grid(row=0, column=0, sticky="ew", padx=(0,5))
        self.gemini_chat_input.bind("<Return>", self.on_send_gemini_message)

        self.gemini_send_button = ttk.Button(chat_input_frame, text="Send", command=self.on_send_gemini_message)
        self.gemini_send_button.grid(row=0, column=1)
        
        self.update_ui_for_session() 

    def update_current_datetime_display(self):
        now = datetime.datetime.now()
        self.datetime_label.config(text=now.strftime("%A, %B %d, %Y  %I:%M:%S %p")) # Uses DateTime.TLabel style
        self.root.after(1000, self.update_current_datetime_display) 


    def on_calendar_date_selected(self, event=None):
        if not TKCALENDAR_AVAILABLE: return
        new_date_str = self.cal.get_date()
        try:
            self.selected_calendar_date = datetime.datetime.strptime(new_date_str, '%Y-%m-%d').date()
        except ValueError: 
             try:
                self.selected_calendar_date = datetime.datetime.strptime(new_date_str, '%m/%d/%y').date() 
             except ValueError:
                print(f"Error parsing date from calendar: {new_date_str}")
                return

        self.daily_summary_labelframe.config(text=f"Summary for {self.selected_calendar_date.strftime('%Y-%m-%d')}") # Label of TLabelframe
        self.refresh_task_list_and_daily_summary()


    def refresh_task_list_and_daily_summary(self):
        for i in self.task_tree.get_children():
            self.task_tree.delete(i)
        
        active_tasks_for_date = self.task_manager.get_tasks_by_scheduled_date(self.selected_calendar_date)
        
        display_tasks = list(active_tasks_for_date) 
        is_today = (self.selected_calendar_date == datetime.date.today())
        
        if is_today:
            unscheduled_active = self.task_manager.get_unscheduled_active_tasks()
            existing_ids = {t.id for t in display_tasks}
            for ut in unscheduled_active:
                if ut.id not in existing_ids:
                    display_tasks.append(ut) 

        if display_tasks:
            header_text = f"Tasks for {self.selected_calendar_date.strftime('%b %d, %Y')}" if not is_today else "Today's & Unscheduled Tasks"
            self.task_tree.heading("text", text=header_text)
            for task in display_tasks:
                self.task_tree.insert("", tk.END, values=(task.text, task.estimated_pomodoros, task.completed_pomodoros), tags=(task.id,))
        else:
             self.task_tree.heading("text", text=f"No active tasks for {self.selected_calendar_date.strftime('%b %d, %Y')}")

        completed_tasks_for_date = self.task_manager.get_completed_tasks(scheduled_date_obj=self.selected_calendar_date)

        self.daily_summary_text.config(state=tk.NORMAL)
        self.daily_summary_text.delete(1.0, tk.END)
        
        summary_content = []
        pomos_for_date = 0
        focus_minutes_for_date = 0.0 
        work_duration = self.config_manager.get("work_duration")

        log_entries_for_date = [
            entry for entry in self.session_log 
            if entry.get("session_for_date") == self.selected_calendar_date.isoformat() 
        ]

        if log_entries_for_date:
            summary_content.append("--- Pomodoro Sessions ---")
            for entry in log_entries_for_date:
                if entry["type"] == self.WORK and not entry.get("skipped", False):
                    pomos_for_date += 1
                    logged_duration = entry.get("duration_minutes")
                    duration_to_add = work_duration 
                    if isinstance(logged_duration, (int, float)) and logged_duration >= 0:
                        duration_to_add = logged_duration
                    
                    focus_minutes_for_date += duration_to_add
                    task_info = f" (Task: {entry.get('task_text', 'N/A')[:30]})" if entry.get('task_text') else ""
                    summary_content.append(f"  - Work: {duration_to_add:.1f} min{task_info}")

                elif entry["type"] != self.WORK and not entry.get("skipped", False):
                    logged_break_duration = entry.get("duration_minutes", 0)
                    break_duration_to_display = logged_break_duration if isinstance(logged_break_duration, (int,float)) and logged_break_duration >=0 else 0
                    summary_content.append(f"  - {entry['type']}: {break_duration_to_display:.1f} min")
            summary_content.append("\n")


        summary_content.append(f"Total Pomodoros Completed: {pomos_for_date}")
        total_hours = int(focus_minutes_for_date // 60)
        total_minutes_rem = int(round(focus_minutes_for_date % 60)) 
        summary_content.append(f"Total Focus Time: {total_hours}h {total_minutes_rem}m")
        summary_content.append("\n--- Tasks Completed on this Day ---")
        
        # Filter completed_tasks_for_date to only show tasks truly completed ON this day
        truly_completed_this_day = [
            task for task in completed_tasks_for_date 
            if task.completed_at and task.completed_at.startswith(self.selected_calendar_date.isoformat())
        ]

        if truly_completed_this_day:
            for task in truly_completed_this_day:
                 summary_content.append(f"  [X] {task.text} (Actual Pomos: {task.completed_pomodoros})")
        else:
            summary_content.append("  No tasks marked complete for this day.")
            
        summary_content.append("\n--- Active Tasks Scheduled for this Day ---")
        active_task_texts_in_log = {entry.get('task_text') for entry in log_entries_for_date if entry.get('task_text') and entry["type"] == self.WORK}
        
        active_for_day_not_in_log = [task for task in display_tasks if not task.done and task.text not in active_task_texts_in_log]

        if active_for_day_not_in_log:
            for task in active_for_day_not_in_log:
                 summary_content.append(f"  [ ] {task.text} (Est: {task.estimated_pomodoros})")
        elif not display_tasks: 
            summary_content.append("  None.")
        
        self.daily_summary_text.insert(tk.END, "\n".join(summary_content))
        self.daily_summary_text.config(state=tk.DISABLED)
        self.on_task_select() 

    def open_schedule_dialog_for_selected_task(self):
        selected_item = self.task_tree.focus()
        if not selected_item:
            messagebox.showwarning("No Task", "Please select a task from the list to schedule.", parent=self.root)
            return
        tags = self.task_tree.item(selected_item, "tags")
        if not tags : return 
        task_id = tags[0]
        task = self.task_manager.get_task_by_id(task_id)
        if not task: return

        if not TKCALENDAR_AVAILABLE:
            date_str = simpledialog.askstring("Schedule Task", f"Enter schedule date for '{task.text}' (YYYY-MM-DD, or leave blank to unschedule):", 
                                              initialvalue=task.scheduled_date or "", parent=self.root)
            if date_str is not None: 
                if not date_str.strip(): 
                    self.task_manager.update_task(task.id, scheduled_date=None)
                    self.refresh_task_list_and_daily_summary()
                else:
                    try:
                        datetime.datetime.strptime(date_str, "%Y-%m-%d")
                        self.task_manager.update_task(task.id, scheduled_date=date_str)
                        self.refresh_task_list_and_daily_summary()
                    except ValueError:
                        messagebox.showerror("Invalid Date", "Date format must be YYYY-MM-DD.", parent=self.root)
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Schedule Task: {task.text[:30]}")
        dialog.configure(bg=self.COLOR_BG) # Direct bg config for Toplevel
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Select Scheduled Date:", background=self.COLOR_BG, foreground=self.COLOR_FG).pack(padx=10, pady=(10,5)) # Explicit Label for Toplevel
        
        initial_date_obj = None
        today = datetime.date.today()
        if task.scheduled_date:
            try: initial_date_obj = datetime.datetime.strptime(task.scheduled_date, "%Y-%m-%d").date()
            except ValueError: pass
        
        date_entry_year = initial_date_obj.year if initial_date_obj else today.year
        date_entry_month = initial_date_obj.month if initial_date_obj else today.month
        date_entry_day = initial_date_obj.day if initial_date_obj else today.day

        # DateEntry is from tkcalendar, not ttk, so colors are direct
        date_entry = DateEntry(dialog, width=12, background=self.COLOR_ACCENT, foreground=self.COLOR_LONG_BREAK_FG, # Using LongBreak FG for contrast on Accent
                               disabledbackground=self.COLOR_BUTTON, disabledforeground=self.COLOR_DISABLED_BUTTON_TEXT,
                               borderwidth=2, date_pattern='yyyy-mm-dd',
                               year=date_entry_year, month=date_entry_month, day=date_entry_day,
                               allow_none=True) 
        if initial_date_obj:
            date_entry.set_date(initial_date_obj)
        else:
            date_entry.delete(0, tk.END) 

        date_entry.pack(padx=10, pady=5)

        def _save_schedule():
            new_scheduled_date_obj = date_entry.get_date() 
            self.task_manager.update_task(task.id, scheduled_date=new_scheduled_date_obj)
            self.refresh_task_list_and_daily_summary()
            dialog.destroy()
            
        btn_frame = ttk.Frame(dialog, style="TFrame") # Use TFrame style for BG
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Save Schedule", command=_save_schedule).pack(side=tk.LEFT, padx=5) # TButton style
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5) # TButton style


    def add_task_gui(self):
        text = self.task_entry.get()
        try: est_pomos = int(self.task_pomodoro_est_spinbox.get())
        except ValueError: est_pomos = 1
            
        if text:
            schedule_to_date = self.selected_calendar_date
            self.task_manager.add_task(text, est_pomos, scheduled_date=schedule_to_date)
            self.task_entry.delete(0, tk.END)
            self.task_pomodoro_est_spinbox.set("1")
            self.refresh_task_list_and_daily_summary()
        else:
            messagebox.showwarning("Input Error", "Task text cannot be empty.", parent=self.root)

    def on_task_select(self, event=None):
        selected_item = self.task_tree.focus()
        if selected_item:
            tags = self.task_tree.item(selected_item, "tags")
            if not tags: self._clear_task_selection_ui(); return

            task_id = tags[0]
            task = self.task_manager.get_task_by_id(task_id)

            if task:
                self.mark_done_button.config(state=tk.NORMAL)
                self.delete_task_button.config(state=tk.NORMAL)
                self.edit_task_button.config(state=tk.NORMAL)
                self.schedule_task_button.config(state=tk.NORMAL)
                self.select_work_task_button.config(state=tk.NORMAL if not task.done else tk.DISABLED)
                
                self.task_notes_text.config(state=tk.NORMAL)
                self.task_notes_text.delete(1.0, tk.END)
                self.task_notes_text.insert(tk.END, task.notes or "")
            else: self._clear_task_selection_ui()
        else: self._clear_task_selection_ui()

    def _clear_task_selection_ui(self):
        self.mark_done_button.config(state=tk.DISABLED)
        self.delete_task_button.config(state=tk.DISABLED)
        self.edit_task_button.config(state=tk.DISABLED)
        self.schedule_task_button.config(state=tk.DISABLED)
        self.select_work_task_button.config(state=tk.DISABLED)
        self.task_notes_text.delete(1.0, tk.END)
        self.task_notes_text.config(state=tk.DISABLED)

    def save_task_notes_auto(self, event=None):
        selected_item = self.task_tree.focus()
        if not selected_item: return
        tags = self.task_tree.item(selected_item, "tags")
        if not tags: return
        task_id = tags[0]
        task = self.task_manager.get_task_by_id(task_id)
        if task:
            current_notes = self.task_notes_text.get(1.0, tk.END).strip()
            if task.notes != current_notes:
                self.task_manager.update_task(task_id, notes=current_notes)

    def toggle_task_done_gui(self):
        selected_item = self.task_tree.focus()
        if not selected_item: return
        tags = self.task_tree.item(selected_item, "tags")
        if not tags: return
        task_id = tags[0]
        self.task_manager.toggle_task_done(task_id)
        task = self.task_manager.get_task_by_id(task_id)
        if self.current_task_id == task_id and task and task.done:
            self.current_task_id = None
            self.current_task_display_label.config(text="Current Task: None")
        self.refresh_task_list_and_daily_summary()

    def edit_task_gui(self):
        selected_item = self.task_tree.focus()
        if not selected_item: return
        tags = self.task_tree.item(selected_item, "tags")
        if not tags: return
        task_id = tags[0]
        task = self.task_manager.get_task_by_id(task_id)
        if not task: return

        edit_dialog = tk.Toplevel(self.root) 
        edit_dialog.title("Edit Task")
        edit_dialog.configure(bg=self.COLOR_BG); edit_dialog.transient(self.root); edit_dialog.grab_set() # Direct BG for Toplevel
        
        ttk.Label(edit_dialog, text="Task Text:", background=self.COLOR_BG, foreground=self.COLOR_FG).grid(row=0, column=0, padx=10, pady=5, sticky="w") # Explicit Label for Toplevel
        edit_text_var = tk.StringVar(value=task.text)
        ttk.Entry(edit_dialog, textvariable=edit_text_var, width=40).grid(row=0, column=1, padx=10, pady=5, sticky="ew") # TEntry style

        ttk.Label(edit_dialog, text="Est. Pomodoros:", background=self.COLOR_BG, foreground=self.COLOR_FG).grid(row=1, column=0, padx=10, pady=5, sticky="w") # Explicit Label for Toplevel
        edit_est_var = tk.StringVar(value=str(task.estimated_pomodoros))
        ttk.Spinbox(edit_dialog, from_=1, to=20, textvariable=edit_est_var, width=5).grid(row=1, column=1, padx=10, pady=5, sticky="w") # TSpinbox style

        sched_date_entry = None 
        if TKCALENDAR_AVAILABLE:
            ttk.Label(edit_dialog, text="Scheduled Date:", background=self.COLOR_BG, foreground=self.COLOR_FG).grid(row=2, column=0, padx=10, pady=5, sticky="w") # Explicit Label for Toplevel
            initial_sched_date_obj = None
            today = datetime.date.today()
            if task.scheduled_date:
                try: initial_sched_date_obj = datetime.datetime.strptime(task.scheduled_date, "%Y-%m-%d").date()
                except ValueError: pass
            
            date_entry_year = initial_sched_date_obj.year if initial_sched_date_obj else today.year
            date_entry_month = initial_sched_date_obj.month if initial_sched_date_obj else today.month
            date_entry_day = initial_sched_date_obj.day if initial_sched_date_obj else today.day

            # DateEntry is from tkcalendar, not ttk, so colors are direct
            sched_date_entry = DateEntry(edit_dialog, date_pattern='yyyy-mm-dd', 
                                         year=date_entry_year, month=date_entry_month, day=date_entry_day,
                                         background=self.COLOR_ACCENT, foreground=self.COLOR_LONG_BREAK_FG, # Using LongBreak FG for contrast on Accent
                                         disabledbackground=self.COLOR_BUTTON, disabledforeground=self.COLOR_DISABLED_BUTTON_TEXT,
                                         allow_none=True)
            if initial_sched_date_obj:
                sched_date_entry.set_date(initial_sched_date_obj)
            else:
                sched_date_entry.delete(0, tk.END) 

            sched_date_entry.grid(row=2, column=1, padx=10, pady=5, sticky="w")

        def save_edit():
            new_text = edit_text_var.get().strip()
            try: new_est = int(edit_est_var.get())
            except ValueError: messagebox.showerror("Input Error", "Invalid Est. Pomodoros.", parent=edit_dialog); return

            new_sched_date_to_save = None 
            if TKCALENDAR_AVAILABLE and sched_date_entry:
                new_sched_date_to_save = sched_date_entry.get_date() 
            
            if new_text:
                self.task_manager.update_task(task_id, text=new_text, estimated_pomodoros=new_est, scheduled_date=new_sched_date_to_save)
                self.refresh_task_list_and_daily_summary()
                if self.current_task_id == task_id: self.current_task_display_label.config(text=f"Working on: {new_text[:40]}...") # Uses CurrentTask.TLabel style
                edit_dialog.destroy()
            else: messagebox.showerror("Input Error", "Task text cannot be empty.", parent=edit_dialog)

        button_frame = ttk.Frame(edit_dialog, style="TFrame"); button_frame.grid(row=3 if TKCALENDAR_AVAILABLE else 2, column=0, columnspan=2, pady=10) # TFrame for BG
        ttk.Button(button_frame, text="Save", command=save_edit).pack(side=tk.LEFT, padx=5) # TButton style
        ttk.Button(button_frame, text="Cancel", command=edit_dialog.destroy).pack(side=tk.LEFT, padx=5) # TButton style
        edit_dialog.columnconfigure(1, weight=1)

    def delete_task_gui(self):
        selected_item = self.task_tree.focus()
        if not selected_item: return
        tags = self.task_tree.item(selected_item, "tags")
        if not tags: return
        task_id = tags[0]
        task = self.task_manager.get_task_by_id(task_id)
        if task and messagebox.askyesno("Confirm Delete", f"Delete task: '{task.text}'?", parent=self.root):
            self.task_manager.remove_task(task_id)
            if self.current_task_id == task_id:
                self.current_task_id = None
                self.current_task_display_label.config(text="Current Task: None")
            self.refresh_task_list_and_daily_summary()
            self._clear_task_selection_ui()


    def set_current_work_task(self):
        selected_item = self.task_tree.focus()
        if not selected_item: messagebox.showwarning("No Task", "Select a task to work on.", parent=self.root); return
        tags = self.task_tree.item(selected_item, "tags")
        if not tags: return
        task_id = tags[0]
        task = self.task_manager.get_task_by_id(task_id)
        if task and not task.done:
            self.current_task_id = task.id
            self.current_task_display_label.config(text=f"Working on: {task.text[:40]}{'...' if len(task.text) > 40 else ''}")
            
            if not task.scheduled_date:
                 if messagebox.askyesno("Schedule Task?", f"Task '{task.text}' is unscheduled. Schedule it for today to track focus on this day?", parent=self.root):
                    self.task_manager.update_task(task.id, scheduled_date=datetime.date.today())
                    self.refresh_task_list_and_daily_summary() 
        elif task and task.done:
            messagebox.showinfo("Task Done", "This task is already completed.", parent=self.root)


    def start_timer(self, event=None): 
        if self.is_running and self.paused: 
            self.paused = False
            self.start_button.config(text="Start", state=tk.DISABLED)
            self.pause_button.config(text="Pause", state=tk.NORMAL)
            self.countdown()
        elif not self.is_running: 
            self.is_running = True; self.paused = False
            self.start_button.config(state=tk.DISABLED)
            self.pause_button.config(state=tk.NORMAL)
            self.reset_button.config(state=tk.NORMAL)
            self.skip_button.config(state=tk.NORMAL if self.current_session_type != self.WORK else tk.DISABLED)
            
            if self.current_session_type == self.WORK and self.current_task_id is None:
                 active_tasks_for_display = self.task_manager.get_tasks_by_scheduled_date(self.selected_calendar_date)
                 if self.selected_calendar_date == datetime.date.today(): 
                    # Create a new list before extending to avoid modifying the original if it's a direct reference
                    active_tasks_for_display = list(active_tasks_for_display)
                    active_tasks_for_display.extend([t for t in self.task_manager.get_unscheduled_active_tasks() if t.id not in {task.id for task in active_tasks_for_display}])


                 if active_tasks_for_display: 
                    if not messagebox.askyesno("No Task Selected", "No task is set as current. Continue anyway?", parent=self.root):
                        self.is_running = False; self.paused = True 
                        self.start_button.config(state=tk.NORMAL); self.pause_button.config(state=tk.DISABLED)
                        return
            self.countdown()
            
    def pause_timer(self, event=None): 
        if self.is_running and not self.paused:
            self.paused = True
            if self.timer_id: self.root.after_cancel(self.timer_id)
            self.start_button.config(text="Resume", state=tk.NORMAL)
            self.pause_button.config(state=tk.DISABLED)

    def reset_current_session(self, event=None): 
        if self.timer_id: self.root.after_cancel(self.timer_id)
        self.is_running = False; self.paused = False
        
        dur_key_map = {self.WORK:"work_duration", self.SHORT_BREAK:"short_break_duration", self.LONG_BREAK:"long_break_duration"}
        dur_key = dur_key_map.get(self.current_session_type, "work_duration") 
        self.time_left = self.config_manager.get(dur_key) * 60
        
        self.update_timer_display()
        self.start_button.config(text="Start", state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED)
        self.skip_button.config(state=tk.NORMAL if self.current_session_type != self.WORK else tk.DISABLED)
        self.update_ui_for_session()

    def skip_break(self, event=None): 
        if self.current_session_type != self.WORK:
            if self.timer_id: self.root.after_cancel(self.timer_id)
            self.is_running = False; self.paused = False
            self.log_session(skipped=True)
            self.next_session(skipped_break=True)

    def reset_pomodoro_cycle_count(self):
        if messagebox.askyesno("Reset Cycle", "Reset Pomodoro cycle count to 0?", parent=self.root):
            self.pomodoros_completed_cycle = 0
            self.update_pomodoro_count_display()

    def countdown(self):
        if self.is_running and not self.paused and self.time_left > 0:
            self.time_left -= 1
            self.update_timer_display()
            self.timer_id = self.root.after(1000, self.countdown)
        elif self.time_left <= 0:
            self.is_running = False
            self.log_session()
            self.next_session()

    def log_session(self, skipped=False):
        task_text = ""
        current_task_obj = None
        session_for_date_str = datetime.date.today().isoformat() 

        if self.current_session_type == self.WORK and self.current_task_id:
            current_task_obj = self.task_manager.get_task_by_id(self.current_task_id)
            if current_task_obj: 
                task_text = current_task_obj.text
                if current_task_obj.scheduled_date: 
                    session_for_date_str = current_task_obj.scheduled_date
        
        dur_key_map = {self.WORK:"work_duration", self.SHORT_BREAK:"short_break_duration", self.LONG_BREAK:"long_break_duration"}
        dur_key = dur_key_map.get(self.current_session_type, "work_duration")
        session_config_duration = self.config_manager.get(dur_key)
        
        actual_duration_minutes = 0.0 
        if skipped:
            actual_duration_minutes = 0.0
        elif self.time_left > 0 : 
            completed_seconds = (session_config_duration * 60) - self.time_left
            actual_duration_minutes = round(completed_seconds / 60.0, 1)
        else: 
            actual_duration_minutes = float(session_config_duration)

        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(), "type": self.current_session_type,
            "duration_minutes": actual_duration_minutes,
            "task_id": self.current_task_id if self.current_session_type == self.WORK else None,
            "task_text": task_text if self.current_session_type == self.WORK else None,
            "skipped": skipped,
            "session_for_date": session_for_date_str
        }
        self.session_log.append(log_entry)
        self.config_manager.save_session_log(self.session_log)
        self.refresh_task_list_and_daily_summary() 

    def next_session(self, skipped_break=False):
        if self.timer_id: self.root.after_cancel(self.timer_id)
        
        sound_config_key = self.WORK if self.current_session_type == self.WORK else "Break"
        self._play_sound(sound_config_key)

        if self.current_session_type == self.WORK:
            self.pomodoros_completed_cycle += 1
            if self.current_task_id:
                self.task_manager.increment_pomodoro_for_task(self.current_task_id)

            if self.pomodoros_completed_cycle % self.config_manager.get("pomodoros_per_long_break") == 0:
                self.current_session_type = self.LONG_BREAK
                self.time_left = self.config_manager.get("long_break_duration") * 60
            else:
                self.current_session_type = self.SHORT_BREAK
                self.time_left = self.config_manager.get("short_break_duration") * 60
        else: 
            self.current_session_type = self.WORK
            self.time_left = self.config_manager.get("work_duration") * 60
            if skipped_break and self.pomodoros_completed_cycle > 0 and \
               (self.pomodoros_completed_cycle % self.config_manager.get("pomodoros_per_long_break") == 0):
                 self.pomodoros_completed_cycle = 0
        
        self.update_pomodoro_count_display()
        self.update_timer_display()
        self.update_ui_for_session()

        self.start_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED)
        self.skip_button.config(state=tk.NORMAL if self.current_session_type != self.WORK else tk.DISABLED)

        if self.config_manager.get("auto_start_next_session") and not skipped_break:
            self.start_timer()
        else:
            self.is_running = False; self.paused = False
            self.root.deiconify(); self.root.attributes('-topmost', 1);
            self.root.after(100, lambda: self.root.attributes('-topmost', self.always_on_top_var.get()))
            if PLAYSOUND_AVAILABLE: # Only bell if sounds are generally available, to avoid annoyance if user disabled them
                self.root.bell() 
            
    def _play_sound(self, sound_type_for_config): 
        if not PLAYSOUND_AVAILABLE or not self.config_manager.get("sound_enabled"): return
        sound_key = "work_end_sound" if sound_type_for_config == self.WORK else "break_end_sound"
        
        sound_file_path_from_config = self.config_manager.get(sound_key)
        if not sound_file_path_from_config: return

        if os.path.isabs(sound_file_path_from_config):
            actual_sound_path = sound_file_path_from_config
        else:
            actual_sound_path = resource_path(sound_file_path_from_config) # Use resource_path

        if os.path.exists(actual_sound_path):
            try:
                playsound(actual_sound_path, block=False)
            except Exception as e:
                print(f"Error playing sound {actual_sound_path}: {e}")
                detail_message = str(e) # Default detail message
                custom_message = f"Could not play sound: {os.path.basename(actual_sound_path)}"

                if "can't find a MCI Video device" in str(e).lower() and sys.platform == "win32":
                     custom_message = "MCI Error: Ensure audio drivers are working and file format (MP3/WAV) is supported."
                elif ("gstreamer" in str(e).lower() or "gst" in str(e).lower()) and sys.platform.startswith("linux"): 
                     custom_message = "GStreamer Error: Could not play sound. Ensure GStreamer plugins for MP3/WAV are installed."
                
                # Check if messagebox can take 'detail' argument (newer Tk versions)
                try:
                    messagebox.showwarning("Sound Playback Issue", custom_message, detail=detail_message, parent=self.root)
                except tk.TclError: # Older Tk, 'detail' option might not exist
                    messagebox.showwarning("Sound Playback Issue", f"{custom_message}\nDetails: {detail_message}", parent=self.root)
        else:
            messagebox.showwarning("Sound File Missing", f"Sound file not found: {actual_sound_path}\nPlease check settings.", parent=self.root)


    def update_timer_display(self):
        minutes, seconds = divmod(self.time_left, 60)
        self.timer_label.config(text=f"{int(minutes):02d}:{int(seconds):02d}")

    def update_pomodoro_count_display(self):
        pomos_per_cycle = self.config_manager.get("pomodoros_per_long_break")
        current_cycle_pomos = self.pomodoros_completed_cycle % pomos_per_cycle
        if self.current_session_type == self.LONG_BREAK and current_cycle_pomos == 0 and self.pomodoros_completed_cycle > 0:
             current_cycle_pomos = pomos_per_cycle
        elif self.current_session_type != self.WORK and current_cycle_pomos == 0 and self.pomodoros_completed_cycle > 0 and (self.pomodoros_completed_cycle % pomos_per_cycle == 0):
             current_cycle_pomos = pomos_per_cycle
        self.pomodoro_count_label.config(text=f"Cycle: {current_cycle_pomos} / {pomos_per_cycle}")


    def update_ui_for_session(self):
        if self.current_session_type == self.WORK:
            frame_style = "Normal.TFrame"
            session_label_style = "Work.Session.TLabel"
            timer_label_style = "Work.Timer.TLabel"
            pomo_count_label_style = "Work.PomodoroCount.TLabel"
        elif self.current_session_type == self.SHORT_BREAK:
            frame_style = "Normal.TFrame"
            session_label_style = "ShortBreak.Session.TLabel"
            timer_label_style = "ShortBreak.Timer.TLabel"
            pomo_count_label_style = "ShortBreak.PomodoroCount.TLabel"
        elif self.current_session_type == self.LONG_BREAK:
            frame_style = "LongBreak.TFrame"
            session_label_style = "LongBreak.Session.TLabel"
            timer_label_style = "LongBreak.Timer.TLabel"
            pomo_count_label_style = "LongBreak.PomodoroCount.TLabel"
        else: 
            frame_style = "Normal.TFrame"
            session_label_style = "TLabel" 
            timer_label_style = "TLabel"
            pomo_count_label_style = "TLabel"

        self.timer_controls_frame.config(style=frame_style)
        self.controls_grid_frame.config(style=frame_style) 

        self.session_label.config(style=session_label_style)
        self.timer_label.config(style=timer_label_style)
        self.pomodoro_count_label.config(style=pomo_count_label_style)
        
        self.root.update_idletasks()

    def update_always_on_top(self, event=None):
        is_on_top = self.always_on_top_var.get()
        self.root.attributes('-topmost', is_on_top)
        self.config_manager.set("always_on_top", is_on_top)

    def open_settings(self):
        if self.is_running and not self.paused: self.pause_timer()

        settings_window = tk.Toplevel(self.root)
        settings_window.title("Settings")
        settings_window.configure(bg=self.COLOR_BG) # Direct BG for Toplevel
        settings_window.transient(self.root)
        settings_window.grab_set()
        settings_window.resizable(False, False)

        main_settings_frame = ttk.Frame(settings_window, padding="20") # TFrame style for BG
        main_settings_frame.pack(expand=True, fill=tk.BOTH)

        # Labels in settings window will use default TLabel style (config_bg, config_fg)
        # Entries and Spinboxes will use TEntry and TSpinbox styles

        ttk.Label(main_settings_frame, text="Work Duration (min):").grid(row=0, column=0, sticky=tk.W, pady=3)
        work_var = tk.IntVar(value=self.config_manager.get("work_duration"))
        ttk.Spinbox(main_settings_frame, from_=1, to=120, textvariable=work_var, width=5).grid(row=0, column=1, sticky=tk.W, pady=3)

        ttk.Label(main_settings_frame, text="Short Break (min):").grid(row=1, column=0, sticky=tk.W, pady=3)
        short_break_var = tk.IntVar(value=self.config_manager.get("short_break_duration"))
        ttk.Spinbox(main_settings_frame, from_=1, to=60, textvariable=short_break_var, width=5).grid(row=1, column=1, sticky=tk.W, pady=3)

        ttk.Label(main_settings_frame, text="Long Break (min):").grid(row=2, column=0, sticky=tk.W, pady=3)
        long_break_var = tk.IntVar(value=self.config_manager.get("long_break_duration"))
        ttk.Spinbox(main_settings_frame, from_=1, to=120, textvariable=long_break_var, width=5).grid(row=2, column=1, sticky=tk.W, pady=3)

        ttk.Label(main_settings_frame, text="Pomos per Long Break:").grid(row=3, column=0, sticky=tk.W, pady=3)
        pomos_cycle_var = tk.IntVar(value=self.config_manager.get("pomodoros_per_long_break"))
        ttk.Spinbox(main_settings_frame, from_=1, to=10, textvariable=pomos_cycle_var, width=5).grid(row=3, column=1, sticky=tk.W, pady=3)
        
        ttk.Label(main_settings_frame, text="User Name:").grid(row=4, column=0, sticky=tk.W, pady=3)
        user_name_var = tk.StringVar(value=self.config_manager.get("user_name", "User"))
        ttk.Entry(main_settings_frame, textvariable=user_name_var, width=20).grid(row=4, column=1, sticky=tk.EW, pady=3)

        auto_start_var = tk.BooleanVar(value=self.config_manager.get("auto_start_next_session"))
        ttk.Checkbutton(main_settings_frame, text="Auto-start next session", variable=auto_start_var).grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=3)

        sound_enabled_var = tk.BooleanVar(value=self.config_manager.get("sound_enabled"))
        ttk.Checkbutton(main_settings_frame, text="Enable sound notifications", variable=sound_enabled_var).grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=3)
        
        ttk.Checkbutton(main_settings_frame, text="Always on Top", variable=self.always_on_top_var, command=self.update_always_on_top).grid(row=7, column=0, columnspan=2, sticky=tk.W, pady=3)

        # Sound selection
        sounds_library = self.config_manager.get("notification_sounds", [])
        self.sound_name_to_path_map = {s["name"]: s["path"] for s in sounds_library}
        sound_names = list(self.sound_name_to_path_map.keys())
        if not sound_names: sound_names = ["No sounds available"]


        # Work End Sound Combobox
        ttk.Label(main_settings_frame, text="Work End Sound:").grid(row=8, column=0, sticky=tk.W, pady=3)
        current_work_sound_path = self.config_manager.get("work_end_sound")
        current_work_sound_name = next((name for name, path in self.sound_name_to_path_map.items() if path == current_work_sound_path), "")
        
        self.work_sound_combo_var = tk.StringVar(value=current_work_sound_name)
        work_sound_combobox = ttk.Combobox(main_settings_frame, textvariable=self.work_sound_combo_var, values=sound_names, state="readonly", width=28)
        work_sound_combobox.grid(row=8, column=1, sticky=tk.EW, pady=3)
        # Removed browse button for individual sound, replaced by Add Custom Sound

        # Break End Sound Combobox
        ttk.Label(main_settings_frame, text="Break End Sound:").grid(row=9, column=0, sticky=tk.W, pady=3)
        current_break_sound_path = self.config_manager.get("break_end_sound")
        current_break_sound_name = next((name for name, path in self.sound_name_to_path_map.items() if path == current_break_sound_path), "")

        self.break_sound_combo_var = tk.StringVar(value=current_break_sound_name)
        break_sound_combobox = ttk.Combobox(main_settings_frame, textvariable=self.break_sound_combo_var, values=sound_names, state="readonly", width=28)
        break_sound_combobox.grid(row=9, column=1, sticky=tk.EW, pady=3)
        # Removed browse button for individual sound

        # Add Custom Sound Button
        add_sound_button = ttk.Button(main_settings_frame, text="Add Custom Sound", command=lambda: self._add_custom_sound(settings_window, work_sound_combobox, break_sound_combobox))
        add_sound_button.grid(row=8, column=2, rowspan=2, padx=5, pady=3, sticky="ns")


        # --- Theme Colors Display ---
        theme_labelframe = ttk.LabelFrame(main_settings_frame, text="Theme Colors (Read-only)")
        theme_labelframe.grid(row=10, column=0, columnspan=3, sticky="ew", pady=(15,5), padx=5)

        theme_canvas = tk.Canvas(theme_labelframe, borderwidth=0, background=self.COLOR_BG, height=150) # Set height
        theme_scrollbar = ttk.Scrollbar(theme_labelframe, orient="vertical", command=theme_canvas.yview)
        theme_scrollable_frame = ttk.Frame(theme_canvas)

        theme_scrollable_frame.bind(
            "<Configure>",
            lambda e: theme_canvas.configure(
                scrollregion=theme_canvas.bbox("all")
            )
        )
        theme_canvas.create_window((0, 0), window=theme_scrollable_frame, anchor="nw")
        theme_canvas.configure(yscrollcommand=theme_scrollbar.set)

        theme_canvas.pack(side="left", fill="both", expand=True)
        theme_scrollbar.pack(side="right", fill="y")

        current_theme_colors = self.config_manager.get("theme")
        color_row = 0
        for name, value in current_theme_colors.items():
            ttk.Label(theme_scrollable_frame, text=f"{name}:", anchor="w").grid(row=color_row, column=0, sticky="ew", padx=5, pady=2)

            hex_value_label = ttk.Label(theme_scrollable_frame, text=value, anchor="w")
            hex_value_label.grid(row=color_row, column=1, sticky="ew", padx=5, pady=2)

            # Color preview swatch
            # Ensure the preview label itself has a contrasting foreground to its own background for readability of the hex code
            # Fallback to a default fg color if the theme's main FG is too similar to the swatch color
            preview_fg = self.COLOR_FG
            try:
                # Basic check for contrast, can be more sophisticated
                bg_lum = sum(int(value[i:i+2], 16) for i in (1, 3, 5)) / (255 * 3)
                fg_lum = sum(int(self.COLOR_FG[i:i+2], 16) for i in (1, 3, 5)) / (255 * 3)
                if abs(bg_lum - fg_lum) < 0.3: # Arbitrary threshold
                    preview_fg = "#000000" if fg_lum > 0.5 else "#FFFFFF"
            except Exception: # In case of invalid hex or other errors
                pass


            color_preview = tk.Label(theme_scrollable_frame, text="     ", background=value, width=5, relief="sunken", borderwidth=1)
            color_preview.grid(row=color_row, column=2, padx=5, pady=2, sticky="w")

            # Re-apply hex value label on top of preview swatch for better visibility if needed, or just use a separate label
            # For simplicity, we use the separate hex_value_label already created.

            color_row += 1
        theme_scrollable_frame.columnconfigure(0, weight=1) # Let color name expand
        theme_scrollable_frame.columnconfigure(1, weight=1) # Let hex value expand

        # --- Gemini Assistant Settings ---
        gemini_frame = ttk.LabelFrame(main_settings_frame, text="Gemini Assistant Settings")
        gemini_frame.grid(row=11, column=0, columnspan=3, sticky="ew", pady=(15,5), padx=5)
        gemini_frame.columnconfigure(1, weight=1)

        gemini_enabled_var = tk.BooleanVar(value=self.config_manager.get("gemini_enabled", False))
        ttk.Checkbutton(gemini_frame, text="Enable Gemini Assistant", variable=gemini_enabled_var).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=3)

        ttk.Label(gemini_frame, text="Gemini API Key:").grid(row=1, column=0, sticky=tk.W, pady=3)
        gemini_api_key_var = tk.StringVar(value=self.config_manager.get("gemini_api_key", ""))
        ttk.Entry(gemini_frame, textvariable=gemini_api_key_var, width=30, show="*").grid(row=1, column=1, sticky=tk.EW, pady=3)

        ttk.Label(gemini_frame, text="Gemini Model:").grid(row=2, column=0, sticky=tk.W, pady=3)
        gemini_model_var = tk.StringVar(value=self.config_manager.get("gemini_model", "gemini-pro"))
        gemini_models_available = self.config_manager.get("gemini_models_available", ["gemini-pro"])
        if not gemini_models_available: gemini_models_available = ["gemini-pro"] # Ensure list is not empty
        gemini_model_combobox = ttk.Combobox(gemini_frame, textvariable=gemini_model_var, values=gemini_models_available, state="readonly", width=28)
        gemini_model_combobox.grid(row=2, column=1, sticky=tk.EW, pady=3)

        gemini_tts_enabled_var = tk.BooleanVar(value=self.config_manager.get("gemini_tts_enabled", False))
        ttk.Checkbutton(gemini_frame, text="Enable Text-to-Speech for Gemini responses", variable=gemini_tts_enabled_var).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=3)


        main_settings_frame.columnconfigure(1, weight=1)

        button_frame = ttk.Frame(main_settings_frame) # TFrame style for BG
        button_frame.grid(row=12, column=0, columnspan=3, pady=15) # Adjusted row for Gemini section

        def save_and_close():
            self.config_manager.set("work_duration", work_var.get())
            self.config_manager.set("short_break_duration", short_break_var.get())
            self.config_manager.set("long_break_duration", long_break_var.get())
            self.config_manager.set("pomodoros_per_long_break", pomos_cycle_var.get())
            self.config_manager.set("user_name", user_name_var.get())
            self.config_manager.set("auto_start_next_session", auto_start_var.get())
            self.config_manager.set("sound_enabled", sound_enabled_var.get())
            
            selected_work_sound_name = self.work_sound_combo_var.get()
            selected_work_sound_path = self.sound_name_to_path_map.get(selected_work_sound_name, self.config_manager.get("work_end_sound")) # Fallback to current if name not found
            self.config_manager.set("work_end_sound", selected_work_sound_path)

            selected_break_sound_name = self.break_sound_combo_var.get()
            selected_break_sound_path = self.sound_name_to_path_map.get(selected_break_sound_name, self.config_manager.get("break_end_sound")) # Fallback
            self.config_manager.set("break_end_sound", selected_break_sound_path)

            # Save Gemini settings
            self.config_manager.set("gemini_enabled", gemini_enabled_var.get())
            self.config_manager.set("gemini_api_key", gemini_api_key_var.get())
            self.config_manager.set("gemini_model", gemini_model_var.get())
            self.config_manager.set("gemini_tts_enabled", gemini_tts_enabled_var.get())

            # notification_sounds list is updated by _add_custom_sound directly via config_manager.set
            self.config_manager.save_settings() # Save all settings at once
            # Reload theme colors in case they are part of future settings
            self._load_theme_colors()
            # Re-apply styles and update UI if colors changed
            self._setup_styles() # Re-apply styles with potentially new colors
            self.root.configure(bg=self.COLOR_BG) # Update root background

            self._initialize_gemini_assistant() # Re-initialize Gemini with new settings
            self._initialize_tts_engine() # Re-initialize TTS with new settings

            if not self.is_running: self.reset_current_session() 
            self.update_pomodoro_count_display()
            self.update_always_on_top() 
            self.update_ui_for_session() # This will update styles of dynamic elements
            self.refresh_task_list_and_daily_summary() # Re-color calendar and other elements if needed
            settings_window.destroy()

        ttk.Button(button_frame, text="Save & Close", command=save_and_close).pack(side=tk.LEFT, padx=10) # TButton style
        ttk.Button(button_frame, text="Cancel", command=settings_window.destroy).pack(side=tk.LEFT, padx=10) # TButton style

    def _add_message_to_chat_history(self, message, tag="info"):
        if not hasattr(self, 'gemini_chat_history') or not self.gemini_chat_history.winfo_exists():
            return # Avoid error if called before UI is fully setup or after destroyed
        self.gemini_chat_history.config(state=tk.NORMAL)
        self.gemini_chat_history.insert(tk.END, message + "\n", (tag,))
        self.gemini_chat_history.config(state=tk.DISABLED)
        self.gemini_chat_history.see(tk.END)

    def _initialize_tts_engine(self):
        if self.config_manager.get("gemini_tts_enabled"):
            try:
                self.tts_engine = pyttsx3.init()
                # Optional: Adjust properties like rate or volume if needed
                # self.tts_engine.setProperty('rate', 150)
            except Exception as e:
                self.tts_engine = None
                print(f"Error initializing TTS engine: {e}")
                self._add_message_to_chat_history(f"TTS (Error): Could not initialize text-to-speech engine: {str(e)[:100]}", "error")
        else:
            if self.tts_engine: # If it was previously initialized, try to stop it
                try:
                    self.tts_engine.stop() # Stop any ongoing speech
                except Exception as e:
                    print(f"Error stopping TTS engine during re-initialization: {e}")
            self.tts_engine = None # Ensure it's None if disabled

    def _initialize_gemini_assistant(self):
        if not hasattr(self, 'gemini_send_button') or not self.gemini_send_button.winfo_exists():
             # UI not ready yet, defer or handle (e.g. called from __init__ too early)
            return

        if self.config_manager.get("gemini_enabled"):
            api_key = self.config_manager.get("gemini_api_key")
            model_name = self.config_manager.get("gemini_model")
            if api_key:
                try:
                    self.gemini_assistant = GeminiAssistant(api_key=api_key, model_name=model_name)
                    if not self.gemini_assistant.model:
                        self._add_message_to_chat_history("Gemini (Error): Failed to initialize. Check API key/model in settings.", "error")
                        self.gemini_assistant = None
                        self.gemini_send_button.config(state=tk.DISABLED)
                    else:
                        self._add_message_to_chat_history("Gemini Assistant initialized.", "info")
                        self.gemini_send_button.config(state=tk.NORMAL)
                except Exception as e: # Catch potential errors during GeminiAssistant instantiation
                    self._add_message_to_chat_history(f"Gemini (Error): Exception during init: {e}", "error")
                    self.gemini_assistant = None
                    self.gemini_send_button.config(state=tk.DISABLED)
            else:
                self.gemini_assistant = None
                self._add_message_to_chat_history("Gemini is enabled, but API key is missing in settings.", "info")
                self.gemini_send_button.config(state=tk.DISABLED)
        else:
            self.gemini_assistant = None
            self._add_message_to_chat_history("Gemini Assistant is disabled.", "info")
            if hasattr(self, 'gemini_send_button'): # Ensure button exists
                 self.gemini_send_button.config(state=tk.DISABLED)
    
    def on_send_gemini_message(self, event=None):
        if not hasattr(self, 'gemini_chat_input') or not self.gemini_chat_input.winfo_exists(): return

        user_text = self.gemini_chat_input.get().strip()
        if not user_text:
            return

        self._add_message_to_chat_history(f"You: {user_text}", "user")
        self.gemini_chat_input.delete(0, tk.END)

        self.gemini_send_button.config(state=tk.DISABLED) # Disable during processing
        self.root.update_idletasks() # Ensure UI updates

        if self.gemini_assistant and self.config_manager.get("gemini_enabled"):
            response_text = self.gemini_assistant.send_message(user_text)

            # TTS Playback
            if self.tts_engine and self.config_manager.get("gemini_tts_enabled") and not response_text.startswith("Error:"):
                try:
                    self.tts_engine.say(response_text)
                    self.tts_engine.runAndWait()
                except Exception as e:
                    print(f"Error during TTS playback: {e}")
                    self._add_message_to_chat_history(f"TTS (Error): Could not play speech: {str(e)[:100]}", "error")

            tag_to_use = "gemini"
            if response_text.startswith("Error:"):
                tag_to_use = "error"
            self._add_message_to_chat_history(f"Gemini: {response_text}", tag_to_use)
        else:
            self._add_message_to_chat_history("Gemini is disabled or not configured. Check settings.", "info")

        # Re-enable send button if Gemini is still configured, otherwise keep it disabled
        if self.gemini_assistant and self.config_manager.get("gemini_enabled") and self.gemini_assistant.model:
            self.gemini_send_button.config(state=tk.NORMAL)
        else:
            self.gemini_send_button.config(state=tk.DISABLED)

    def _add_custom_sound(self, parent_window, work_combo, break_combo):
        sounds_dir = resource_path("sounds")
        try:
            os.makedirs(sounds_dir, exist_ok=True)
        except OSError as e:
            messagebox.showerror("Error", f"Could not create sounds directory: {e}", parent=parent_window)
            return

        filepath = filedialog.askopenfilename(
            parent=parent_window,
            title="Select Custom Sound File",
            initialdir=sounds_dir, # Start in sounds dir or user's last known
            filetypes=(("Audio Files", "*.wav *.mp3"), ("All files", "*.*"))
        )
        if not filepath: return

        sound_name = simpledialog.askstring("Sound Name", "Enter a display name for this sound:", parent=parent_window)
        if not sound_name: return

        # Sanitize sound_name slightly for filename, or use a timestamp
        base_filename, file_extension = os.path.splitext(os.path.basename(filepath))
        # Using timestamp to ensure uniqueness for copied file
        timestamp = str(int(time.time()))
        # Replace spaces and special characters in sound_name for filename, or just use a generic prefix
        safe_sound_name_part = "".join(c if c.isalnum() else "_" for c in sound_name[:20]) # limit length
        new_filename = f"custom_{safe_sound_name_part}_{timestamp}{file_extension}"
        destination_path_relative = os.path.join("sounds", new_filename).replace(os.sep, "/") # Relative path for config
        destination_path_absolute = resource_path(destination_path_relative)

        try:
            shutil.copy(filepath, destination_path_absolute)
        except Exception as e:
            messagebox.showerror("File Copy Error", f"Could not copy sound file: {e}", parent=parent_window)
            return

        sounds_library = self.config_manager.get("notification_sounds", [])
        # Check if name or path already exists to avoid duplicates
        if any(s['name'] == sound_name for s in sounds_library):
            messagebox.showwarning("Duplicate Name", f"A sound with the name '{sound_name}' already exists.", parent=parent_window)
            # Potentially remove the copied file if name is duplicate and we don't want to overwrite
            try: os.remove(destination_path_absolute)
            except OSError: pass # Ignore if removal fails
            return
        if any(s['path'] == destination_path_relative for s in sounds_library):
            # This should be rare due to timestamp, but good to check
            messagebox.showwarning("Duplicate Path", "This sound file path somehow already exists in the library.", parent=parent_window)
            return

        sounds_library.append({"name": sound_name, "path": destination_path_relative})
        self.config_manager.set("notification_sounds", sounds_library) # Save updated list

        # Update internal map and combobox values
        self.sound_name_to_path_map[sound_name] = destination_path_relative
        new_sound_names = list(self.sound_name_to_path_map.keys())
        work_combo['values'] = new_sound_names
        break_combo['values'] = new_sound_names

        # Optionally set the new sound as selected for one of the comboboxes
        # work_combo.set(sound_name)

        messagebox.showinfo("Sound Added", f"Sound '{sound_name}' added. It's now available in the dropdowns.", parent=parent_window)


    def _browse_sound_file(self, string_var_to_update, parent_window): # Kept for now, but might be deprecated by comboboxes
        initial_dir_sounds = resource_path("sounds") 
        if not os.path.isdir(initial_dir_sounds):
            initial_dir_sounds = resource_path("") 

        filepath = filedialog.askopenfilename(
            parent=parent_window, 
            title="Select Sound File (Legacy)",
            initialdir=initial_dir_sounds,
            filetypes=(("Audio Files", "*.wav *.mp3"), ("All files", "*.*"))
        )
        if filepath:
            normalized_filepath = os.path.normpath(filepath)
            app_root_normalized = os.path.normpath(resource_path(""))
            try:
                if normalized_filepath.startswith(app_root_normalized):
                    relative_path = os.path.relpath(normalized_filepath, app_root_normalized)
                    string_var_to_update.set(relative_path.replace(os.sep, "/"))
                else: 
                    string_var_to_update.set(normalized_filepath.replace(os.sep, "/"))
            except ValueError:
                 string_var_to_update.set(normalized_filepath.replace(os.sep, "/"))


    def _bind_shortcuts(self): 
        self.root.bind('<Control-s>', self.start_timer)
        self.root.bind('<Control-S>', self.start_timer) 
        self.root.bind('<Control-p>', self.pause_timer)
        self.root.bind('<Control-P>', self.pause_timer)
        self.root.bind('<Control-r>', self.reset_current_session)
        self.root.bind('<Control-R>', self.reset_current_session)
        self.root.bind('<Control-k>', self.skip_break)
        self.root.bind('<Control-K>', self.skip_break)

    def on_task_drag_start(self, event):
        item_iid = self.task_tree.identify_row(event.y)
        if item_iid:
            # Check if the click is on the actual item, not header or empty space
            if self.task_tree.exists(item_iid):
                tags = self.task_tree.item(item_iid, "tags")
                if tags:
                    self.dragging_task_id = tags[0]
                    # self.task_tree.config(cursor="hand2") # Optional: change cursor
                else:
                    self.dragging_task_id = None # Clicked on something without a task ID tag
            else:
                self.dragging_task_id = None # Clicked outside of an actual item
        else:
            self.dragging_task_id = None

    def on_task_drag_motion(self, event):
        if self.dragging_task_id:
            self.task_tree.config(cursor="hand2") # Or "grabbing" if available/preferred
            # Visual feedback (like a line or ghost item) could be added here
            # For now, just cursor change.
            pass

    def on_task_drag_release(self, event):
        if not self.dragging_task_id:
            self.task_tree.config(cursor="") # Reset cursor
            return

        target_iid = self.task_tree.identify_row(event.y)

        if target_iid and self.task_tree.exists(target_iid) and target_iid != self.dragging_task_id:
            # Get the ID of the item being dragged (from its tags)
            dragged_item_tree_id = None
            for item_in_tree in self.task_tree.get_children(''):
                if self.task_tree.item(item_in_tree, "tags") and self.task_tree.item(item_in_tree, "tags")[0] == self.dragging_task_id:
                    dragged_item_tree_id = item_in_tree
                    break

            if dragged_item_tree_id:
                try:
                    target_index = self.task_tree.index(target_iid)
                    self.task_tree.move(dragged_item_tree_id, '', target_index)
                except tk.TclError as e:
                    print(f"Error moving task: {e}") # Should not happen if target_iid is valid
            else:
                print(f"Could not find tree item for dragging_task_id: {self.dragging_task_id}")

        elif not target_iid: # Dropped in empty space (likely at the end)
             # Get the ID of the item being dragged (from its tags)
            dragged_item_tree_id = None
            for item_in_tree in self.task_tree.get_children(''):
                if self.task_tree.item(item_in_tree, "tags") and self.task_tree.item(item_in_tree, "tags")[0] == self.dragging_task_id:
                    dragged_item_tree_id = item_in_tree
                    break
            if dragged_item_tree_id:
                self.task_tree.move(dragged_item_tree_id, '', tk.END)

        self.dragging_task_id = None
        self.task_tree.config(cursor="") # Reset cursor


    def on_close(self):
        self.save_task_notes_auto()
        if self.is_running and not self.paused:
             if not messagebox.askyesno("Timer Running", "Timer is running. Quit anyway?", parent=self.root): return
        if self.timer_id: self.root.after_cancel(self.timer_id)
        self.config_manager.save_settings()
        self.config_manager.save_session_log(self.session_log)
        self.root.destroy()

def main():
    root = tk.Tk()
    root.minsize(850, 650) 
    # Set application icon for the main window (works on Windows, some Linux WMs)
    # This requires the icon to be accessible at runtime.
    # For a bundled app, resource_path is essential here.
    # In app.py -> main()
    try:
        # Attempt .ico first (might be preferred by root.iconbitmap on some systems or if it's a high-quality multi-res .ico)
        icon_path_ico = resource_path("Misc/HyperPomo.ico") 
        if os.path.exists(icon_path_ico):
            root.iconbitmap(icon_path_ico) 
        else: # Fallback to PNG if .ico is not found or if you explicitly want to try PNG next
            icon_path_png = resource_path("Misc/HyperPomo.png") 
            if os.path.exists(icon_path_png):
                img = tk.PhotoImage(file=icon_path_png)
                root.tk.call('wm', 'iconphoto', root._w, img)
            else:
                print(f"Window icon (PNG) not found: {icon_path_png}")
    except Exception as e:
        print(f"Could not set window icon: {e}")

    app = PomodoroApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()

if __name__ == "__main__":
    main()