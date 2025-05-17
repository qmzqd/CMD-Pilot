import re
from typing import Dict, Any

class SecurityError(Exception):
    """安全验证异常"""
    def __init__(self, message: str, command: str = None, risk_level: str = None):
        super().__init__(message)
        self.command = command
        self.risk_level = risk_level  # 新增风险等级属性

class CommandValidator:
    """命令验证器"""
    
    PRIVILEGE_PATTERNS = {
        'privilege_escalation': [
            r'\bsudo\s+\w+',
            r'\bpkexec\s+\w+',
            r'\bdoas\s+\w+',
            r'\bStart-Process\s+.*-Verb\s+RunAs',
            r'[;|&amp;]\s*[;|&amp;]'  # 严格匹配命令连接符
        ],
        'data_destruction': [
            r'\b(rm|del)\s+-[rf]',  # 严格匹配rm -r/f
            r'\bformat\s+\w+:',
            r'\bdd\s+if=.*of=',
            r'\bshred\s+-n',
            r'\bchmod\s+0{3,4}\s'
        ],
        'network_operations': [
            r'\b(curl|wget)\s+https?://',  # 匹配带URL的网络操作
            r'\bssh\s+-o\s+StrictHostKeyChecking=no',
            r'\bmount\s+.*-o\s+rw'
        ]
    }

    def sanitize_command(self, command: str) -> str:
        """清理命令中的潜在危险内容"""
        if not command:
            return ""
            
        # 移除注释
        cleaned = re.sub(r'#.*$', '', command)
        # 移除多余空格
        cleaned = ' '.join(cleaned.split())
        return cleaned

    @lru_cache(maxsize=512)
    def is_safe(self, command: str) -> bool:
        """检查命令是否安全"""
        command = command.strip()
        if not command:
            return False
        
        # 检查命令注入
        if re.search(r'[;&|]', command):
            return False
        
        try:
            parsed = shlex.split(command)
            if not parsed:
                return False
            return (parsed[0] in self._allowed_commands 
                    and not any(p.search(command) for p in self._compiled_patterns))
        except ValueError:
            return False

    def _check_filesystem_access(self, parsed_command: list) -> bool:
        """检查危险文件操作"""
        dangerous_commands = {'rm', 'del', 'mv', 'chmod', 'chown'}
        return parsed_command[0] not in dangerous_commands

    def assess_risk(self, command: str) -> Dict[str, Dict[str, Any]]:
        """评估命令风险级别"""
        results = {}
        for level, patterns in [
            ("critical", self.PRIVILEGE_PATTERNS['privilege_escalation']),
            ("high", self.PRIVILEGE_PATTERNS['data_destruction']),
            ("medium", self.PRIVILEGE_PATTERNS['network_operations'])
        ]:
            matched = []
            for pattern in patterns:
                if re.search(pattern, command, re.IGNORECASE):
                    matched.append(pattern)
            if matched:
                results[level] = {
                    "patterns": matched,
                    "count": len(matched)
                }
        return results
