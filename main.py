import os
import subprocess
import sys
import threading
import tempfile
from openai import OpenAI
from dotenv import load_dotenv
from tkinter import *
from tkinter.scrolledtext import ScrolledText
from tkinter import messagebox, ttk, Menu

# 加载环境变量
load_dotenv()

class KimiClient:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("MOONSHOT_API_KEY"),
            base_url="https://api.moonshot.cn/v1",
        )
        self.messages = [
            {
                "role": "system", 
                "content": """你是由深度求索(DeepSeek)公司开发的智能助手Kimi，需要帮助用户管理系统并执行命令。
遵守规则：
1. 使用中文简体字回复
2. 只返回可直接执行的命令或批处理脚本内容
3. 绝对不要包含任何解释说明
4. 确保命令在当前平台有效
5. 多步操作请用批处理脚本格式"""
            }
        ]
    
    def get_response(self, user_prompt, max_tokens=1000):
        """获取带上下文的响应"""
        try:
            self.messages.append({"role": "user", "content": user_prompt})
            
            completion = self.client.chat.completions.create(
                model="moonshot-v1-8k",
                messages=self.messages,
                temperature=0.3,
                max_tokens=max_tokens
            )
            
            assistant_message = completion.choices[0].message
            self.messages.append(assistant_message)
            
            if len(self.messages) > 12:
                self.messages = [self.messages[0]] + self.messages[-10:]
                
            return assistant_message.content.strip()
        except Exception as e:
            raise RuntimeError(f"API错误: {str(e)}")

class CommandExecutor:
    def __init__(self):
        self.platform = "Windows" if sys.platform.startswith('win') else "Linux"
        self.kimi = KimiClient()
        self.context = []
        self.dangerous_commands = {
            'destructive': ['rm', 'del', 'shutdown', 'format', 'dd', 'mkfs'],
            'sensitive': ['chmod', 'chown', 'sudo', 'passwd', 'usermod'],
            'network': ['wget', 'curl', 'ssh', 'scp']
        }

    def get_ai_command(self, user_request):
        """获取带上下文的命令"""
        try:
            context_info = "\n".join(
                [f"[历史{idx+1}] {ctx['request']} -> 执行: {ctx['command']}" 
                for idx, ctx in enumerate(self.context[-3:])]
            )
            
            prompt = f"""你是一位专业的{self.platform}系统管理员，精通这个系统的各种命令，根据用户需求生成命令行指令。
生成规则：
1. 必须只返回可直接执行的命令或批处理脚本内容
2. 绝对不要包含任何解释说明
3. 确保命令在当前平台有效
4. 如果是多步操作，请使用批处理文本格式
5. 不要使用自然语言描述步骤

当前系统：{self.platform}
历史上下文：
{context_info if context_info else "无历史记录"}
用户请求：{user_request}"""
            
            command = self.kimi.get_response(prompt)
            return self._clean_command(command)
        except Exception as e:
            raise RuntimeError(f"命令生成失败: {str(e)}")

    def _clean_command(self, command):
        """增强型命令清理"""
        # 移除代码块标记和注释
        cleaned = command.replace('```batch', '').replace('```', '') \
                        .replace('@echo off', '').replace('@echo on', '')
        
        # 提取第一个代码块内容（如果有）
        if '```' in cleaned:
            cleaned = cleaned.split('```')[1]
        
        # 处理每行内容
        lines = []
        for line in cleaned.split('\n'):
            line = line.strip()
            # 跳过空行和注释
            if not line or line.startswith(('::', 'REM ', 'rem ', 'echo ')):
                continue
            # 保留有效命令
            if line:
                lines.append(line)
        return '\n'.join(lines) if len(lines) > 1 else lines[0] if lines else ""

    def execute_command(self, command):
        """改进的命令执行方法"""
        if not command:
            return "无效命令"

        try:
            # 如果是多行命令，保存为批处理文件执行
            if '\n' in command:
                return self._execute_batch_script(command)
            
            shell = sys.platform.startswith('win')
            process = subprocess.Popen(
                command,
                shell=shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True
            )
            
            try:
                stdout, stderr = process.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                return f"命令执行超时（30秒）\n已捕获输出：\n{stdout}\n{stderr}"

            output = stdout.strip()
            if process.returncode != 0:
                error_msg = stderr.strip() or "未知错误"
                output += f"\n[错误代码 {process.returncode}] {error_msg}"
            return output
        except Exception as e:
            return f"执行异常: {str(e)}"

    def _execute_batch_script(self, script_content):
        """执行批处理脚本"""
        try:
            # 创建临时批处理文件
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.bat',
                encoding='gbk',
                delete=False
            ) as f:
                f.write("@echo off\n")
                f.write(script_content)
                temp_path = f.name
            
            # 执行批处理文件
            process = subprocess.Popen(
                temp_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True
            )
            
            try:
                stdout, stderr = process.communicate(timeout=60)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

            output = stdout.strip()
            if process.returncode != 0:
                error_msg = stderr.strip() or "未知错误"
                output += f"\n[错误代码 {process.returncode}] {error_msg}"
            return output
        except Exception as e:
            return f"批处理执行失败: {str(e)}"
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass

    def check_danger_level(self, command):
        """检查危险等级"""
        cmd_lower = command.lower()
        danger_info = []
        for category, keywords in self.dangerous_commands.items():
            if any(kw in cmd_lower for kw in keywords):
                danger_info.append(category)
        return danger_info

    def analyze_result(self, user_request, output):
        """上下文感知的结果分析"""
        try:
            context_info = "\n".join(
                [f"[历史{idx+1}] {ctx['request']} -> 结果: {ctx['result'][:100]}"
                for idx, ctx in enumerate(self.context[-2:])]
            )
            
            prompt = f"""系统平台：{self.platform}
历史结果：
{context_info if context_info else "无历史记录"}
当前请求：{user_request}
执行结果：{output}"""
            
            return self.kimi.get_response(prompt)
        except Exception as e:
            return f"分析失败: {str(e)}\n原始输出：\n{output}"

    def update_context(self, user_request, command, result):
        """更新上下文"""
        self.context.append({
            "request": user_request,
            "command": command,
            "result": result
        })
        if len(self.context) > 5:
            self.context = self.context[-5:]

