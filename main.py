import os
import re
import platform
import subprocess
import threading
import asyncio
import requests
import tempfile
import json
import shlex
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple, TypedDict, Union
from functools import partial, lru_cache
import argparse
import logging
from dotenv import load_dotenv
import sys
import os
# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

from CMD_Pilot.cmd_pilot.core.command_engine import CommandEngine, CommandContext
from CMD_Pilot.cmd_pilot.security import SecurityError

# ========== 配置部分 ==========
from CMD_Pilot.cmd_pilot.config import (
    MODEL_CONFIGS, 
    UI_THEME, 
    UI_STYLE, 
    DEFAULT_SETTINGS, 
    ALLOWED_COMMANDS,
    ModelConfig,
    ThemeConfig,
    UIStyle
)

class EnhancedConfig:
    """增强配置类，提供配置访问接口"""
    
    MODEL_CONFIGS = MODEL_CONFIGS
    UI_THEME = UI_THEME
    UI_STYLE = UI_STYLE
    DEFAULT_SETTINGS = DEFAULT_SETTINGS
    ALLOWED_COMMANDS = ALLOWED_COMMANDS
    lock = threading.Lock()  # 添加线程锁

    @classmethod
    @lru_cache(maxsize=32)
    def get_model_config(cls, model_id: str) -> ModelConfig:
        """Cached config access"""
        from copy import deepcopy
        return deepcopy(cls.MODEL_CONFIGS.get(model_id))

