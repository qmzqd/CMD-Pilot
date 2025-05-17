from tkinter import Frame, Text, Scrollbar
import logging
from typing import Optional


class ConsolePanel(Frame):
    """Enhanced console panel with improved error handling and async support."""
    
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._init_ui()
        self._setup_bindings()
        self._configure_tags()

    def _init_ui(self):
        # Main text widget with improved scrolling
        self.text = Text(self, wrap='word', undo=True)
        self.scrollbar = Scrollbar(self, command=self.text.yview)
        self.text.configure(yscrollcommand=self.scrollbar.set)
        
        # Layout using grid for better resize handling
        self.text.grid(row=0, column=0, sticky='nsew')
        self.scrollbar.grid(row=0, column=1, sticky='ns')
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def _setup_bindings(self):
        # Add right-click context menu
        self.text.bind('<Button-3>', self._show_context_menu)
        
    def _configure_tags(self):
        # Syntax highlighting tags
        self.text.tag_config('error', foreground='red')
        self.text.tag_config('warning', foreground='orange')
        self.text.tag_config('success', foreground='green')

    async def append_text(self, text: str, tag: Optional[str] = None):
        """Thread-safe text appending with optional tagging"""
        self.text.after(0, lambda: self._safe_append(text, tag))
        
    def _safe_append(self, text: str, tag: Optional[str] = None):
        """Actual text insertion (runs in main thread)"""
        self.text.configure(state='normal')
        self.text.insert('end', text + '\n', tag)
        self.text.configure(state='disabled')
        self.text.see('end')

    from cmd_pilot.utils.security import sanitize_command

    def sanitize_input(self, text: str) -> str:
        """Use centralized command sanitization"""
        return sanitize_command(text)

    def show_error(self, message: str):
        """Display error message with proper formatting"""
        self.append_text(f"ERROR: {message}", 'error')
        logging.error(message)
        
    def clear(self):
        """Clear console contents"""
        self.text.configure(state='normal')
        self.text.delete(1.0, 'end')
        self.text.configure(state='disabled')
