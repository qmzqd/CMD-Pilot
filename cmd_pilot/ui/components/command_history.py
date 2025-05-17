# cmd_pilot/ui/components/command_history.py
from tkinter import Frame, Listbox, Scrollbar
from typing import List, Optional
import logging

class CommandHistory(Frame):
    """Component for displaying and managing command history"""

    def __init__(self, master, max_history: int = 100, **kwargs):
        super().__init__(master, **kwargs)
        self.max_history = max_history
        self._init_ui()
        self.history: List[str] = []

    def _init_ui(self):
        self.listbox = Listbox(self)
        self.scrollbar = Scrollbar(self, orient="vertical")
        
        self.listbox.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.listbox.yview)
        
        self.listbox.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    def add_command(self, command: str) -> None:
        """Add a command to history with validation"""
        if not command or command in self.history:
            return
            
        self.history.insert(0, command)
        self.listbox.insert(0, command)
        
        if len(self.history) > self.max_history:
            self.history.pop()
            self.listbox.delete(self.max_history)

    def get_selected(self) -> Optional[str]:
        """Get currently selected command"""
        try:
            return self.listbox.get(self.listbox.curselection())
        except:
            return None

    def clear(self) -> None:
        """Clear command history"""
        try:
            self.history.clear()
            self.listbox.delete(0, "end")
        except Exception as e:
            logging.error(f"Error clearing history: {e}")