# ========== 引擎部分 ==========
        
        data = {
            "model": self.config["model"],
            "messages": messages,
            "temperature": 0.3
        }
        
        response = requests.post(
            f"{self.config['base_url']}/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        try:
            # 记录请求详情
            logging.debug(f"API请求: URL={self.config['base_url']}, Headers={headers}, Data={data}")
            
            response.raise_for_status()
            response_data = response.json()
            
            # 记录完整响应
            logging.debug(f"API响应: {response_data}")
            
            if not isinstance(response_data, dict):
                error_msg = "API响应不是有效的JSON对象"
                logging.error(error_msg)
                raise ValueError(error_msg)
                
            choices = response_data.get("choices", [])
            if not isinstance(choices, list) or len(choices) == 0:
                error_msg = "API响应缺少choices字段"
                logging.error(error_msg)
                raise ValueError(error_msg)
                
            message = choices[0].get("message", {})
            if not isinstance(message, dict):
                error_msg = "API响应message字段无效"
                logging.error(error_msg)
                raise ValueError(error_msg)
                
            content = message.get("content")
            if not isinstance(content, str):
                error_msg = "API响应content不是字符串"
                logging.error(error_msg)
                raise ValueError(error_msg)
                
            return content
            
        except requests.RequestException as e:
            error_msg = f"API请求失败: {str(e)}"
            logging.error(error_msg)
            raise RuntimeError(error_msg)
        except (ValueError, KeyError, IndexError) as e:
            error_msg = f"API响应解析失败: {str(e)}"
            logging.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"未知API错误: {str(e)}"
            logging.error(error_msg)
            raise RuntimeError(error_msg)

    def _call_spark_api(self, messages: List[Dict[str, str]]) -> str:
        """调用讯飞星火API"""
        # 实现讯飞星火API调用逻辑
        pass

    def _sanitize_output(self, text: Optional[str]) -> str:
        """清理输出文本，提取命令部分"""
        if text is None:
            return ""
        if not isinstance(text, str):
            return str(text)
            
        code_blocks = re.findall(r'```(?:bash|shell|powershell|cmd)?\n(.*?)```', text, re.DOTALL)
        if code_blocks:
            return code_blocks[-1].strip()
        
        lines = text.splitlines()
        commands = [line.strip() for line in lines if line.strip() and not line.startswith('#')]
        return '\n'.join(commands[-3:]) if commands else ""

    def confirm_risky_command(self, command: str) -> bool:
        risk_level = self.analyze_risk(command).keys()
        if 'critical' in risk_level:
            print(f"警告！检测到高危操作: {command}")
            return input("确认执行？(y/N) ").lower() == 'y'
        return True

    def execute(self, command: str) -> Tuple[str, int]:
        if not command:
            return "空命令", -1
        
        # 使用配置中的白名单
        command_base = (shlex.split(command)[0] if command else '')
        if command_base not in EnhancedConfig.ALLOWED_COMMANDS:
            return f"拒绝执行未授权命令: {command}", -1
        
        # 高危命令确认
        if not self.confirm_risky_command(command):
            return "用户取消执行高危命令", -1
        
        try:
            with CommandContext() as ctx:
                with ctx:  # 确保上下文管理器正确生效
                    with self.lock:
                        self.current_process = subprocess.Popen(
                            command,
                            shell=False,  # 禁用shell执行
                            executable='/bin/bash' if os.name == 'posix' else None,
                            env=ctx.env,
                            cwd=ctx.cwd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )
                    stdout, stderr = self.current_process.communicate(timeout=60)
                    return_code = self.current_process.returncode
                    
                    if stderr:
                        return stderr.strip(), return_code
                    return stdout.strip(), return_code
        except subprocess.TimeoutExpired:
            self.terminate_process()
            return "执行超时（60秒）", -1
        except Exception as e:
            return f"执行错误: {str(e)}", -1
        finally:
            with self.lock:
                self.current_process = None

    def terminate_process(self):
        with self.lock:
            if self.current_process:
                self.current_process.kill()
                try:
                    self.current_process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    self.current_process.terminate()

    PRIVILEGE_PATTERNS = {
        'privilege_escalation': [
            r'sudo\s+\w+',
            r'pkexec\s+\w+',
            r'doas\s+\w+',
            r'Start-Process\s+.*-Verb\s+RunAs'
        ],
        'data_destruction': [
            r'rm\s+-(rf|fr)',
            r'format\s+\w+:',
            r'dd\s+if=.*of=',
            r'shred\s+-n',
            r'chmod\s+0{3,4}\s'
        ],
        'network_operations': [
            r'curl\s+-F\s+@',
            r'wget\s+--post-file',
            r'ssh\s+-o\s+StrictHostKeyChecking=no',
            r'mount\s+.*-o\s+rw'
        ]
    }

    def analyze_risk(self, command: str) -> Dict[str, Dict[str, Any]]:
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

class AsyncExecutor:
    """Helper class for async operations"""
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def run_blocking(self, func, *args):
        return await self.loop.run_in_executor(
            self.executor, 
            partial(func, *args)
        )

class PlaceholderText(tk.Text):
    """带placeholder提示的文本框"""
    def __init__(
        self, 
        master: Optional[tk.Widget] = None, 
        placeholder: Optional[str] = None, 
        **kwargs: Any
    ) -> None:
        super().__init__(master, **kwargs)
        self.placeholder = placeholder
        self._setup_bindings()
        self._set_placeholder()

    def _setup_bindings(self) -> None:
        """设置事件绑定"""
        self.bind("<FocusIn>", self._clear_placeholder)
        self.bind("<FocusOut>", self._set_placeholder)

    def _set_placeholder(self, event: Optional[tk.Event] = None) -> None:
        """设置placeholder文本"""
        if not self.get("1.0", "end-1c"):
            self.insert("1.0", self.placeholder)
            self.config(fg="grey")

    def _clear_placeholder(self, event=None):
        if self.get("1.0", "end-1c") == self.placeholder:
            self.delete("1.0", "end")
            self.config(fg="black")

class ToolTip:
    """悬浮提示工具类"""
    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event: Optional[tk.Event] = None) -> None:
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        
        label = ttk.Label(tw, text=self.text, background="#ffffe0",
                          relief="solid", borderwidth=1)
        label.pack()

    def hide_tip(self, event: Optional[tk.Event] = None) -> None:
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

