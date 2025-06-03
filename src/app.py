# HyperPomo/src/app.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog, scrolledtext, PanedWindow
import time
import os
import datetime
import sys
import speech_recognition as sr
import vlc
import yt_dlp
import threading
import asyncio
import pyttsx3

from .config_manager import ConfigManager
from .task_manager import TaskManager, Task
from .gemini_client import GeminiClient


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
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    return os.path.join(base_path, relative_path)

class PomodoroApp:
    WORK = "Work"
    SHORT_BREAK = "Short Break"
    LONG_BREAK = "Long Break"

    def __init__(self, root):
        self.root = root
        self.root.title("HyperPomo") 

        self.config_manager = ConfigManager(data_dir=resource_path("data"))

        self._load_colors_from_config()
        self.root.configure(bg=self.COLOR_BG)

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

        self.dragging_task_id = None
        self.drag_start_y = 0

        self.gemini_client = GeminiClient(
            api_key=self.config_manager.get("gemini_api_key"),
            model_name=self.config_manager.get("gemini_model")
        )

        self.tts_engine = None
        self.tts_available_voices = []
        try:
            self.tts_engine = pyttsx3.init()
            if self.tts_engine:
                self.tts_engine.setProperty('rate', self.config_manager.get("tts_rate"))
                stored_voice_id = self.config_manager.get("tts_voice_id")
                if stored_voice_id:
                    try: self.tts_engine.setProperty('voice', stored_voice_id)
                    except Exception as e: print(f"Error setting initial TTS voice: {e}")
            else:
                print("Warning: pyttsx3.init() returned None. TTS will be disabled.")
        except Exception as e:
            print(f"Error initializing pyttsx3 engine: {e}. TTS will be disabled.")
            self.tts_engine = None

        self.vlc_instance = None
        self.vlc_player = None
        self.youtube_playlist = []
        self.current_youtube_track_index = -1
        self.is_youtube_playing = False
        self.current_media = None
        self.youtube_event_manager = None

        try:
            self.vlc_instance = vlc.Instance("--no-xlib")
            self.vlc_player = self.vlc_instance.media_player_new()
            if self.vlc_player:
                 self.youtube_event_manager = self.vlc_player.event_manager()
                 if self.youtube_event_manager:
                    self.youtube_event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self._youtube_on_end_reached_event_handler)
                 else: print("Warning: Could not get VLC event manager.")
            else: print("Warning: Could not create VLC media player.")
        except Exception as e:
            self.vlc_instance = None
            self.vlc_player = None
            print(f"Error initializing VLC: {e}. VLC features will be disabled.")

        self.ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': False,
            'extract_flat': 'in_playlist',
            'quiet': True,
            'default_search': 'ytsearch',
            'source_address': '0.0.0.0',
            'nocheckcertificate': True
        }

        self._apply_initial_settings()
        self._setup_styles()
        self._setup_ui() 
        self.update_timer_display()
        self.refresh_task_list_and_daily_summary() 
        self.update_always_on_top()
        self._bind_shortcuts()
        self.update_current_datetime_display()

    def _load_colors_from_config(self):
        self.COLOR_BG = self.config_manager.get("ui_color_bg")
        self.COLOR_FG = self.config_manager.get("ui_color_fg")
        self.COLOR_ACCENT = self.config_manager.get("ui_color_accent")
        self.COLOR_WORK = self.config_manager.get("ui_color_work")
        self.COLOR_SHORT_BREAK = self.config_manager.get("ui_color_short_break")
        self.COLOR_LONG_BREAK_BG = self.config_manager.get("ui_color_long_break_bg")
        self.COLOR_LONG_BREAK_FG = self.config_manager.get("ui_color_long_break_fg")
        self.COLOR_BUTTON = self.config_manager.get("ui_color_button")
        self.COLOR_BUTTON_HOVER = self.config_manager.get("ui_color_button_hover")
        self.COLOR_BUTTON_TEXT = self.config_manager.get("ui_color_button_text")
        self.COLOR_DISABLED_BUTTON_TEXT = self.config_manager.get("ui_color_disabled_button_text")
        self.COLOR_ENTRY_BG = self.config_manager.get("ui_color_entry_bg")
        self.COLOR_TREEVIEW_BG = self.config_manager.get("ui_color_treeview_bg")
        self.COLOR_TREEVIEW_FG = self.config_manager.get("ui_color_treeview_fg")
        self.COLOR_TREEVIEW_FIELD_BG = self.config_manager.get("ui_color_treeview_field_bg")
        self.COLOR_TREEVIEW_HEADING_BG = self.config_manager.get("ui_color_treeview_heading_bg")
        self.COLOR_CURRENT_TASK_BG = self.config_manager.get("ui_color_current_task_bg")
        self.COLOR_CALENDAR_HEADER = self.config_manager.get("ui_color_calendar_header")
        self.COLOR_CALENDAR_WEEKEND = self.config_manager.get("ui_color_calendar_weekend")

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
        style.map("Treeview", background=[('selected', self.COLOR_ACCENT)], foreground=[('selected', self.COLOR_BG)])
        style.configure("Treeview.Heading", background=self.COLOR_TREEVIEW_HEADING_BG, foreground=self.COLOR_FG, font=('Segoe UI', 9, 'bold'), padding=4, relief=tk.FLAT)
        style.configure("TLabelframe", background=self.COLOR_BG, bordercolor=self.COLOR_ACCENT, padding=8, relief=tk.GROOVE)
        style.configure("TLabelframe.Label", background=self.COLOR_BG, foreground=self.COLOR_ACCENT, font=("Segoe UI", 10, "bold"))
        style.configure("TEntry", fieldbackground=self.COLOR_ENTRY_BG, foreground=self.COLOR_FG, insertcolor=self.COLOR_FG, font=("Segoe UI", 10), borderwidth=1, relief=tk.FLAT)
        style.configure("TSpinbox", fieldbackground=self.COLOR_ENTRY_BG, foreground=self.COLOR_FG, insertcolor=self.COLOR_FG, arrowcolor=self.COLOR_FG, background=self.COLOR_BUTTON, font=("Segoe UI", 10), relief=tk.FLAT)
        style.configure("TSash", background=self.COLOR_ACCENT, sashthickness=6)


    def _setup_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.main_paned_window = PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=5, bg=self.COLOR_ACCENT)
        self.main_paned_window.pack(fill=tk.BOTH, expand=True)

        left_main_frame = ttk.Frame(self.main_paned_window, padding=0)
        # Add panes first
        self.main_paned_window.add(left_main_frame, minsize=450)

        left_main_frame.columnconfigure(0, weight=1)
        left_main_frame.rowconfigure(0, weight=1)

        left_vertical_paned_window = PanedWindow(left_main_frame, orient=tk.VERTICAL, sashrelief=tk.RAISED, sashwidth=5, bg=self.COLOR_ACCENT)
        left_vertical_paned_window.grid(row=0, column=0, sticky="nsew")

        top_left_content_frame = ttk.Frame(left_vertical_paned_window, padding=5)
        top_left_content_frame.columnconfigure(0, weight=1)
        top_left_content_frame.rowconfigure(1, weight=1)
        left_vertical_paned_window.add(top_left_content_frame, minsize=300, weight=1)

        self.timer_controls_frame = ttk.Frame(top_left_content_frame)
        self.timer_controls_frame.grid(row=0, column=0, sticky="ew", pady=(0,5))
        self.timer_controls_frame.columnconfigure(0, weight=1)

        self.session_label = ttk.Label(self.timer_controls_frame, text=self.current_session_type, anchor="center")
        self.session_label.pack(pady=(0,2), fill=tk.X)
        self.timer_label = ttk.Label(self.timer_controls_frame, text="25:00", anchor="center")
        self.timer_label.pack(pady=(0,2), fill=tk.X)
        self.pomodoro_count_label = ttk.Label(self.timer_controls_frame, text=f"Cycle: 0 / {self.config_manager.get('pomodoros_per_long_break')}", anchor="center")
        self.pomodoro_count_label.pack(pady=(0,2), fill=tk.X)
        
        self.current_task_display_label = ttk.Label(self.timer_controls_frame, text="Current Task: None", style="CurrentTask.TLabel", anchor="center", wraplength=400)
        self.current_task_display_label.pack(pady=(2,2), fill=tk.X, padx=10)

        self.controls_grid_frame = ttk.Frame(self.timer_controls_frame) 
        self.controls_grid_frame.pack(pady=2)
        self.start_button = ttk.Button(self.controls_grid_frame, text="Start", command=self.start_timer, width=10)
        self.start_button.grid(row=0, column=0, padx=2)
        self.pause_button = ttk.Button(self.controls_grid_frame, text="Pause", command=self.pause_timer, width=10, state=tk.DISABLED)
        self.pause_button.grid(row=0, column=1, padx=2)
        self.reset_button = ttk.Button(self.controls_grid_frame, text="Reset", command=self.reset_current_session, width=10)
        self.reset_button.grid(row=0, column=2, padx=2)
        self.skip_button = ttk.Button(self.controls_grid_frame, text="Skip Break", command=self.skip_break, width=10, state=tk.DISABLED)
        self.skip_button.grid(row=0, column=3, padx=2)

        task_section_frame = ttk.LabelFrame(top_left_content_frame, text="Task Management")
        task_section_frame.grid(row=1, column=0, sticky="nsew", pady=(5,0))
        task_section_frame.columnconfigure(0, weight=1) 
        task_section_frame.rowconfigure(1, weight=1) 

        task_input_frame = ttk.Frame(task_section_frame)
        task_input_frame.grid(row=0, column=0, sticky="ew", pady=2, padx=5)
        task_input_frame.columnconfigure(0, weight=1)
        self.task_entry = ttk.Entry(task_input_frame, width=25)
        self.task_entry.grid(row=0, column=0, sticky="ew", padx=(0,2))
        self.task_entry.bind("<Return>", lambda event: self.add_task_gui())
        self.task_pomodoro_est_label = ttk.Label(task_input_frame, text="Est:")
        self.task_pomodoro_est_label.grid(row=0, column=1, padx=(2,0))
        self.task_pomodoro_est_spinbox = ttk.Spinbox(task_input_frame, from_=1, to=20, width=3, justify=tk.CENTER)
        self.task_pomodoro_est_spinbox.set("1")
        self.task_pomodoro_est_spinbox.grid(row=0, column=2, padx=(0,2))
        self.add_task_button = ttk.Button(task_input_frame, text="Add", command=self.add_task_gui)
        self.add_task_button.grid(row=0, column=3, padx=(2,0))

        task_display_notebook = ttk.Notebook(task_section_frame)
        task_display_notebook.grid(row=1, column=0, sticky="nsew", pady=2, padx=5)

        tasks_tab_frame = ttk.Frame(task_display_notebook)
        tasks_tab_frame.columnconfigure(0, weight=1)
        tasks_tab_frame.rowconfigure(0, weight=1)
        task_display_notebook.add(tasks_tab_frame, text="Scheduled Tasks")

        self.task_tree = ttk.Treeview(tasks_tab_frame, columns=("text", "est", "done_p"), show="headings", selectmode="browse")
        self.task_tree.heading("text", text="Task (for selected date)")
        self.task_tree.heading("est", text="Est.")
        self.task_tree.heading("done_p", text="Done")
        self.task_tree.column("text", width=200, stretch=tk.YES)
        self.task_tree.column("est", width=35, anchor="center")
        self.task_tree.column("done_p", width=40, anchor="center")
        self.task_tree.grid(row=0, column=0, sticky="nsew")
        self.task_tree.bind("<<TreeviewSelect>>", self.on_task_select)
        self.task_tree.bind("<ButtonPress-1>", self._on_task_drag_start)
        self.task_tree.bind("<B1-Motion>", self._on_task_drag_motion)
        self.task_tree.bind("<ButtonRelease-1>", self._on_task_drag_release)
        
        task_tree_scrollbar = ttk.Scrollbar(tasks_tab_frame, orient="vertical", command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=task_tree_scrollbar.set)
        task_tree_scrollbar.grid(row=0, column=1, sticky="ns")

        notes_tab_frame = ttk.Frame(task_display_notebook)
        notes_tab_frame.columnconfigure(0, weight=1)
        notes_tab_frame.rowconfigure(0, weight=1)
        task_display_notebook.add(notes_tab_frame, text="Notes")
        self.task_notes_text = scrolledtext.ScrolledText(notes_tab_frame, wrap=tk.WORD, height=4, width=30,
                                                         bg=self.COLOR_ENTRY_BG, fg=self.COLOR_FG, insertbackground=self.COLOR_FG,
                                                         font=("Segoe UI", 9), relief=tk.FLAT, borderwidth=2)
        self.task_notes_text.pack(expand=True, fill=tk.BOTH, padx=2, pady=2)
        self.task_notes_text.bind("<FocusOut>", self.save_task_notes_auto)
        self.task_notes_text.config(state=tk.DISABLED)

        task_button_frame = ttk.Frame(task_section_frame)
        task_button_frame.grid(row=2, column=0, sticky="ew", pady=2, padx=5)
        self.select_work_task_button = ttk.Button(task_button_frame, text="Work on", command=self.set_current_work_task, state=tk.DISABLED, width=8)
        self.select_work_task_button.pack(side=tk.LEFT, padx=1)
        self.mark_done_button = ttk.Button(task_button_frame, text="Done", command=self.toggle_task_done_gui, state=tk.DISABLED, width=6)
        self.mark_done_button.pack(side=tk.LEFT, padx=1)
        self.edit_task_button = ttk.Button(task_button_frame, text="Edit", command=self.edit_task_gui, state=tk.DISABLED, width=6)
        self.edit_task_button.pack(side=tk.LEFT, padx=1)
        self.delete_task_button = ttk.Button(task_button_frame, text="Delete", command=self.delete_task_gui, state=tk.DISABLED, width=6)
        self.delete_task_button.pack(side=tk.LEFT, padx=1)
        self.schedule_task_button = ttk.Button(task_button_frame, text="Schedule", command=self.open_schedule_dialog_for_selected_task, state=tk.DISABLED, width=8)
        self.schedule_task_button.pack(side=tk.LEFT, padx=1)

        bottom_left_content_frame = ttk.Frame(left_vertical_paned_window, padding=5)
        bottom_left_content_frame.columnconfigure(0, weight=1)
        bottom_left_content_frame.rowconfigure(1, weight=1)
        left_vertical_paned_window.add(bottom_left_content_frame, minsize=250, weight=1)

        self.datetime_label = ttk.Label(bottom_left_content_frame, text="", style="DateTime.TLabel", anchor="e")
        self.datetime_label.grid(row=0, column=0, sticky="ew", pady=(0,2), padx=5)

        calendar_outer_frame = ttk.LabelFrame(bottom_left_content_frame, text="Calendar")
        calendar_outer_frame.grid(row=1, column=0, sticky="new", pady=2, padx=5)
        calendar_outer_frame.columnconfigure(0, weight=1)

        if TKCALENDAR_AVAILABLE:
            self.cal = Calendar(calendar_outer_frame, selectmode='day', date_pattern='yyyy-mm-dd',
                                year=self.selected_calendar_date.year, month=self.selected_calendar_date.month, day=self.selected_calendar_date.day,
                                background=self.COLOR_CALENDAR_HEADER, foreground='white',
                                headersbackground=self.COLOR_CALENDAR_HEADER, headersforeground='white',
                                bordercolor=self.COLOR_ACCENT, weekendbackground=self.COLOR_BG, weekendforeground=self.COLOR_CALENDAR_WEEKEND,
                                othermonthbackground=self.COLOR_ENTRY_BG, othermonthwebackground=self.COLOR_ENTRY_BG,
                                othermonthforeground='gray60', othermonthweforeground='gray50',
                                normalbackground=self.COLOR_TREEVIEW_BG, normalforeground='white',
                                selectedbackground=self.COLOR_ACCENT, selectedforeground='black',
                                font=("Segoe UI", 9), firstweekday='monday')
            self.cal.pack(fill="x", expand=True, padx=2, pady=2)
            self.cal.bind("<<CalendarSelected>>", self.on_calendar_date_selected)
        else:
            ttk.Label(calendar_outer_frame, text="Calendar feature disabled.", foreground="orange").pack(padx=5, pady=5)

        self.daily_summary_labelframe = ttk.LabelFrame(bottom_left_content_frame, text=f"Summary for {self.selected_calendar_date.strftime('%Y-%m-%d')}")
        self.daily_summary_labelframe.grid(row=2, column=0, sticky="nsew", pady=2, padx=5)
        self.daily_summary_labelframe.columnconfigure(0, weight=1)
        self.daily_summary_labelframe.rowconfigure(0, weight=1)
        bottom_left_content_frame.rowconfigure(2, weight=1)

        self.daily_summary_text = scrolledtext.ScrolledText(self.daily_summary_labelframe, wrap=tk.WORD, height=6,
                                                            bg=self.COLOR_ENTRY_BG, fg=self.COLOR_FG,
                                                            font=("Segoe UI", 9), relief=tk.FLAT, borderwidth=1)
        self.daily_summary_text.pack(expand=True, fill=tk.BOTH, padx=2, pady=2)
        self.daily_summary_text.config(state=tk.DISABLED)

        bottom_controls_frame = ttk.Frame(bottom_left_content_frame)
        bottom_controls_frame.grid(row=3, column=0, sticky="ew", pady=(5,0), padx=5)
        bottom_controls_frame.columnconfigure(1, weight=1)

        self.reset_cycle_button = ttk.Button(bottom_controls_frame, text="Reset Cycle", command=self.reset_pomodoro_cycle_count, width=12)
        self.reset_cycle_button.grid(row=0, column=0, sticky="w", padx=(0,5))
        
        settings_button = ttk.Button(bottom_controls_frame, text="⚙️ Settings", command=self.open_settings, width=12)
        settings_button.grid(row=0, column=2, sticky="e")
        
        self.gemini_chat_frame = ttk.Frame(self.main_paned_window, padding=10)
        self.main_paned_window.add(self.gemini_chat_frame, minsize=350)

        # Configure panes using their index (0 for the first, 1 for the second)
        # This assumes left_main_frame was added as index 0, and gemini_chat_frame as index 1
        try:
            self.main_paned_window.paneconfig(0, weight=2) # For left_main_frame
            self.main_paned_window.paneconfig(1, weight=1) # For gemini_chat_frame
        except tk.TclError as e:
            print(f"Error configuring PanedWindow panes: {e}. This might occur if panes are not added as expected.")

        self.gemini_chat_frame.columnconfigure(0, weight=1)
        self.gemini_chat_frame.rowconfigure(0, weight=1)
        self.gemini_chat_frame.rowconfigure(1, weight=0)
        self.gemini_chat_frame.rowconfigure(2, weight=0)

        self.gemini_chat_history_text = scrolledtext.ScrolledText(
            self.gemini_chat_frame, wrap=tk.WORD, height=10,
            bg=self.COLOR_ENTRY_BG, fg=self.COLOR_FG,
            font=("Segoe UI", 9), relief=tk.FLAT, borderwidth=1
        )
        self.gemini_chat_history_text.grid(row=0, column=0, columnspan=3, sticky="nsew", pady=(0,5))
        self.gemini_chat_history_text.config(state=tk.DISABLED)

        gemini_input_frame = ttk.Frame(self.gemini_chat_frame)
        gemini_input_frame.grid(row=1, column=0, columnspan=3, sticky="ew")
        gemini_input_frame.columnconfigure(0, weight=1)

        self.gemini_chat_input_entry = ttk.Entry(gemini_input_frame, font=("Segoe UI", 10))
        self.gemini_chat_input_entry.grid(row=0, column=0, sticky="ew", padx=(0,5))
        self.gemini_chat_input_entry.bind("<Return>", self._send_gemini_message)

        self.gemini_record_voice_button = ttk.Button(gemini_input_frame, text="🎤", command=self._start_stt_thread, width=3)
        self.gemini_record_voice_button.grid(row=0, column=1, sticky="e", padx=(0,5))

        self.gemini_send_message_button = ttk.Button(gemini_input_frame, text="Send", command=self._send_gemini_message, width=8)
        self.gemini_send_message_button.grid(row=0, column=2, sticky="e")

        self._update_gemini_chat_initial_state()

        yt_player_frame = ttk.LabelFrame(self.gemini_chat_frame, text="YouTube Music Player", padding=10)
        yt_player_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10,0))
        yt_player_frame.columnconfigure(1, weight=1)

        ttk.Label(yt_player_frame, text="Playlist URL:").grid(row=0, column=0, sticky="w", pady=(0,5))
        self.youtube_playlist_url_entry = ttk.Entry(yt_player_frame, width=30)
        self.youtube_playlist_url_entry.grid(row=0, column=1, sticky="ew", padx=(5,5), pady=(0,5))
        self.youtube_load_playlist_button = ttk.Button(yt_player_frame, text="Load", width=8, command=self._youtube_load_playlist)
        self.youtube_load_playlist_button.grid(row=0, column=2, sticky="e", pady=(0,5))

        now_playing_frame = ttk.Frame(yt_player_frame)
        now_playing_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(5,5))
        now_playing_frame.columnconfigure(1, weight=1)
        ttk.Label(now_playing_frame, text="Now Playing:").pack(side=tk.LEFT)
        self.youtube_now_playing_label = ttk.Label(now_playing_frame, text="None", anchor=tk.W, style="Accent.TLabel")
        self.youtube_now_playing_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        yt_controls_frame = ttk.Frame(yt_player_frame)
        yt_controls_frame.grid(row=2, column=0, columnspan=3, sticky="ew")

        self.youtube_prev_button = ttk.Button(yt_controls_frame, text="⏮ Prev", command=self._youtube_prev_track, width=8)
        self.youtube_prev_button.pack(side=tk.LEFT, padx=2)
        self.youtube_play_pause_button = ttk.Button(yt_controls_frame, text="▶ Play", command=self._youtube_play_pause, width=8)
        self.youtube_play_pause_button.pack(side=tk.LEFT, padx=2)
        self.youtube_next_button = ttk.Button(yt_controls_frame, text="Next ⏭", command=self._youtube_next_track, width=8)
        self.youtube_next_button.pack(side=tk.LEFT, padx=2)
        self.youtube_stop_button = ttk.Button(yt_controls_frame, text="⏹ Stop", command=self._youtube_stop, width=8)
        self.youtube_stop_button.pack(side=tk.LEFT, padx=2)

        if not self.vlc_player:
            self._disable_youtube_controls_during_load(vlc_unavailable=True)
            self.youtube_now_playing_label.config(text="VLC not available or failed to init.")
        else:
            self._restore_youtube_controls_state()

        self.update_ui_for_session()

    # --- YouTube Music Player Methods ---
    def _youtube_load_playlist(self):
        playlist_url = self.youtube_playlist_url_entry.get()
        if not playlist_url:
            messagebox.showwarning("Input Error", "Please enter a YouTube Playlist URL.", parent=self.root)
            return

        self._disable_youtube_controls_during_load()
        self.youtube_now_playing_label.config(text="Loading playlist...")
        self.youtube_playlist = []
        self.current_youtube_track_index = -1
        if self.vlc_player and (self.vlc_player.is_playing() or self.vlc_player.get_state() == vlc.State.Paused):
            self.vlc_player.stop()
        self.is_youtube_playing = False
        self.youtube_play_pause_button.config(text="▶ Play")

        threading.Thread(target=self._fetch_playlist_thread_target, args=(playlist_url,), daemon=True).start()

    def _fetch_playlist_thread_target(self, url):
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                playlist_info = ydl.extract_info(url, download=False)

            temp_playlist = []
            if 'entries' in playlist_info:
                for entry in playlist_info.get('entries', []):
                    if entry:
                        video_url = entry.get('webpage_url') or entry.get('url')
                        title = entry.get('title', 'Unknown Title')
                        if video_url and title:
                             temp_playlist.append({'title': title, 'page_url': video_url, 'audio_url': None})

            self.root.after(0, lambda: self._handle_playlist_loaded(temp_playlist))
        except Exception as e:
            self.root.after(0, lambda: self._handle_playlist_load_error(e))

    def _handle_playlist_loaded(self, playlist_data):
        self._restore_youtube_controls_state()
        if not playlist_data:
            self.youtube_now_playing_label.config(text="No tracks found or error loading playlist.")
            return

        self.youtube_playlist = playlist_data
        self.youtube_now_playing_label.config(text=f"Loaded {len(self.youtube_playlist)} tracks. Select or press Play.")
        if self.youtube_playlist:
             self.current_youtube_track_index = 0
             self.youtube_now_playing_label.config(text=f"{self.youtube_playlist[0]['title'][:50]}...")
        else:
            self.current_youtube_track_index = -1


    def _handle_playlist_load_error(self, error):
        self._restore_youtube_controls_state()
        self.youtube_now_playing_label.config(text="Error loading playlist.")
        messagebox.showerror("Playlist Load Error", f"Failed to load playlist: {error}", parent=self.root)

    def _youtube_prepare_track(self, track_index, autoplay=False):
        if not self.vlc_player or not (0 <= track_index < len(self.youtube_playlist)):
            self.youtube_now_playing_label.config(text="Track unavailable or VLC error.")
            self._restore_youtube_controls_state()
            return

        self.current_youtube_track_index = track_index
        track = self.youtube_playlist[track_index]

        current_vlc_state = self.vlc_player.get_state()
        if current_vlc_state == vlc.State.Playing or current_vlc_state == vlc.State.Paused:
             self.vlc_player.stop()
        self.is_youtube_playing = False
        self.youtube_play_pause_button.config(text="▶ Play")

        self.youtube_now_playing_label.config(text=f"Loading: {track['title'][:40]}...")
        self._disable_youtube_controls_during_load()

        if track.get('audio_url'):
            self._handle_audio_url_fetched(track_index, track['audio_url'], track['title'], autoplay)
        else:
            threading.Thread(target=self._fetch_audio_url_thread_target, args=(track['page_url'], track_index, autoplay), daemon=True).start()

    def _fetch_audio_url_thread_target(self, page_url, track_idx_on_call, autoplay_on_call):
        single_ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'source_address': '0.0.0.0',
            'skip_download': True,
            'nocheckcertificate': True,
        }
        title_for_error = "Track"
        if 0 <= track_idx_on_call < len(self.youtube_playlist):
            title_for_error = self.youtube_playlist[track_idx_on_call]['title']

        try:
            with yt_dlp.YoutubeDL(single_ydl_opts) as ydl:
                info = ydl.extract_info(page_url, download=False)
            audio_url = info.get('url') if isinstance(info, dict) else None
            if not audio_url and isinstance(info, dict) and 'entries' in info and info['entries']:
                first_entry = info['entries'][0]
                audio_url = first_entry.get('url') if isinstance(first_entry, dict) else None
                title_for_error = first_entry.get('title', title_for_error) if isinstance(first_entry, dict) else title_for_error

            actual_title = info.get('title', title_for_error) if isinstance(info, dict) else title_for_error
            self.root.after(0, lambda: self._handle_audio_url_fetched(track_idx_on_call, audio_url, actual_title, autoplay_on_call))
        except Exception as e:
            print(f"Error fetching audio URL for {title_for_error}: {e}")
            self.root.after(0, lambda: self.youtube_now_playing_label.config(text=f"Error loading: {title_for_error[:30]}..."))
            self.root.after(0, self._restore_youtube_controls_state)


    def _handle_audio_url_fetched(self, track_idx_when_started, audio_url, title, autoplay):
        if track_idx_when_started != self.current_youtube_track_index and self.current_youtube_track_index != -1:
            self._restore_youtube_controls_state()
            if autoplay and self.current_youtube_track_index != -1 :
                 self._youtube_prepare_track(self.current_youtube_track_index, autoplay=True)
            return

        if audio_url:
            self.youtube_playlist[self.current_youtube_track_index]['audio_url'] = audio_url
            self.current_media = self.vlc_instance.media_new(audio_url)
            self.vlc_player.set_media(self.current_media)
            self.youtube_now_playing_label.config(text=title[:50])
            if autoplay:
                self.vlc_player.play()
                self.is_youtube_playing = True
                self.youtube_play_pause_button.config(text="⏸ Pause")
        else:
            self.youtube_now_playing_label.config(text=f"Failed to get stream for {title[:30]}...")
        self._restore_youtube_controls_state()


    def _youtube_play_pause(self):
        if not self.vlc_player: return

        if not self.youtube_playlist:
            if self.youtube_playlist_url_entry.get(): self._youtube_load_playlist()
            return

        if self.current_youtube_track_index == -1 and self.youtube_playlist:
            self._youtube_prepare_track(0, autoplay=True)
            return

        if self.is_youtube_playing:
            if self.vlc_player.can_pause():
                self.vlc_player.pause()
                self.is_youtube_playing = False
                self.youtube_play_pause_button.config(text="▶ Play")
        else:
            if self.current_media:
                 current_vlc_state = self.vlc_player.get_state()
                 if current_vlc_state == vlc.State.Ended:
                     self._youtube_prepare_track(self.current_youtube_track_index, autoplay=True)
                 else:
                    play_success = self.vlc_player.play()
                    if play_success == -1:
                        self.youtube_now_playing_label.config(text="Error playing media.")
                        self._restore_youtube_controls_state()
                    else:
                        self.is_youtube_playing = True
                        self.youtube_play_pause_button.config(text="⏸ Pause")
            elif self.youtube_playlist :
                 self._youtube_prepare_track(0, autoplay=True)


    def _youtube_prev_track(self):
        if not self.vlc_player or not self.youtube_playlist or len(self.youtube_playlist) == 0: return

        should_autoplay = self.is_youtube_playing or (self.vlc_player and self.vlc_player.get_state() == vlc.State.Playing)
        prev_index = (self.current_youtube_track_index - 1 + len(self.youtube_playlist)) % len(self.youtube_playlist)
        self._youtube_prepare_track(prev_index, autoplay=should_autoplay)

    def _youtube_next_track(self):
        if not self.vlc_player or not self.youtube_playlist or len(self.youtube_playlist) == 0: return

        should_autoplay = self.is_youtube_playing or (self.vlc_player and self.vlc_player.get_state() == vlc.State.Playing)
        next_index = (self.current_youtube_track_index + 1) % len(self.youtube_playlist)
        self._youtube_prepare_track(next_index, autoplay=should_autoplay)

    def _youtube_stop(self):
        if self.vlc_player:
            self.vlc_player.stop()
        self.is_youtube_playing = False
        self.youtube_play_pause_button.config(text="▶ Play")
        self.youtube_now_playing_label.config(text="Stopped")

    def _youtube_on_end_reached_event_handler(self, event):
        self.root.after(0, self._youtube_next_track)

    def _disable_youtube_controls_during_load(self, vlc_unavailable=False):
        if vlc_unavailable:
            self.youtube_load_playlist_button.config(state=tk.DISABLED)

        self.youtube_prev_button.config(state=tk.DISABLED)
        self.youtube_play_pause_button.config(state=tk.DISABLED)
        self.youtube_next_button.config(state=tk.DISABLED)
        self.youtube_stop_button.config(state=tk.DISABLED)

    def _restore_youtube_controls_state(self):
        if not self.vlc_player: return
        self.youtube_load_playlist_button.config(state=tk.NORMAL)

        if self.youtube_playlist:
            self.youtube_prev_button.config(state=tk.NORMAL)
            self.youtube_play_pause_button.config(state=tk.NORMAL)
            self.youtube_next_button.config(state=tk.NORMAL)
            self.youtube_stop_button.config(state=tk.NORMAL)
        else:
            self.youtube_prev_button.config(state=tk.DISABLED)
            self.youtube_play_pause_button.config(state=tk.DISABLED)
            self.youtube_next_button.config(state=tk.DISABLED)
            self.youtube_stop_button.config(state=tk.DISABLED)

    def _update_gemini_chat_initial_state(self):
        is_client_configured = self.gemini_client.is_configured()
        chat_elements_state = tk.NORMAL if is_client_configured else tk.DISABLED

        if hasattr(self, 'gemini_chat_input_entry'): self.gemini_chat_input_entry.config(state=chat_elements_state)
        if hasattr(self, 'gemini_send_message_button'): self.gemini_send_message_button.config(state=chat_elements_state)
        if hasattr(self, 'gemini_record_voice_button'): self.gemini_record_voice_button.config(state=chat_elements_state)

        if not is_client_configured:
            self._append_to_chat_history("System: Gemini client not configured. Please set API key in Settings -> Integrations.", "System")

    def _start_stt_thread(self):
        if hasattr(self, 'gemini_record_voice_button'): self.gemini_record_voice_button.config(state=tk.DISABLED, text="...")
        if hasattr(self, 'gemini_send_message_button'): self.gemini_send_message_button.config(state=tk.DISABLED)
        if hasattr(self, 'gemini_chat_input_entry'): self.gemini_chat_input_entry.config(state=tk.DISABLED)

        threading.Thread(target=self._record_and_transcribe_voice, daemon=True).start()

    def _record_and_transcribe_voice(self):
        recognizer = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                self.root.after(0, lambda: self._append_to_chat_history("System: Listening...", "System"))
                self.root.after(0, lambda: self._update_record_button_text("Listening..."))
                try:
                    recognizer.adjust_for_ambient_noise(source)
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                except sr.WaitTimeoutError:
                    self.root.after(0, lambda: self._handle_stt_error("No speech detected within timeout."))
                    return

            self.root.after(0, lambda: self._update_record_button_text("Transcribing..."))

            try:
                transcribed_text = recognizer.recognize_google(audio)
                self.root.after(0, lambda: self._handle_stt_success(transcribed_text))
            except sr.UnknownValueError:
                self.root.after(0, lambda: self._handle_stt_error("Could not understand audio"))
            except sr.RequestError as e:
                self.root.after(0, lambda: self._handle_stt_error(f"STT service error: {e}"))
            except Exception as e:
                self.root.after(0, lambda: self._handle_stt_error(f"Transcription error: {e}"))

        except sr.RequestError as e:
             self.root.after(0, lambda: self._handle_stt_error(f"Microphone error: {e}. Ensure a microphone is connected and configured."))
        except Exception as e:
            self.root.after(0, lambda: self._handle_stt_error(f"Could not access microphone: {e}"))
        finally:
            self.root.after(0, self._restore_chat_input_state)


    def _update_record_button_text(self, new_text):
        if hasattr(self, 'gemini_record_voice_button'):
            self.gemini_record_voice_button.config(text=new_text)

    def _restore_chat_input_state(self):
        is_client_configured = self.gemini_client.is_configured()
        record_button_state = tk.NORMAL if is_client_configured else tk.DISABLED
        send_button_state = tk.NORMAL if is_client_configured else tk.DISABLED
        input_entry_state = tk.NORMAL if is_client_configured else tk.DISABLED

        if hasattr(self, 'gemini_record_voice_button'):
            self.gemini_record_voice_button.config(text="🎤", state=record_button_state)
        if hasattr(self, 'gemini_send_message_button'):
            self.gemini_send_message_button.config(state=send_button_state)
        if hasattr(self, 'gemini_chat_input_entry'):
            self.gemini_chat_input_entry.config(state=input_entry_state)
            if is_client_configured: self.gemini_chat_input_entry.focus()


    def _handle_stt_success(self, transcribed_text):
        if hasattr(self, 'gemini_chat_input_entry'):
            self.gemini_chat_input_entry.delete(0, tk.END)
            self.gemini_chat_input_entry.insert(0, transcribed_text)
        self._append_to_chat_history(f"System: Transcribed: \"{transcribed_text}\"", "System")

    def _handle_stt_error(self, error_message):
        self._append_to_chat_history(f"System: STT Error: {error_message}", "System")

    def _speak_text_thread_target(self, text_to_speak):
        if self.tts_engine:
            try:
                self.tts_engine.setProperty('rate', self.config_manager.get("tts_rate"))
                voice_id = self.config_manager.get("tts_voice_id")
                if voice_id:
                    self.tts_engine.setProperty('voice', voice_id)

                self.tts_engine.say(text_to_speak)
                self.tts_engine.runAndWait()
            except Exception as e:
                print(f"Error during TTS operation: {e}")

    def _append_to_chat_history(self, message, sender="You"):
        if not hasattr(self, 'gemini_chat_history_text'): return
        self.gemini_chat_history_text.config(state=tk.NORMAL)

        formatted_message = f"{sender}: {message}\n\n"
        self.gemini_chat_history_text.insert(tk.END, formatted_message)
        self.gemini_chat_history_text.config(state=tk.DISABLED)
        self.gemini_chat_history_text.see(tk.END)

    def _send_gemini_message(self, event=None):
        if not hasattr(self, 'gemini_chat_input_entry') or not self.gemini_client.is_configured():
            if hasattr(self, 'gemini_chat_history_text'):
                 self._append_to_chat_history("System: Gemini client not configured. Please set API key in Settings -> Integrations.", "System")
            if hasattr(self, 'gemini_chat_input_entry'): self.gemini_chat_input_entry.config(state=tk.DISABLED)
            if hasattr(self, 'gemini_send_message_button'): self.gemini_send_message_button.config(state=tk.DISABLED)
            if hasattr(self, 'gemini_record_voice_button'): self.gemini_record_voice_button.config(state=tk.DISABLED)
            return

        user_input = self.gemini_chat_input_entry.get().strip()
        if not user_input:
            return

        self._append_to_chat_history(user_input, "You")
        self.gemini_chat_input_entry.delete(0, tk.END)

        self.gemini_chat_input_entry.config(state=tk.DISABLED)
        self.gemini_send_message_button.config(state=tk.DISABLED)
        if hasattr(self, 'gemini_record_voice_button'): self.gemini_record_voice_button.config(state=tk.DISABLED)
        self._append_to_chat_history("Gemini is thinking...", "System")


        def _gemini_api_call_thread_target(message_to_send):
            try:
                response = asyncio.run(self.gemini_client.send_message(message_to_send))
                self.root.after(0, lambda: self._handle_gemini_response(response))
            except Exception as e:
                print(f"Exception in Gemini API call thread: {e}")
                self.root.after(0, lambda: self._handle_gemini_response(f"System Error: {e}"))


        threading.Thread(target=_gemini_api_call_thread_target, args=(user_input,), daemon=True).start()

    def _handle_gemini_response(self, response_text):
        if not hasattr(self, 'gemini_chat_history_text'): return

        self.gemini_chat_history_text.config(state=tk.NORMAL)
        content = self.gemini_chat_history_text.get(1.0, tk.END).strip()
        lines = content.split('\n\n')
        if lines and lines[-1].startswith("System: Gemini is thinking..."):
            lines.pop()
            new_content = "\n\n".join(lines) + ("\n\n" if lines else "")
            self.gemini_chat_history_text.delete(1.0, tk.END)
            self.gemini_chat_history_text.insert(tk.END, new_content)
        self.gemini_chat_history_text.config(state=tk.DISABLED)

        self._append_to_chat_history(response_text, "Gemini")

        if self.config_manager.get("tts_enabled") and self.tts_engine:
            threading.Thread(target=self._speak_text_thread_target, args=(response_text,), daemon=True).start()

        if hasattr(self, 'gemini_chat_input_entry'): self.gemini_chat_input_entry.config(state=tk.NORMAL)
        if hasattr(self, 'gemini_send_message_button'): self.gemini_send_message_button.config(state=tk.NORMAL)
        if hasattr(self, 'gemini_record_voice_button'): self.gemini_record_voice_button.config(state=tk.NORMAL)
        if hasattr(self, 'gemini_chat_input_entry'): self.gemini_chat_input_entry.focus()

    # --- Task Drag and Drop Handlers ---
    def _on_task_drag_start(self, event):
        item_iid = self.task_tree.identify_row(event.y)
        if item_iid:
            task_id_tuple = self.task_tree.item(item_iid, "tags")
            if task_id_tuple and task_id_tuple[0]:
                self.dragging_task_id = str(task_id_tuple[0])
                self.drag_start_y = event.y
            else:
                self.dragging_task_id = None
        else:
            self.dragging_task_id = None

    def _on_task_drag_motion(self, event):
        if self.dragging_task_id:
            target_item_iid = self.task_tree.identify_row(event.y)
            # Future: Add visual cue for insertion point

    def _on_task_drag_release(self, event):
        if not self.dragging_task_id:
            return

        target_item_iid = self.task_tree.identify_row(event.y)
        dragged_task_id_str = str(self.dragging_task_id)

        if target_item_iid:
            target_task_id_tuple = self.task_tree.item(target_item_iid, "tags")
            if target_task_id_tuple and target_task_id_tuple[0]:
                target_task_id_str = str(target_task_id_tuple[0])

                if dragged_task_id_str != target_task_id_str:
                    position = "before"
                    success = self.task_manager.reorder_task(dragged_task_id_str, target_task_id_str, position)
                    if success:
                        self.refresh_task_list_and_daily_summary()
                        print(f"Task {dragged_task_id_str} moved successfully.")
                    else:
                        print(f"Failed to move task {dragged_task_id_str}.")
                else:
                    print("Drag cancelled: dropped on the same item.")
            else:
                print("Drag cancelled: invalid drop target.")
        else:
            success = self.task_manager.reorder_task(dragged_task_id_str, target_task_id=None, position="after")
            if success:
                self.refresh_task_list_and_daily_summary()
                print(f"Task {dragged_task_id_str} moved to the end successfully.")
            else:
                print(f"Failed to move task {dragged_task_id_str} to the end.")

        self.dragging_task_id = None
        self.drag_start_y = 0

    def update_current_datetime_display(self):
        now = datetime.datetime.now()
        self.datetime_label.config(text=now.strftime("%A, %B %d, %Y  %I:%M:%S %p"))
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

        self.daily_summary_labelframe.config(text=f"Summary for {self.selected_calendar_date.strftime('%Y-%m-%d')}")
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
        dialog.configure(bg=self.COLOR_BG)
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Select Scheduled Date:").pack(padx=10, pady=(10,5))
        
        initial_date_obj = None
        today = datetime.date.today()
        if task.scheduled_date:
            try: initial_date_obj = datetime.datetime.strptime(task.scheduled_date, "%Y-%m-%d").date()
            except ValueError: pass
        
        date_entry_year = initial_date_obj.year if initial_date_obj else today.year
        date_entry_month = initial_date_obj.month if initial_date_obj else today.month
        date_entry_day = initial_date_obj.day if initial_date_obj else today.day

        date_entry = DateEntry(dialog, width=12, background=self.COLOR_ACCENT, foreground='black', borderwidth=2,
                               date_pattern='yyyy-mm-dd', year=date_entry_year, month=date_entry_month, day=date_entry_day,
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
            
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Save Schedule", command=_save_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)


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
        edit_dialog.configure(bg=self.COLOR_BG); edit_dialog.transient(self.root); edit_dialog.grab_set()
        
        ttk.Label(edit_dialog, text="Task Text:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        edit_text_var = tk.StringVar(value=task.text)
        ttk.Entry(edit_dialog, textvariable=edit_text_var, width=40).grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        ttk.Label(edit_dialog, text="Est. Pomodoros:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        edit_est_var = tk.StringVar(value=str(task.estimated_pomodoros))
        ttk.Spinbox(edit_dialog, from_=1, to=20, textvariable=edit_est_var, width=5).grid(row=1, column=1, padx=10, pady=5, sticky="w")

        sched_date_entry = None 
        if TKCALENDAR_AVAILABLE:
            ttk.Label(edit_dialog, text="Scheduled Date:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
            initial_sched_date_obj = None
            today = datetime.date.today()
            if task.scheduled_date:
                try: initial_sched_date_obj = datetime.datetime.strptime(task.scheduled_date, "%Y-%m-%d").date()
                except ValueError: pass
            
            date_entry_year = initial_sched_date_obj.year if initial_sched_date_obj else today.year
            date_entry_month = initial_sched_date_obj.month if initial_sched_date_obj else today.month
            date_entry_day = initial_sched_date_obj.day if initial_sched_date_obj else today.day

            sched_date_entry = DateEntry(edit_dialog, date_pattern='yyyy-mm-dd', 
                                         year=date_entry_year, month=date_entry_month, day=date_entry_day,
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
                if self.current_task_id == task_id: self.current_task_display_label.config(text=f"Working on: {new_text[:40]}...")
                edit_dialog.destroy()
            else: messagebox.showerror("Input Error", "Task text cannot be empty.", parent=edit_dialog)

        button_frame = ttk.Frame(edit_dialog); button_frame.grid(row=3 if TKCALENDAR_AVAILABLE else 2, column=0, columnspan=2, pady=10)
        ttk.Button(button_frame, text="Save", command=save_edit).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=edit_dialog.destroy).pack(side=tk.LEFT, padx=5)
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
            if PLAYSOUND_AVAILABLE:
                self.root.bell() 
            
    def _play_sound(self, sound_type_for_config): 
        if not PLAYSOUND_AVAILABLE or not self.config_manager.get("sound_enabled"): return
        sound_key = "work_end_sound" if sound_type_for_config == self.WORK else "break_end_sound"
        
        sound_file_path_from_config = self.config_manager.get(sound_key)
        if not sound_file_path_from_config: return

        if os.path.isabs(sound_file_path_from_config):
            actual_sound_path = sound_file_path_from_config
        else:
            actual_sound_path = resource_path(sound_file_path_from_config)

        if os.path.exists(actual_sound_path):
            try:
                playsound(actual_sound_path, block=False)
            except Exception as e:
                print(f"Error playing sound {actual_sound_path}: {e}")
                detail_message = str(e)
                custom_message = f"Could not play sound: {os.path.basename(actual_sound_path)}"

                if "can't find a MCI Video device" in str(e).lower() and sys.platform == "win32":
                     custom_message = "MCI Error: Ensure audio drivers are working and file format (MP3/WAV) is supported."
                elif ("gstreamer" in str(e).lower() or "gst" in str(e).lower()) and sys.platform.startswith("linux"): 
                     custom_message = "GStreamer Error: Could not play sound. Ensure GStreamer plugins for MP3/WAV are installed."
                
                try:
                    messagebox.showwarning("Sound Playback Issue", custom_message, detail=detail_message, parent=self.root)
                except tk.TclError:
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
        settings_window.configure(bg=self.COLOR_BG)
        settings_window.transient(self.root)
        settings_window.grab_set()
        settings_window.resizable(False, True)

        settings_notebook = ttk.Notebook(settings_window)
        settings_notebook.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        general_settings_frame = ttk.Frame(settings_notebook, padding="15")
        settings_notebook.add(general_settings_frame, text="General")

        appearance_settings_frame = ttk.Frame(settings_notebook, padding="15")
        settings_notebook.add(appearance_settings_frame, text="Appearance")

        integrations_settings_frame = ttk.Frame(settings_notebook, padding="15")
        settings_notebook.add(integrations_settings_frame, text="Integrations")

        current_row_general = 0
        ttk.Label(general_settings_frame, text="Work Duration (min):").grid(row=current_row_general, column=0, sticky=tk.W, pady=3)
        work_var = tk.IntVar(value=self.config_manager.get("work_duration"))
        ttk.Spinbox(general_settings_frame, from_=1, to=120, textvariable=work_var, width=5).grid(row=current_row_general, column=1, sticky=tk.W, pady=3)
        current_row_general += 1

        ttk.Label(general_settings_frame, text="Short Break (min):").grid(row=current_row_general, column=0, sticky=tk.W, pady=3)
        short_break_var = tk.IntVar(value=self.config_manager.get("short_break_duration"))
        ttk.Spinbox(general_settings_frame, from_=1, to=60, textvariable=short_break_var, width=5).grid(row=current_row_general, column=1, sticky=tk.W, pady=3)
        current_row_general += 1

        ttk.Label(general_settings_frame, text="Long Break (min):").grid(row=current_row_general, column=0, sticky=tk.W, pady=3)
        long_break_var = tk.IntVar(value=self.config_manager.get("long_break_duration"))
        ttk.Spinbox(general_settings_frame, from_=1, to=120, textvariable=long_break_var, width=5).grid(row=current_row_general, column=1, sticky=tk.W, pady=3)
        current_row_general += 1

        ttk.Label(general_settings_frame, text="Pomos per Long Break:").grid(row=current_row_general, column=0, sticky=tk.W, pady=3)
        pomos_cycle_var = tk.IntVar(value=self.config_manager.get("pomodoros_per_long_break"))
        ttk.Spinbox(general_settings_frame, from_=1, to=10, textvariable=pomos_cycle_var, width=5).grid(row=current_row_general, column=1, sticky=tk.W, pady=3)
        current_row_general += 1
        
        ttk.Label(general_settings_frame, text="User Name:").grid(row=current_row_general, column=0, sticky=tk.W, pady=3)
        user_name_var = tk.StringVar(value=self.config_manager.get("user_name", "User"))
        ttk.Entry(general_settings_frame, textvariable=user_name_var, width=20).grid(row=current_row_general, column=1, sticky=tk.EW, pady=3)
        current_row_general += 1

        auto_start_var = tk.BooleanVar(value=self.config_manager.get("auto_start_next_session"))
        ttk.Checkbutton(general_settings_frame, text="Auto-start next session", variable=auto_start_var).grid(row=current_row_general, column=0, columnspan=2, sticky=tk.W, pady=3)
        current_row_general += 1

        sound_enabled_var = tk.BooleanVar(value=self.config_manager.get("sound_enabled"))
        ttk.Checkbutton(general_settings_frame, text="Enable sound notifications", variable=sound_enabled_var).grid(row=current_row_general, column=0, columnspan=2, sticky=tk.W, pady=3)
        current_row_general += 1
        
        ttk.Checkbutton(general_settings_frame, text="Always on Top", variable=self.always_on_top_var, command=self.update_always_on_top).grid(row=current_row_general, column=0, columnspan=2, sticky=tk.W, pady=3)
        current_row_general += 1

        self.default_sounds = {
            "Default Work Start": "sounds/work_start.mp3",
            "Default Work End": "sounds/work_end.mp3",
            "Default Break Start": "sounds/work_start.mp3",
            "Default Break End": "sounds/break_end.mp3",
            "Custom...": "custom"
        }
        sound_options = list(self.default_sounds.keys())

        ttk.Label(general_settings_frame, text="Work End Sound:").grid(row=current_row_general, column=0, sticky=tk.W, pady=3)
        work_sound_var = tk.StringVar()
        work_sound_combo = ttk.Combobox(general_settings_frame, textvariable=work_sound_var, values=sound_options, width=27, state="readonly")
        work_sound_combo.grid(row=current_row_general, column=1, sticky=tk.EW, pady=3)
        current_work_sound_path = self.config_manager.get("work_end_sound")
        found_friendly_work_sound = False
        for name, path in self.default_sounds.items():
            if path == current_work_sound_path:
                work_sound_var.set(name); found_friendly_work_sound = True; break
        if not found_friendly_work_sound and current_work_sound_path: work_sound_var.set("Custom...")
        ttk.Button(general_settings_frame, text="...", width=3, command=lambda: self._browse_sound_file(work_sound_var, "work_end_sound", work_sound_combo, settings_window)).grid(row=current_row_general, column=2, padx=5, pady=3)
        current_row_general += 1

        ttk.Label(general_settings_frame, text="Break End Sound:").grid(row=current_row_general, column=0, sticky=tk.W, pady=3)
        break_sound_var = tk.StringVar()
        break_sound_combo = ttk.Combobox(general_settings_frame, textvariable=break_sound_var, values=sound_options, width=27, state="readonly")
        break_sound_combo.grid(row=current_row_general, column=1, sticky=tk.EW, pady=3)
        current_break_sound_path = self.config_manager.get("break_end_sound")
        found_friendly_break_sound = False
        for name, path in self.default_sounds.items():
            if path == current_break_sound_path:
                break_sound_var.set(name); found_friendly_break_sound = True; break
        if not found_friendly_break_sound and current_break_sound_path: break_sound_var.set("Custom...")
        ttk.Button(general_settings_frame, text="...", width=3, command=lambda: self._browse_sound_file(break_sound_var, "break_end_sound", break_sound_combo, settings_window)).grid(row=current_row_general, column=2, padx=5, pady=3)

        general_settings_frame.columnconfigure(1, weight=1)

        self.color_vars = {}
        self.color_displays = {}

        colors_to_customize = [
            ("ui_color_bg", "App Background"),
            ("ui_color_fg", "Main Foreground"),
            ("ui_color_accent", "Accent Color"),
            ("ui_color_button", "Button Background"),
            ("ui_color_entry_bg", "Entry Background")
        ]
        appearance_current_row = 0
        for key, text in colors_to_customize:
            ttk.Label(appearance_settings_frame, text=f"{text}:").grid(row=appearance_current_row, column=0, sticky=tk.W, pady=4, padx=(0,5))
            color_val = self.config_manager.get(key)
            self.color_vars[key] = tk.StringVar(value=color_val)
            self.color_displays[key] = tk.Frame(appearance_settings_frame, width=20, height=20, relief=tk.SUNKEN, borderwidth=1, background=color_val)
            self.color_displays[key].grid(row=appearance_current_row, column=1, sticky=tk.W, padx=5)
            choose_cmd = lambda k=key, disp=self.color_displays[key]: self._choose_color(self.color_vars[k], disp, settings_window)
            ttk.Button(appearance_settings_frame, text="Choose...", command=choose_cmd).grid(row=appearance_current_row, column=2, sticky=tk.W, padx=5)
            appearance_current_row += 1
        appearance_settings_frame.columnconfigure(2, weight=1)

        integrations_current_row = 0
        
        gemini_settings_frame = ttk.LabelFrame(integrations_settings_frame, text="Gemini AI", padding=10)
        gemini_settings_frame.grid(row=integrations_current_row, column=0, columnspan=3, sticky="ew", pady=5)
        gemini_settings_frame.columnconfigure(1, weight=1)

        ttk.Label(gemini_settings_frame, text="API Key:").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.gemini_api_key_var = tk.StringVar(value=self.config_manager.get("gemini_api_key"))
        ttk.Entry(gemini_settings_frame, textvariable=self.gemini_api_key_var, width=38, show="*").grid(row=0, column=1, sticky=tk.EW, pady=3)

        ttk.Label(gemini_settings_frame, text="Model:").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.gemini_model_var = tk.StringVar(value=self.config_manager.get("gemini_model"))
        gemini_model_options = ["models/gemini-1.5-flash-latest", "models/gemini-pro", "models/gemini-1.0-pro"]
        model_combo = ttk.Combobox(gemini_settings_frame, textvariable=self.gemini_model_var, values=gemini_model_options, width=36, state="readonly")
        model_combo.grid(row=1, column=1, sticky=tk.EW, pady=3)
        integrations_current_row += 1

        tts_settings_frame = ttk.LabelFrame(integrations_settings_frame, text="Text-to-Speech (TTS)", padding=10)
        tts_settings_frame.grid(row=integrations_current_row, column=0, columnspan=3, sticky="ew", pady=5)
        tts_settings_frame.columnconfigure(1, weight=1)

        self.tts_enabled_var = tk.BooleanVar(value=self.config_manager.get("tts_enabled"))
        ttk.Checkbutton(tts_settings_frame, text="Enable TTS for Gemini responses", variable=self.tts_enabled_var).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=3)

        ttk.Label(tts_settings_frame, text="Speech Rate:").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.tts_rate_var = tk.IntVar(value=self.config_manager.get("tts_rate"))
        ttk.Spinbox(tts_settings_frame, from_=50, to=300, textvariable=self.tts_rate_var, width=5).grid(row=1, column=1, sticky=tk.W, pady=3)

        ttk.Label(tts_settings_frame, text="Voice:").grid(row=2, column=0, sticky=tk.W, pady=3)
        self.tts_voice_id_var = tk.StringVar(value=self.config_manager.get("tts_voice_id"))
        self.tts_voice_combo = ttk.Combobox(tts_settings_frame, textvariable=self.tts_voice_id_var, width=36, state="readonly")
        self.tts_voice_combo.grid(row=2, column=1, sticky=tk.EW, pady=3)

        self.tts_voice_display_names_to_ids = {}

        if self.tts_engine:
            try:
                voices = self.tts_engine.getProperty('voices')
                self.tts_available_voices = voices
                voice_display_names = []
                current_voice_id_from_config = self.config_manager.get("tts_voice_id")
                current_voice_display_name_to_set = None

                for i, voice in enumerate(voices):
                    lang = voice.languages[0] if voice.languages else "N/A"
                    gender = voice.gender if voice.gender else "N/A"
                    name_part = voice.name.split(' - ')[0] if ' - ' in voice.name else voice.name

                    max_name_len = 30
                    display_name = f"{name_part[:max_name_len]} ({lang}, {gender})"

                    self.tts_voice_display_names_to_ids[display_name] = voice.id
                    voice_display_names.append(display_name)

                    if voice.id == current_voice_id_from_config:
                        current_voice_display_name_to_set = display_name

                if voice_display_names:
                    self.tts_voice_combo['values'] = voice_display_names
                    self.tts_voice_combo.config(state="readonly")
                    if current_voice_display_name_to_set:
                        self.tts_voice_combo.set(current_voice_display_name_to_set)
                    elif voice_display_names:
                        self.tts_voice_combo.current(0)
                        self.tts_voice_id_var.set(self.tts_available_voices[0].id)
                else:
                    self.tts_voice_combo.config(state="disabled")
            except Exception as e:
                print(f"Error getting TTS voices: {e}")
                self.tts_voice_combo.config(state="disabled")
        else:
            self.tts_voice_combo.config(state="disabled")

        def _on_tts_voice_selected(event):
            selected_display_name = self.tts_voice_combo.get()
            if selected_display_name in self.tts_voice_display_names_to_ids:
                self.tts_voice_id_var.set(self.tts_voice_display_names_to_ids[selected_display_name])

        self.tts_voice_combo.bind("<<ComboboxSelected>>", _on_tts_voice_selected)
        integrations_current_row += 1

        integrations_settings_frame.columnconfigure(1, weight=1)

        button_frame = ttk.Frame(settings_window, padding=(0, 10, 0, 0))
        button_frame.pack(fill=tk.X, side=tk.BOTTOM)

        def save_and_close():
            self.config_manager.set("work_duration", work_var.get())
            self.config_manager.set("short_break_duration", short_break_var.get())
            self.config_manager.set("long_break_duration", long_break_var.get())
            self.config_manager.set("pomodoros_per_long_break", pomos_cycle_var.get())
            self.config_manager.set("user_name", user_name_var.get())
            self.config_manager.set("auto_start_next_session", auto_start_var.get())
            self.config_manager.set("sound_enabled", sound_enabled_var.get())
            self.config_manager.set("work_end_sound", self.work_sound_path_to_save.get())
            self.config_manager.set("break_end_sound", self.break_sound_path_to_save.get())

            for key, var_obj in self.color_vars.items():
                self.config_manager.set(key, var_obj.get())
            
            self.config_manager.set("gemini_api_key", self.gemini_api_key_var.get())
            self.config_manager.set("gemini_model", self.gemini_model_var.get())
            self.config_manager.set("tts_enabled", self.tts_enabled_var.get())
            self.config_manager.set("tts_rate", self.tts_rate_var.get())
            self.config_manager.set("tts_voice_id", self.tts_voice_id_var.get())

            self.config_manager.save_settings()
            self._apply_new_color_settings()

            if self.gemini_client:
                self.gemini_client.update_config(
                    api_key=self.config_manager.get("gemini_api_key"),
                    model_name=self.config_manager.get("gemini_model")
                )
            self._update_gemini_chat_initial_state()

            if self.tts_engine:
                try:
                    self.tts_engine.setProperty('rate', self.tts_rate_var.get())
                    selected_voice_id = self.tts_voice_id_var.get()
                    if selected_voice_id:
                        self.tts_engine.setProperty('voice', selected_voice_id)
                except Exception as e:
                    print(f"Error applying TTS settings: {e}")


            if not self.is_running: self.reset_current_session()
            self.update_pomodoro_count_display()
            self.update_always_on_top()
            settings_window.destroy()

        ttk.Button(button_frame, text="Save & Close", command=save_and_close).pack(side=tk.RIGHT, padx=(0,15))
        ttk.Button(button_frame, text="Cancel", command=settings_window.destroy).pack(side=tk.RIGHT, padx=(0,10))
    
    def _choose_color(self, color_var, display_widget, parent_window):
        from tkinter import colorchooser
        current_color = color_var.get()
        chosen_color_tuple = colorchooser.askcolor(color=current_color, parent=parent_window, title="Select Color")
        if chosen_color_tuple and chosen_color_tuple[1]:
            new_color_hex = chosen_color_tuple[1]
            color_var.set(new_color_hex)
            display_widget.config(background=new_color_hex)

    def _apply_new_color_settings(self):
        self._load_colors_from_config()
        self._setup_styles()
        self.root.configure(bg=self.COLOR_BG)
        if hasattr(self, 'main_paned_window'):
            self.main_paned_window.configure(bg=self.COLOR_ACCENT, sashcolor=self.COLOR_ACCENT)

        if hasattr(self, 'task_notes_text'):
            self.task_notes_text.config(bg=self.COLOR_ENTRY_BG, fg=self.COLOR_FG, insertbackground=self.COLOR_FG)
        if hasattr(self, 'daily_summary_text'):
            self.daily_summary_text.config(bg=self.COLOR_ENTRY_BG, fg=self.COLOR_FG)

        if TKCALENDAR_AVAILABLE and hasattr(self, 'cal'):
            self.cal.configure(
                background=self.COLOR_CALENDAR_HEADER, foreground='white',
                headersbackground=self.COLOR_CALENDAR_HEADER, headersforeground='white',
                bordercolor=self.COLOR_ACCENT,
                weekendbackground=self.COLOR_BG, weekendforeground=self.COLOR_CALENDAR_WEEKEND,
                othermonthbackground=self.COLOR_ENTRY_BG, othermonthwebackground=self.COLOR_ENTRY_BG,
                normalbackground=self.COLOR_TREEVIEW_BG, normalforeground=self.COLOR_FG,
                selectedbackground=self.COLOR_ACCENT, selectedforeground=self.COLOR_LONG_BREAK_FG
            )

        if hasattr(self, 'gemini_chat_history_text'):
            self.gemini_chat_history_text.config(bg=self.COLOR_ENTRY_BG, fg=self.COLOR_FG)

        self.update_ui_for_session()
        self.root.update_idletasks()


    def _browse_sound_file(self, combo_var, config_key_to_update, combobox_widget, parent_window):
        initial_dir_sounds = resource_path("sounds")
        if not os.path.isdir(initial_dir_sounds):
            initial_dir_sounds = resource_path("")

        filepath = filedialog.askopenfilename(
            parent=parent_window,
            title="Select Sound File",
            initialdir=initial_dir_sounds,
            filetypes=(("Audio Files", "*.wav *.mp3"), ("All files", "*.*"))
        )
        if filepath:
            normalized_filepath = os.path.normpath(filepath)
            app_root_normalized = os.path.normpath(resource_path(""))
            
            final_path_to_store = ""
            try:
                if normalized_filepath.startswith(app_root_normalized):
                    relative_path = os.path.relpath(normalized_filepath, app_root_normalized)
                    final_path_to_store = relative_path.replace(os.sep, "/")
                else:
                    final_path_to_store = normalized_filepath.replace(os.sep, "/")
            except ValueError:
                 final_path_to_store = normalized_filepath.replace(os.sep, "/")

            if config_key_to_update == "work_end_sound":
                self.work_sound_path_to_save.set(final_path_to_store)
            elif config_key_to_update == "break_end_sound":
                self.break_sound_path_to_save.set(final_path_to_store)

            combo_var.set("Custom...")

    def _bind_shortcuts(self): 
        self.root.bind('<Control-s>', self.start_timer)
        self.root.bind('<Control-P>', self.pause_timer)
        self.root.bind('<Control-R>', self.reset_current_session)
        self.root.bind('<Control-K>', self.skip_break)


    def on_close(self):
        self.save_task_notes_auto()
        if self.is_running and not self.paused:
             if not messagebox.askyesno("Timer Running", "Timer is running. Quit anyway?", parent=self.root): return
        if self.timer_id: self.root.after_cancel(self.timer_id)

        if self.tts_engine:
            try:
                self.tts_engine.stop()
            except Exception as e:
                print(f"Error stopping TTS engine: {e}")

        if self.vlc_player:
            try:
                self.vlc_player.stop()
                self.vlc_player.release()
            except Exception as e:
                print(f"Error releasing VLC player: {e}")
        if self.vlc_instance:
            try:
                self.vlc_instance.release()
            except Exception as e:
                print(f"Error releasing VLC instance: {e}")

        self.config_manager.save_settings()
        self.config_manager.save_session_log(self.session_log)
        self.root.destroy()

def main():
    root = tk.Tk()
    root.minsize(850, 650) 
    try:
        # Attempt PNG first as it's more broadly compatible for window icons via PhotoImage
        icon_path_png = resource_path("Misc/HyperPomo.png")
        if os.path.exists(icon_path_png):
            img = tk.PhotoImage(file=icon_path_png)
            root.tk.call('wm', 'iconphoto', root._w, img)
        else:
            # Fallback to ICO if PNG is not found (primarily for Windows taskbar)
            icon_path_ico = resource_path("Misc/HyperPomo.ico")
            if os.path.exists(icon_path_ico):
                root.iconbitmap(default=icon_path_ico) # Use default= for .ico
            else:
                print(f"Window icon (PNG or ICO) not found.")
    except Exception as e:
        print(f"Could not set window icon: {e}")

    app = PomodoroApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()

if __name__ == "__main__":
    main()