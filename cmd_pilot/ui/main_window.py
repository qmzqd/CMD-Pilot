from cmd_pilot.ui.components.console import ConsolePanel
from cmd_pilot.ui.components.top_bar import TopBar
from cmd_pilot.ui.components.command_history import CommandHistory
from cmd_pilot.utils.security import CommandValidator
from cmd_pilot.utils.error_handler import ErrorHandler
import tkinter as tk
from tkinter import messagebox
import asyncio

"""
Main application window module
"""

class ModernUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self._init_components()
        self.command_validator = CommandValidator()
    def _init_components(self):
        """Initialize all UI components using factory methods"""
        self._init_top_bar()
        self._init_console()
        self._init_command_history()
        
    def _init_top_bar(self):
        self.top_bar = TopBar(self)
        self.top_bar.pack(fill=tk.X)
        
    def _init_console(self):
        self.console = ConsolePanel(self)
        self.console.pack(fill=tk.BOTH, expand=True)
        
    def _init_command_history(self):
        self.history = CommandHistory(self)
        self.history.pack(fill=tk.BOTH)

    def execute_command(self, command):
        """Modified to use async execution with proper error handling"""
        if not self.validate_command(command):
            return
            
        async def _execute():
            try:
                result = await self.command_engine.async_execute(command)
                self.console.update_output(result)
            except Exception as e:
                ErrorHandler.log_error(e, "COMMAND_EXECUTION")
                self.show_error(f"Execution failed: {str(e)}")
                
        asyncio.create_task(_execute())

    #                           Error Handling
    # ===

    # -------------------------------------------------------------------------
    #                           Error Handling
    # -------------------------------------------------------------------------

    #                           Error Handling
    # ===
    def show_error(self, message):
        """Standardized error display using messagebox"""
        messagebox.showerror("Error", message)

    def validate_command(self, command):
        """Use centralized command validation with risk assessment"""
        if not self.command_validator.is_safe(command):
            risk = self.command_validator.assess_risk(command)
            self.show_error(
                f"Command rejected (Risk: {risk['level']})\n"
                f"Reasons: {', '.join(risk['reasons'])}"
            )
            return False
        return True