class ModernUI(tk.Tk):
    def __init__(self, default_model: str = "moonshot") -> None:
        super().__init__()
        self.title("智能命令助手")
        self.geometry("1000x700")
        self.default_model = default_model
        self.async_executor = AsyncExecutor()
        
        # 先初始化样式，再设置关闭协议
        if not self._init_styles():
            messagebox.showerror("错误", "UI样式初始化失败")
            self.destroy()
            return
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self) -> None:
        """处理窗口关闭事件"""
        # 停止任何正在运行的任务
        if hasattr(self, 'current_task') and self.current_task and not self.current_task.done():
            self.current_task.cancel()
        
        # 保存设置
        if hasattr(self, '_save_settings'):
            self._save_settings()
        
        # 关闭线程池
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)
        
        # 销毁窗口
        self.destroy()

    @staticmethod
    def _adjust_color(hex_color: str, delta: int) -> str:
        """调整颜色亮度"""
        r = max(0, min(255, int(hex_color[1:3], 16) + delta))
        g = max(0, min(255, int(hex_color[3:5], 16) + delta))
        b = max(0, min(255, int(hex_color[5:7], 16) + delta))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _init_styles(self):
        """初始化样式配置"""
        style = ttk.Style()
        style.theme_use("clam")
        
        # 基础样式
        style.configure(".", 
            font=(EnhancedConfig.UI_THEME['font_family'], EnhancedConfig.UI_THEME['font_size']),
            background=EnhancedConfig.UI_THEME['bg'],
            foreground=EnhancedConfig.UI_THEME['text']
        )
        
        # 按钮样式
        style.configure("Primary.TButton", 
            background=EnhancedConfig.UI_THEME['primary'],
            foreground="white",
            **EnhancedConfig.UI_STYLE["TButton"]
        )
        style.map("Primary.TButton",
            background=[('active', self._adjust_color(EnhancedConfig.UI_THEME['primary'], -20))],
            relief=[('pressed', 'sunken'), ('!pressed', 'raised')]
        )
        
        # 初始化配置
        self.config_path = os.path.expanduser('~/.cmd_assistant_config.json')
        self.settings = self._load_settings()
        
        self.active_model = "moonshot"
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.current_task: Optional[Future] = None
        self.last_command: Optional[str] = None
        self.raw_response: Optional[str] = None
        
        try:
            self.engine = CommandEngine(self.active_model)
        except Exception as e:
            messagebox.showerror("初始化错误", str(e))
            self.destroy()
            return False
        
        self._init_components()
        self._setup_bindings()
        return True

    def _load_settings(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except:
                return EnhancedConfig.DEFAULT_SETTINGS.copy()
        return EnhancedConfig.DEFAULT_SETTINGS.copy()

    def _save_settings(self) -> None:
        with open(self.config_path, 'w') as f:
            json.dump(self.settings, f, indent=2)

    def _init_components(self) -> None:
        self._create_top_bar()
        self._create_input_panel()
        self._create_command_display()
        self._create_action_buttons()
        self._create_output_panel()
        self._create_status_bar()

    def _create_top_bar(self) -> None:
        """创建顶部控制栏"""
        self.top_frame = ttk.Frame(self, padding=(10, 5))
        self.top_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 左侧模型选择区域
        self._create_model_selector()
        
        # 右侧操作区域
        self._create_action_controls()

    def _create_model_selector(self):
        """创建模型选择组件"""
        model_frame = ttk.Frame(self.top_frame)
        model_frame.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(model_frame, text="AI模型:").pack(side=tk.LEFT)
        self.model_var = tk.StringVar()
        self.model_combobox = ttk.Combobox(
            model_frame,
            textvariable=self.model_var,
            values=list(EnhancedConfig.MODEL_CONFIGS.keys()),
            state="readonly"
        )
        self.model_combobox.pack(side=tk.LEFT, padx=5)
        self.model_combobox.current(0)
        ToolTip(self.model_combobox, "选择不同的大模型进行交互")

    def _create_action_controls(self):
        """创建操作控制组件"""
        action_frame = ttk.Frame(self.top_frame)
        action_frame.pack(side=tk.RIGHT, padx=5)
        
        # 上下文管理
        self.clear_ctx_btn = ttk.Button(
            action_frame,
            text="清除上下文",
            command=self._clear_context,
            style="Primary.TButton"
        )
        self.clear_ctx_btn.pack(side=tk.RIGHT, padx=5)
        ToolTip(self.clear_ctx_btn, "清除当前对话上下文")
        
        # 显示选项
        self.raw_output_var = tk.BooleanVar(value=self.settings.get('show_raw_output', False))
        self.raw_output_cb = ttk.Checkbutton(
            action_frame,
            text="显示原始输出",
            variable=self.raw_output_var,
            command=self._update_settings
        )
        self.raw_output_cb.pack(side=tk.RIGHT, padx=5)
        ToolTip(self.raw_output_cb, "显示AI返回的原始JSON数据")

    def _create_input_panel(self):
        """创建输入面板"""
        input_frame = ttk.LabelFrame(
            self,
            text="输入指令",
            padding=(10, 5)
        )
        input_frame.pack(fill=tk.BOTH, padx=10, pady=5, expand=True)
        
        self.input_text = PlaceholderText(
            input_frame,
            placeholder="请输入您的指令...",
            wrap=tk.WORD,
            height=5,
            font=(EnhancedConfig.UI_THEME['font_family'], EnhancedConfig.UI_THEME['font_size']),
            bg="white",
            fg="black",
            insertbackground="black"
        )
        self.input_text.pack(fill=tk.BOTH, expand=True)

    def _create_command_display(self):
        """创建命令显示区域"""
        command_frame = ttk.LabelFrame(
            self,
            text="生成命令",
            padding=(10, 5)
        )
        command_frame.pack(fill=tk.BOTH, padx=10, pady=5)
        
        self.command_text = tk.Text(
            command_frame,
            wrap=tk.WORD,
            height=3,
            font=("Consolas", 12),
            bg="#f8f8f8",
            fg=EnhancedConfig.UI_THEME['text'],
            state=tk.DISABLED
        )
        self.command_text.pack(fill=tk.BOTH)

    def _create_action_buttons(self):
        """创建操作按钮"""
        button_frame = ttk.Frame(self, padding=(10, 5))
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.generate_btn = ttk.Button(
            button_frame,
            text="生成命令",
            command=self._on_generate,
            style="Primary.TButton"
        )
        self.generate_btn.pack(side=tk.LEFT, padx=5)
        
        self.execute_btn = ttk.Button(
            button_frame,
            text="执行命令",
            command=self._on_execute,
            style="Primary.TButton"
        )
        self.execute_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(
            button_frame,
            text="停止",
            command=self.stop_process,
            style="Primary.TButton"
        )
        self.stop_btn.pack(side=tk.RIGHT, padx=5)

    def _create_output_panel(self):
        """创建输出面板"""
        output_frame = ttk.LabelFrame(
            self,
            text="输出结果",
            padding=(10, 5)
        )
        output_frame.pack(fill=tk.BOTH, padx=10, pady=5, expand=True)
        
        self.output_notebook = ttk.Notebook(output_frame)
        self.output_notebook.pack(fill=tk.BOTH, expand=True)
        
        # 控制台输出
        self._create_console_output(self.output_notebook)
        
        # 结构化视图
        self._create_structured_view(self.output_notebook)

    def _create_console_output(self, parent):
        """创建控制台输出"""
        console_frame = ttk.Frame(parent)
        self.console_text = scrolledtext.ScrolledText(
            console_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg="black",
            fg="white",
            state=tk.DISABLED
        )
        self.console_text.pack(fill=tk.BOTH, expand=True)
        parent.add(console_frame, text="控制台")

    def _create_structured_view(self, parent):
        """创建结构化视图"""
        struct_frame = ttk.Frame(parent)
        
        # 命令历史
        history_frame = ttk.LabelFrame(
            struct_frame,
            text="命令历史",
            padding=(5, 5)
        )
        history_frame.pack(fill=tk.BOTH, padx=5, pady=5, expand=True)
        
        self.history_tree = ttk.Treeview(
            history_frame,
            columns=("time", "command", "result"),
            show="headings"
        )
        self.history_tree.heading("time", text="时间")
        self.history_tree.heading("command", text="命令")
        self.history_tree.heading("result", text="结果")
        self.history_tree.pack(fill=tk.BOTH, expand=True)
        
        parent.add(struct_frame, text="结构化视图")

    def _create_status_bar(self):
        """创建状态栏和进度条"""
        status_frame = ttk.Frame(self)
        status_frame.pack(fill=tk.X, padx=1, pady=1)
        
        # 状态文本
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            width=20
        )
        status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 进度条
        self.progress = ttk.Progressbar(
            status_frame,
            orient=tk.HORIZONTAL,
            mode='indeterminate',
            length=100
        )
        self.progress.pack(side=tk.RIGHT)

    def _setup_bindings(self):
        """设置事件绑定"""
        self.model_combobox.bind("<<ComboboxSelected>>", self._on_model_change)
        self.input_text.bind("<Return>", self._on_generate)
        
        # 快捷键
        self.bind("<Control-g>", lambda e: self._on_generate())
        self.bind("<Control-e>", lambda e: self._on_execute())
        self.bind("<Control-q>", lambda e: self._on_close())

    def _update_settings(self):
        """更新设置"""
        self.settings['show_raw_output'] = self.raw_output_var.get()
        self._save_settings()

    def start_process(self):
        """开始处理用户输入"""
        try:
            query = self.input_text.get("1.0", "end-1c").strip()
            if not query or query == self.input_text.placeholder:
                self.status_var.set("错误: 请输入有效指令")
                return
            
            # 输入验证
            if len(query) > 1000:
                self.status_var.set("错误: 输入过长")
                return
                
            self.status_var.set("处理中...")
            self.progress.start()  # 启动进度条
            self._toggle_ui_state(False)
            
            # 确保有事件循环
            if not hasattr(self, '_loop'):
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
            
            # 创建并运行协程任务
            async def run_async_process():
                try:
                    result = await self._async_process(query)
                    return result
                except Exception as e:
                    return {"error": f"处理失败: {str(e)}"}
            
            # 使用线程安全的协程执行
            self.current_task = asyncio.run_coroutine_threadsafe(
                run_async_process(),
                self._loop
            )
            self.current_task.add_done_callback(self._handle_result)
            
            # 设置超时监控
            self.after(30000, self._check_task_timeout)
        except Exception as e:
            self.status_var.set(f"启动错误: {str(e)}")
            self._toggle_ui_state(True)
            self.progress.stop()

    async def _async_process(self, query: str) -> Dict[str, Any]:
        """异步处理用户查询
        
        Args:
            query: 用户输入的查询字符串
            
        Returns:
            包含处理结果的字典:
            - sanitized: 清理后的命令字符串
            - raw: 原始API响应
            - error: 错误信息(如果有)
        """
        try:
            result = await self.engine.async_generate_command(query)
            if not isinstance(result, dict):
                raise ValueError("无效的API响应格式")
                
            if "sanitized" not in result:
                raise ValueError("API响应缺少sanitized字段")
                
            self.last_command = result["sanitized"]
            return {
                "sanitized": result["sanitized"],
                "raw": result.get("raw"),
                "error": None
            }
        except Exception as e:
            return {
                "sanitized": "",
                "raw": None,
                "error": str(e)
            }

    def _confirm_execution(self, risk: Dict[str, Any], command_data: Dict[str, str]) -> bool:
        """确认执行危险命令"""
        if not risk:
            return True
        
        msg = f"检测到潜在危险操作:\n{command_data['sanitized']}\n\n确定要执行吗？"
        return messagebox.askyesno("危险操作确认", msg)

    def _handle_result(self, future: Future) -> None:
        """处理异步任务结果"""
        try:
            # 停止进度条
            self.progress.stop()
            
            if future.done():
                result = future.result()
                
                # 确保结果不是协程
                if asyncio.iscoroutine(result):
                    self.status_var.set("错误: 无效的异步结果")
                    self._append_output("内部错误: 异步处理失败", -1)
                    return
                
                if result and isinstance(result, dict) and "error" in result:
                    self.status_var.set(f"错误: {result['error']}")
                    self._append_output(f"执行错误: {result['error']}", -1)
                    return
                
                # 验证结果结构
                if not isinstance(result, dict) or "sanitized" not in result:
                    self.status_var.set("错误: 无效的响应格式")
                    self._append_output("内部错误: 无效的响应格式", -1)
                    return
                
                # 获取风险评估
                risk = self.engine.assess_risk(result["sanitized"])
                self._show_command(result["sanitized"], risk['level'])
                
                # 高风险命令额外警告
                if risk['level'] == 'high':
                    self._append_output(
                        f"警告: 高风险命令 - {', '.join(risk['reasons'])}", 
                        1  # 使用1表示警告级别
                    )
                
                self.raw_response = result["raw"]
                if self.raw_output_var.get():
                    self._show_raw_response()
                
                self.status_var.set("就绪")
        except SecurityError as se:
            self.status_var.set(f"安全警告: {se.message}")
            self._append_output(f"安全警告: {se.message}", 1)
        except asyncio.TimeoutError:
            self.status_var.set("错误: 处理超时")
            self._append_output("处理超时，请重试", -1)
        except Exception as e:
            self.status_var.set(f"处理错误: {str(e)}")
            self._append_output(f"处理错误: {str(e)}", -1)
        finally:
            self._toggle_ui_state(True)
            self.progress.stop()
            
            # 清理事件循环
            if hasattr(self, '_loop'):
                self._loop.call_soon_threadsafe(self._loop.stop)

    def _check_task_timeout(self):
        """检查任务是否超时"""
        if hasattr(self, 'current_task') and not self.current_task.done():
            self.status_var.set("错误: 处理超时")
            self._append_output("处理超时，请重试", -1)
            self._toggle_ui_state(True)
            self.progress.stop()

    def _clear_context(self):
        """清除上下文"""
        self.engine.context.clear()
        self.status_var.set("上下文已清除")

    def _show_error(self, message: str):
        """显示错误信息"""
        self.console_text.config(state=tk.NORMAL)
        self.console_text.insert(tk.END, f"错误: {message}\n")
        self.console_text.config(state=tk.DISABLED)
        self.console_text.see(tk.END)

    def _show_command(self, command: str, risk_level: str = 'low'):
        """显示生成的命令(带风险级别)
        
        Args:
            command: 要显示的命令
            risk_level: 风险级别(low/medium/high)
        """
        self.command_text.config(state=tk.NORMAL)
        self.command_text.delete("1.0", tk.END)
        
        # 添加风险指示
        if risk_level == 'high':
            self.command_text.tag_config('risk_high', foreground='red')
            self.command_text.insert("1.0", "⚠️ ", 'risk_high')
        elif risk_level == 'medium':
            self.command_text.tag_config('risk_medium', foreground='orange') 
            self.command_text.insert("1.0", "⚠️ ", 'risk_medium')
            
        self.command_text.insert(tk.END, command)
        self.command_text.config(state=tk.DISABLED)

    def _append_output(self, text: str, exit_code: int = 0):
        """追加输出到控制台"""
        color = "red" if exit_code != 0 else "green"
        
        self.console_text.config(state=tk.NORMAL)
        self.console_text.tag_config(color, foreground=color)
        self.console_text.insert(tk.END, text + "\n", color)
        self.console_text.config(state=tk.DISABLED)
        self.console_text.see(tk.END)

    def _show_raw_response(self):
        """显示原始API响应"""
        if not self.raw_response:
            return
        
        top = tk.Toplevel(self)
        top.title("原始API响应")
        top.geometry("800x600")
        
        text = scrolledtext.ScrolledText(
            top,
            wrap=tk.WORD,
            font=("Consolas", 10)
        )
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, json.dumps(self.raw_response, indent=2))
        text.config(state=tk.DISABLED)

    def _on_model_change(self, event=None):
        """处理模型变更"""
        model = self.model_var.get()
        if model == self.active_model:
            return
        
        try:
            self.engine = CommandEngine(model)
            self.active_model = model
            self.status_var.set(f"已切换到模型: {EnhancedConfig.MODEL_CONFIGS[model]['name']}")
        except Exception as e:
            messagebox.showerror("错误", str(e))
            self.model_var.set(self.active_model)

    def _toggle_ui_state(self, enabled: bool):
        """切换UI状态"""
        state = tk.NORMAL if enabled else tk.DISABLED
        self.generate_btn.config(state=state)
        self.execute_btn.config(state=state)
        self.input_text.config(state=state)

    def stop_process(self):
        """停止当前进程"""
        if hasattr(self.engine, 'terminate_process'):
            self.engine.terminate_process()
            self.status_var.set("进程已停止")

    def _on_generate(self, event=None):
        """生成命令按钮回调"""
        self.start_process()

    def _on_execute(self, event=None):
        """执行命令按钮回调"""
        if not self.last_command:
            self.status_var.set("错误: 请先生成命令")
            return
        
        self.status_var.set("执行中...")
        self._toggle_ui_state(False)
        
        def execute():
            output, exit_code = self.engine.execute(self.last_command)
            return output, exit_code
        
        self.current_task = self.executor.submit(execute)
        self.current_task.add_done_callback(
            lambda f: self._append_output(*f.result())
        )
        self.current_task.add_done_callback(
            lambda _: self._toggle_ui_state(True)
        )
        self.current_task.add_done_callback(
            lambda _: self.status_var.set("就绪")
        )

# ========== 主程序入口 ==========
def setup_logging():
    """配置日志系统"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('app.log'),
            logging.StreamHandler()
        ]
    )

def check_config():
    """检查必要配置"""
    required_vars = set()
    for config in EnhancedConfig.MODEL_CONFIGS.values():
        required_vars.update(config['env_vars'])
    
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise EnvironmentError(f"缺少必需环境变量: {', '.join(missing)}")

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='AI命令行助手')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    parser.add_argument('--model', choices=EnhancedConfig.MODEL_CONFIGS.keys(), 
                       default='moonshot', help='选择AI模型')
    return parser.parse_args()

def main():
    """主程序入口"""
    args = parse_args()
    setup_logging()
    load_dotenv()
    
    try:
        check_config()
        app = ModernUI(default_model=args.model)
        app.mainloop()
    except Exception as e:
        logging.critical(f"应用程序启动失败: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
