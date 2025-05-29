
import uuid
import datetime

class Task:
    def __init__(self, text, estimated_pomodoros=1, completed_pomodoros=0,
                 done=False, id=None, notes="", scheduled_date=None, due_date=None,
                 created_at=None, completed_at=None):
        self.id = id if id is not None else str(uuid.uuid4())
        self.text = text
        self.estimated_pomodoros = int(estimated_pomodoros)
        self.completed_pomodoros = int(completed_pomodoros)
        self.done = bool(done)
        self.notes = notes if notes else ""
        
        # Dates should be stored as ISO format strings (YYYY-MM-DD)
        self.scheduled_date = scheduled_date # Date the task is planned to be worked on
        self.due_date = due_date # Optional deadline
        
        self.created_at = created_at if created_at else datetime.datetime.now().isoformat()
        self.completed_at = completed_at # ISO string, set when task is marked done

    def to_dict(self):
        return {
            "id": self.id, "text": self.text,
            "estimated_pomodoros": self.estimated_pomodoros,
            "completed_pomodoros": self.completed_pomodoros,
            "done": self.done, "notes": self.notes,
            "scheduled_date": self.scheduled_date,
            "due_date": self.due_date,
            "created_at": self.created_at,
            "completed_at": self.completed_at
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            text=data.get("text", "Untitled Task"),
            estimated_pomodoros=data.get("estimated_pomodoros", 1),
            completed_pomodoros=data.get("completed_pomodoros", 0),
            done=data.get("done", False),
            id=data.get("id"),
            notes=data.get("notes", ""),
            scheduled_date=data.get("scheduled_date"),
            due_date=data.get("due_date"),
            created_at=data.get("created_at"),
            completed_at=data.get("completed_at")
        )

    def __str__(self):
        status = "[X]" if self.done else "[ ]"
        schedule_info = f" (Sch: {{self.scheduled_date}})" if self.scheduled_date else ""
        return f"{{status}} {{self.text}}{{schedule_info}} (Est: {{self.estimated_pomodoros}}, Done: {{self.completed_pomodoros}})"

class TaskManager:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.tasks = self._load_tasks_from_config()

    def _load_tasks_from_config(self):
        task_data_list = self.config_manager.get_all_tasks()
        return [Task.from_dict(data) for data in task_data_list]

    def _save_tasks_to_config(self):
        self.config_manager.save_tasks([task.to_dict() for task in self.tasks])

    def add_task(self, text, estimated_pomodoros=1, notes="", scheduled_date=None, due_date=None):
        if not text.strip(): return None
        # Ensure date is in YYYY-MM-DD string format if provided
        if isinstance(scheduled_date, datetime.date):
            scheduled_date = scheduled_date.isoformat()
        if isinstance(due_date, datetime.date):
            due_date = due_date.isoformat()
            
        new_task = Task(text.strip(), estimated_pomodoros, notes=notes, 
                        scheduled_date=scheduled_date, due_date=due_date)
        self.tasks.append(new_task)
        self._save_tasks_to_config()
        return new_task

    def remove_task(self, task_id):
        self.tasks = [task for task in self.tasks if task.id != task_id]
        self._save_tasks_to_config()

    def toggle_task_done(self, task_id):
        for task in self.tasks:
            if task.id == task_id:
                task.done = not task.done
                task.completed_at = datetime.datetime.now().isoformat() if task.done else None
                break
        self._save_tasks_to_config()
    
    def increment_pomodoro_for_task(self, task_id):
        for task in self.tasks:
            if task.id == task_id:
                task.completed_pomodoros += 1
                break
        self._save_tasks_to_config()

    def get_task_by_id(self, task_id):
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def get_tasks_by_scheduled_date(self, date_obj): # date_obj is datetime.date
        date_str = date_obj.isoformat()
        return [task for task in self.tasks if task.scheduled_date == date_str and not task.done]
    
    def get_unscheduled_active_tasks(self):
        return [task for task in self.tasks if not task.scheduled_date and not task.done]

    def get_all_active_tasks(self): # All active, regardless of schedule
        return [task for task in self.tasks if not task.done]
        
    def get_completed_tasks(self, scheduled_date_obj=None):
        if scheduled_date_obj:
            date_str = scheduled_date_obj.isoformat()
            return [task for task in self.tasks if task.done and task.scheduled_date == date_str]
        return [task for task in self.tasks if task.done]


    def update_task(self, task_id, text=None, estimated_pomodoros=None, notes=None, 
                    scheduled_date=None, due_date=None):
        task = self.get_task_by_id(task_id)
        if task:
            if text is not None: task.text = text
            if estimated_pomodoros is not None: task.estimated_pomodoros = int(estimated_pomodoros)
            if notes is not None: task.notes = notes
            if scheduled_date is not None: # Can be datetime.date object or string or None
                task.scheduled_date = scheduled_date.isoformat() if isinstance(scheduled_date, datetime.date) else scheduled_date
            if due_date is not None:  # Can be datetime.date object or string or None
                task.due_date = due_date.isoformat() if isinstance(due_date, datetime.date) else due_date
            self._save_tasks_to_config()
            return True
        return False
