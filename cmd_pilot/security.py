from functools import lru_cache
import shlex
import re
from typing import Set, Dict, Any
import logging
import os
import traceback

class CommandValidator:
    """Centralized command validation with comprehensive security checks"""
    
    BLACKLISTED_PATTERNS = [
        # Combined command control patterns
        r'[&|;]\s*[&|;]',  # command chaining/separators
        r'[`$]\s*\(.*\)|\$\{.*\}',  # command substitution
        r'\|\s*[a-z]',  # piping to commands
        
        # Dangerous operations
        r'(rm|del)\s+-[rf]|[sq]',  # recursive/file deletion
        r'chmod\s+[0-7]{3,4}',  # permission changes
        r'(wget|curl)\s+https?://',  # remote downloads
        r'(nc|ncat|netcat)\s+-[a-z]',  # netcat usage
        r'(python|perl|ruby|bash)\s+-[c]',  # arbitrary code execution
        r'base64\s+-d',  # base64 encoded commands
        r'(\.\/|\.\.\/|\/etc\/|\/tmp\/)[^\s]*',  # sensitive file access
        r'(ssh|scp|sftp)\s+[^\s]+@[^\s]+'  # remote connections
    ]
    
    def __init__(self, allowed_commands: Set[str] = None):
        self._allowed_commands = allowed_commands or set()
        self._compiled_patterns = [re.compile(p) for p in self.BLACKLISTED_PATTERNS]

    @lru_cache(maxsize=512)
    def is_safe(self, command: str) -> bool:
        """Comprehensive command safety check with detailed validation"""
        command = command.strip()
        if not command:
            return False
            
        # Add check for relative paths
        if '../' in command or '/./' in command:
            return False
            
        # Add check for environment variables
        if '$(' in command or '${' in command:
            return False
            
        try:
            parsed = shlex.split(command)
            return (parsed[0] in self._allowed_commands and 
                   not any(p.search(command) for p in self._compiled_patterns) and
                   self._check_filesystem_access(parsed))
        except ValueError:
            return False
            
    def _check_filesystem_access(self, parsed_command: list) -> bool:
        """Check for dangerous filesystem operations"""
        dangerous_ops = {'rm', 'del', 'mv', 'chmod', 'chown'}
        return not (set(parsed_command) & dangerous_ops)
            
    def assess_risk(self, command: str) -> Dict[str, Any]:
        """Enhanced risk assessment with detailed scoring"""
        risk = {'level': 'low', 'score': 0, 'reasons': [], 'suggestions': []}
        
        # Length risk
        if len(command) > 100:
            risk['score'] += 20
            risk['reasons'].append('Long command (>100 chars)')
            
        # Complexity risk
        if len(shlex.split(command)) > 3:
            risk['score'] += 10 * (len(shlex.split(command)) - 3)
            risk['reasons'].append(f'Complex command ({len(shlex.split(command))} parts)')
            
        # Dangerous operations
        danger_ops = {
            'rm': 30, 'del': 30, 'kill': 25, 
            'chmod': 20, 'mv': 15, '>': 10
        }
        # Network operation risks
        network_ops = {
            'wget': 40, 'curl': 40, 'nc': 50, 
            'ssh': 30, 'scp': 30, 'telnet': 50
        }
        for op, score in network_ops.items():
            if op in command:
                risk['score'] += score
                risk['reasons'].append(f'Network operation: {op}')
                risk['suggestions'].append(f'Review {op} usage carefully')
        for op, score in danger_ops.items():
            if op in command:
                risk['score'] += score
                risk['reasons'].append(f'Dangerous operation: {op}')
                risk['suggestions'].append(f'Review {op} usage carefully')
        
        # Determine final level
        if risk['score'] >= 50:
            risk['level'] = 'critical'
        elif risk['score'] >= 30:
            risk['level'] = 'high'
        elif risk['score'] >= 15:
            risk['level'] = 'medium'
            
        return risk


class SecurityError(Exception):
    """Custom exception for security violations"""
    def __init__(self, message: str, command: str = None):
        super().__init__(message)
        self.command = command
        self.message = f"Security violation: {message}"
        if command:
            self.message += f" in command: {command}"


def sanitize_command(command: str) -> str:
    """Centralized command sanitization with strict validation"""
    command = command.strip()
    validator = CommandValidator()
    if not validator.is_safe(command):
        risk = validator.assess_risk(command)
        raise SecurityError(
            f"Command rejected (risk: {risk['level']})", 
            command
        )
    return ' '.join(shlex.split(command))


def log_security_event(event_type: str, details: str):
    """Centralized security logging with stack trace"""
    logger = logging.getLogger('security')
    logger.warning(
        f"Security event [{event_type}]: {details}\n"
        f"Stack trace: {''.join(traceback.format_stack())}"
    )


def validate_environment() -> bool:
    """Check for secure execution environment"""
    try:
        # Check for restricted PATH
        path = os.environ.get('PATH', '')
        if '/usr/local/sbin' in path or '/usr/sbin' in path:
            return False
            
        # Check for safe umask
        if os.umask(0) != 0o077:
            return False
            
        return os.geteuid() != 0  # Don't run as root
    except Exception as e:
        log_security_event('ENV_CHECK_FAILED', str(e))
        return False