class Application(Tk):
    def __init__(self):
        super().__init__()
        self._apply_theme()
        self.executor = CommandExecutor()
        self.title("智能系统助手 - Kimi")
        self.geometry("900x650")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._setup_ui()
        self._setup_menu()
        self.running = False

    def _apply_theme(self):
        """应用主题样式"""
        try:
            from ttkthemes import ThemedStyle
            style = ThemedStyle(self)
            style.set_theme("arc")
        except ImportError:
            pass

    def _setup_ui(self):
        """初始化用户界面"""
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=BOTH, expand=True)

        # 输入区域
        input_frame = ttk.LabelFrame(main_frame, text=" 输入请求 ", padding=10)
        input_frame.pack(fill=X, pady=5)
        
        self.input_txt = ScrolledText(
            input_frame, 
            height=4, 
            wrap=WORD,
            font=('微软雅黑', 10),
            padx=8,
            pady=8
        )
        self.input_txt.pack(fill=BOTH, expand=True)
        self.input_txt.bind("<Return>", lambda e: "break")

        # 控制面板
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=X, pady=8)

        self.btn_group = ttk.Frame(control_frame)
        self.btn_group.pack(side=LEFT)
        
        self.submit_btn = ttk.Button(
            self.btn_group,
            text="执行 (Ctrl+Enter)",
            command=self.start_execution,
            style="Accent.TButton"
        )
        self.submit_btn.pack(side=LEFT, padx=3)

        self.stop_btn = ttk.Button(
            self.btn_group,
            text="停止 (Esc)",
            command=self.stop_execution,
            state=DISABLED
        )
        self.stop_btn.pack(side=LEFT, padx=3)

        self.context_btn = ttk.Button(
            self.btn_group,
            text="查看上下文",
            command=self.show_context
        )
        self.context_btn.pack(side=LEFT, padx=3)

        # 进度条
        self.progress = ttk.Progressbar(
            control_frame,
            mode='indeterminate',
            length=220
        )
        self.progress.pack(side=RIGHT)

        # 命令显示
        self.cmd_display = ttk.Entry(
            main_frame,
            state='readonly',
            font=('Consolas', 11),
            foreground='#1E88E5'
        )
        self.cmd_display.pack(fill=X, pady=5)

        # 输出区域
        output_frame = ttk.LabelFrame(main_frame, text=" 执行结果 ", padding=10)
        output_frame.pack(fill=BOTH, expand=True)

        self.output_txt = ScrolledText(
            output_frame,
            wrap=WORD,
            font=('Consolas', 10),
            state='disabled',
            padx=8,
            pady=8
        )
        self.output_txt.pack(fill=BOTH, expand=True)

        # 快捷键
        self.bind("<Control-Return>", lambda e: self.start_execution())
        self.bind("<Escape>", lambda e: self.stop_execution())

    def _setup_menu(self):
        """设置右键菜单"""
        self.context_menu = Menu(self, tearoff=0)
        self.context_menu.add_command(
            label="清除历史",
            command=self.clear_context
        )
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="退出程序",
            command=self.destroy
        )
        self.bind("<Button-3>", self._show_context_menu)

    def _show_context_menu(self, event):
        """显示右键菜单"""
        self.context_menu.post(event.x_root, event.y_root)

    def start_execution(self, event=None):
        """开始执行"""
        if self.running:
            return
            
        user_input = self.input_txt.get("1.0", END).strip()
        if not user_input:
            messagebox.showwarning("输入错误", "请输入有效请求内容", parent=self)
            return

        self.running = True
        self._toggle_controls()
        self.clear_output()
        threading.Thread(
            target=self._process_request,
            args=(user_input,),
            daemon=True
        ).start()

    def stop_execution(self, event=None):
        """停止执行"""
        if self.running:
            self.running = False
            self._toggle_controls()
            self.append_output("操作已由用户终止")

    def _toggle_controls(self):
        """切换控件状态"""
        state = 'disabled' if self.running else 'normal'
        self.submit_btn.config(state=state)
        self.stop_btn.config(state='normal' if self.running else 'disabled')
        self.progress.start(10) if self.running else self.progress.stop()

    def _process_request(self, user_input):
        """处理请求流程"""
        try:
            # 生成命令
            command = self.executor.get_ai_command(user_input)
            self.after(0, lambda: self._update_command_display(command))
            
            # 危险检查
            danger_types = self.executor.check_danger_level(command)
            if danger_types:
                if not self.after(0, lambda: self._confirm_dangerous(command, danger_types)):
                    self.after(0, lambda: self.append_output("用户取消执行危险命令"))
                    return

            # 文件操作二次确认
            if any(cmd in command.lower() for cmd in ['del ', 'rm ', 'format']):
                if not self.after(0, lambda: self._confirm_file_operation()):
                    self.after(0, lambda: self.append_output("用户取消文件操作"))
                    return

            # 执行命令
            result = self.executor.execute_command(command)
            self.after(0, lambda: self.append_output(f"✅ 执行结果:\n{result}"))

            # 分析结果
            analysis = self.executor.analyze_result(user_input, result)
            self.after(0, lambda: self.append_output(f"\n📊 分析报告:\n{analysis}"))
            
            # 更新上下文
            self.executor.update_context(user_input, command, result)

        except Exception as e:
            self.after(0, lambda: self.show_error(f"处理错误: {str(e)}"))
        finally:
            self.running = False
            self.after(0, self._toggle_controls)

    def _update_command_display(self, command):
        """更新命令显示"""
        self.cmd_display.config(state='normal')
        self.cmd_display.delete(0, END)
        self.cmd_display.insert(0, command)
        self.cmd_display.config(state='readonly')

    def append_output(self, text):
        """追加输出内容"""
        self.output_txt.config(state='normal')
        self.output_txt.insert(END, text + "\n" + "━"*60 + "\n\n")
        self.output_txt.see(END)
        self.output_txt.config(state='disabled')

    def clear_output(self):
        """清空输出"""
        self.output_txt.config(state='normal')
        self.output_txt.delete(1.0, END)
        self.output_txt.config(state='disabled')

    def _confirm_dangerous(self, command, danger_types):
        """危险命令确认对话框"""
        category_mapping = {
            'destructive': '🛑 破坏性操作（可能造成数据丢失）',
            'sensitive': '🔑 权限相关操作（可能影响系统安全）',
            'network': '🌐 网络相关操作（可能涉及外部连接）'
        }
        
        categories = "\n".join(
            [category_mapping.get(t, t) for t in danger_types]
        )
        
        return messagebox.askyesno(
            "高级安全警告",
            f"检测到以下类型危险命令：\n\n{categories}\n\n"
            f"即将执行的命令：\n{command}\n\n"
            "是否确认继续执行？\n"
            "（建议确认完全理解命令作用后再继续）",
            parent=self,
            icon='warning'
        )

    def _confirm_file_operation(self):
        """文件操作二次确认"""
        return messagebox.askyesno(
            "文件操作确认",
            "即将执行包含文件删除/修改的操作\n是否确认继续？",
            parent=self,
            icon='warning'
        )

    def show_context(self):
        """显示上下文窗口"""
        context_win = Toplevel(self)
        context_win.title("操作上下文")
        
        text_area = ScrolledText(
            context_win,
            wrap=WORD,
            font=('Consolas', 9),
            padx=10,
            pady=10
        )
        text_area.pack(fill=BOTH, expand=True)
        
        context_text = "\n\n".join(
            [f"操作 {idx+1}:\n• 请求: {ctx['request']}\n• 命令: {ctx['command']}\n• 结果: {ctx['result'][:200]}"
             for idx, ctx in enumerate(self.executor.context)]
        ) or "暂无上下文记录"
        
        text_area.insert(END, "最近5条操作上下文：\n\n" + context_text)
        text_area.config(state='disabled')

    def clear_context(self):
        """清除上下文"""
        self.executor.context.clear()
        messagebox.showinfo("提示", "已清除所有操作上下文", parent=self)

    def show_error(self, message):
        """显示错误信息"""
        messagebox.showerror("错误", message, parent=self)

    def on_close(self):
        """关闭窗口事件"""
        if self.running and not messagebox.askokcancel(
            "确认退出", 
            "当前有任务正在执行，确定要退出吗？",
            parent=self
        ):
            return
        self.destroy()

if __name__ == "__main__":
    app = Application()
    app.mainloop()