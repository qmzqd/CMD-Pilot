import logging
from typing import Any

class ErrorHandler:
    """错误处理工具类"""
    
    @staticmethod
    def log_error(error: Exception, context: str = None) -> None:
        """记录错误日志
        
        Args:
            error: 异常对象
            context: 错误上下文信息
        """
        error_msg = f"[{context}] {str(error)}" if context else str(error)
        logging.error(error_msg)
        
        # 可以在这里添加其他错误处理逻辑，如发送错误报告等
