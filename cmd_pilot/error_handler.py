import requests
import json
import subprocess
import logging
from ..core.security import SecurityError


class ErrorHandler:
    @classmethod
    def handle_api_error(cls, exc: Exception) -> str:
        """Enhanced error handler for API-related exceptions"""
        error_map = {
            requests.Timeout: "API请求超时，请检查网络连接",
            requests.HTTPError: lambda e: f"HTTP错误: {e.response.status_code}",
            json.JSONDecodeError: "无效的API响应格式"
        }
        return error_map.get(type(exc), str(exc))
    
    @classmethod
    def handle_command_error(cls, exc: Exception) -> str:
        """Enhanced handler for command execution errors"""
        error_map = {
            subprocess.TimeoutExpired: "命令执行超时",
            subprocess.CalledProcessError: lambda e: f"命令执行失败 (返回码: {e.returncode})",
            SecurityError: lambda e: f"安全限制: {e.message} (风险等级: {e.risk_level})",
            FileNotFoundError: "命令不存在或路径错误"
        }
        if type(exc) in error_map:
            handler = error_map[type(exc)]
            return handler(exc) if callable(handler) else handler
        return str(exc)

    @classmethod
    def log_error(cls, exc: Exception, context: str = ""):
        """Enhanced error logging with security context"""
        if isinstance(exc, SecurityError):
            logging.error(
                f"[SECURITY][{context}] {exc.message} - "
                f"Command: {exc.command}, Risk: {exc.risk_level}",
                exc_info=True
            )
        else:
            logging.error(f"[{context}] Error: {str(exc)}", exc_info=True)

    @staticmethod
    def get_user_friendly_message(exc: Exception) -> str:
        """More comprehensive user-friendly messages"""
        if isinstance(exc, SecurityError):
            return f"安全限制: 检测到危险操作 ({exc.risk_level}风险)"
        elif isinstance(exc, (requests.Timeout, requests.ConnectionError)):
            return "网络连接出现问题，请检查后重试"
        elif isinstance(exc, json.JSONDecodeError):
            return "服务器返回了无效的响应"
        elif isinstance(exc, subprocess.CalledProcessError):
            return f"命令执行失败 (错误码: {exc.returncode})"
        return "发生未知错误，请查看日志获取详细信息"
