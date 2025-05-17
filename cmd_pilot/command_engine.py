import os
import platform
import asyncio
import tempfile
from typing import Any, Dict, List, Optional, Tuple, TypedDict, Union
from functools import partial, lru_cache
import logging
from cmd_pilot.config import MODEL_CONFIGS
from cmd_pilot.utils.error_handler import ErrorHandler
from cmd_pilot.utils.security import CommandValidator, SecurityError

class CommandContext:
    """Context manager for command execution environment"""
    def __init__(self):
        self.env = os.environ.copy()
        self.cwd = os.getcwd()
        self.umask = os.umask(0o077)  # 设置严格默认权限
        os.umask(self.umask)  # 还原原始umask

    def __enter__(self):
        os.chdir(tempfile.mkdtemp())  # 进入临时目录
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.chdir(self.cwd)  # 还原原始目录

class CommandEngine:
    """Enhanced command engine with AI generation and security validation"""
    
    def __init__(self, model_id: str):
        if model_id not in MODEL_CONFIGS:
            raise ValueError(f"Unsupported model: {model_id}")
        self.model_id = model_id
        self.config = MODEL_CONFIGS[model_id]
        self._validate_env()
        self.validator = CommandValidator()

    def _validate_env(self):
        """Validate required environment variables"""
        missing = [var for var in self.config['env_vars'] if not os.getenv(var)]
        if missing:
            raise EnvironmentError(f"Missing required env vars: {missing}")

    def _prepare_query_with_context(self, query: str) -> str:
        """Prepare query with system context"""
        return f"""根据以下要求生成系统命令:
[上下文] 当前系统: {platform.system()}
[用户需求] {query}
[解释] 命令作用和注意事项
[命令] ```shell
实际命令```
要求：简洁、安全、对高危操作警告"""

    def _build_system_message(self) -> Dict[str, str]:
        """Build system message for AI command generation"""
        return {
            "role": "system",
            "content": """你是一个命令行工具生成器，根据用户需求生成安全可靠的系统命令。
规则:
1. 只生成实际可执行的命令
2. 对危险操作必须添加警告注释
3. 优先使用跨平台兼容的命令"""
        }

    async def async_generate_command(self, query: str) -> Dict[str, Any]:
        """Generate command using AI with async support"""
        messages = [
            self._build_system_message(),
            {"role": "user", "content": self._prepare_query_with_context(query)}
        ]
        
        try:
            if self.config['api_type'] == 'openai':
                raw_response = await self._call_openai_api(messages)
            elif self.config['api_type'] == 'spark':
                raw_response = await self._call_spark_api(messages)
            else:
                raise ValueError("Unsupported API type")
            
            # 清理输出并提取命令
            sanitized = self._sanitize_output(raw_response)
            return {
                "sanitized": sanitized,
                "raw": raw_response,
                "error": None
            }
        except Exception as e:
            return {
                "sanitized": "",
                "raw": None,
                "error": str(e)
            }

    def _sanitize_output(self, text: str) -> str:
        """清理API响应，提取命令部分"""
        code_blocks = re.findall(r'```(?:bash|shell)?\n(.*?)```', text, re.DOTALL)
        if code_blocks:
            return code_blocks[-1].strip()
        return text.splitlines()[-1].strip() if text else ""

    def generate_command(self, query: str) -> Dict[str, str]:
        """Synchronous version of command generation"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.async_generate_command(query))

    def _get_highest_risk_level(self, risk_assessment):
        """获取最高风险等级"""
        for level in ['critical', 'high', 'medium']:
            if level in risk_assessment:
                return level
        return 'low'

    async def async_execute(self, query: str) -> Dict[str, str]:
        """Execute command with enhanced security validation"""
        try:
            command_data = await self.async_generate_command(query)
            sanitized = self.validator.sanitize_command(command_data['command'])
            
            if not self.validator.is_safe(sanitized):
                risk = self.validator.assess_risk(sanitized)
                highest_level = self._get_highest_risk_level(risk)
                risk_order = {'critical':3, 'high':2, 'medium':1, 'low':0}
                if risk_order[highest_level] > risk_order.get(self.config.get('max_risk_level', 'medium'), 1):
                    raise SecurityError("命令风险过高", command=sanitized, risk_level=highest_level)
            
            with CommandContext():
                return await self._execute_command(sanitized)
                
        except Exception as e:
            ErrorHandler.log_error(e, "COMMAND_EXECUTION_FAILED")
            raise

    def _execute_command(self, command: str) -> Dict[str, str]:
        """Actual command execution logic"""
        # Implementation would go here
        return {
            "output": "Command executed successfully",
            "status": "success",
            "command": command
        }

    def _call_openai_api(self, messages: List[Dict[str, str]]) -> str:
        """Call OpenAI API for command generation"""
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv(self.config['env_vars'][0]))
        response = client.chat.completions.create(
            model=self.config['model'],
            messages=messages
        )
        return response.choices[0].message.content

    def _call_spark_api(self, messages: List[Dict[str, str]]) -> str:
        """Call Spark API for command generation"""
        import requests
        from requests.exceptions import RequestException
        
        try:
            api_key = os.getenv(self.config['env_vars'][0])
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            payload = {
                "model": self.config['model'],
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2000
            }
            
            response = requests.post(
                self.config['base_url'],
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except RequestException as e:
            ErrorHandler.log_error(e, "SPARK_API_CALL_FAILED")
            raise ValueError(f"Spark API request failed: {str(e)}")
