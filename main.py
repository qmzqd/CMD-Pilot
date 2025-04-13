import os
import subprocess
import tempfile
import platform
from openai import OpenAI
from dotenv import load_dotenv
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from concurrent.futures import ThreadPoolExecutor

# 加载环境变量
load_dotenv()

class ModernScrolledText(scrolledtext.ScrolledText):
    """现代化滚动文本框组件"""
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            wrap=tk.WORD,
            font=('Segoe UI', 10),
            padx=12,
            pady=12,
            highlightthickness=0,
            **kwargs
        )
        self.config(
            bg='#F5F5F5',
            fg='#333333',
            insertbackground='#2196F3'
        )

class KimiClient:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("MOONSHOT_API_KEY"),
            base_url="https://api.moonshot.cn/v1"
        )
        self._init_system_prompt()
    
    def _init_system_prompt(self):
        """初始化系统提示词"""
        self.messages = [{
            "role": "system",
            "content": f"""你是由深度求索(DeepSeek)开发的智能助手Kimi，需要帮助用户管理系统并执行命令。当前操作系统：{platform.system()}
            
请严格遵循以下规则：
1. 使用中文简体回复
2. 只返回可直接执行的命令或脚本
3. 禁止包含任何解释说明
4. 确保命令在当前平台有效
5. 多步骤操作使用批处理脚本格式"""
        }]

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
            
            # 上下文轮转机制
            if len(self.messages) > 10:
                self.messages = [self.messages[0]] + self.messages[-8:]
                
            return assistant_message.content.strip()
        except Exception as e:
            raise RuntimeError(f"API请求失败: {str(e)}")

class CommandEngine:
    SAFETY_LEVELS = {
        'destructive': {'keywords': ['rm', 'del', 'shutdown', 'format', 'dd'], 'color': '#EF5350'},
        'privilege': {'keywords': ['sudo', 'chmod', 'chown', 'passwd'], 'color': '#FFA726'},
        'network': {'keywords': ['curl', 'wget', 'ssh', 'scp'], 'color': '#42A5F5'},
        'system': {'keywords': ['reg', 'diskpart', 'service'], 'color': '#AB47BC'}
    }

    def __init__(self):
        self.context = []
        self.history = []
        self.kimi = KimiClient()
        self.os_type = platform.system()
    
    def generate_command(self, user_input):
        """生成带上下文的命令"""
        try:
            context = "\n".join(
                f"[历史{idx}] {item['request']} → {item['command']}" 
                for idx, item in enumerate(self.context[-3:], 1)
            )  # 修复缺少的括号
            
            prompt = f"""用户请求：{user_input}
操作系统：{self.os_type}
历史上下文：
{context or "无历史记录"}

请严格按照以下格式返回：
1. 单条命令直接返回
2. 多步骤操作用批处理语法
3. 不要任何解释和注释"""
            
            response = self.kimi.get_response(prompt)
            return self._sanitize_output(response)
        except Exception as e:
            raise RuntimeError(f"命令生成失败: {str(e)}")
    
    def _sanitize_output(self, text):
        """净化输出内容"""
        clean_text = text.replace('```batch', '').replace('```', '')
        lines = []
        for line in clean_text.split('\n'):
            line = line.strip()
            if line and not line.startswith(('::', 'REM', 'rem', 'echo')):
                lines.append(line)
        return '\n'.join(lines) if len(lines) > 1 else lines[0] if lines else ''

    def execute(self, command):
        """执行命令或脚本"""
        if not command:
            return "无效命令", -1
        
        try:
            if '\n' in command:
                return self._execute_script(command)
            return self._execute_single(command)
        except Exception as e:
            return f"执行异常: {str(e)}", -1

    def _execute_single(self, command):
        """执行单条命令"""
        shell = self.os_type == 'Windows'
        process = subprocess.Popen(
            command,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='gbk' if shell else 'utf-8'
        )
        
        try:
            stdout, stderr = process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            return "命令执行超时（30秒）", -1
        
        output = stdout.strip()
        if process.returncode != 0:
            output += f"\n[错误 {process.returncode}] {stderr.strip()}"
        return output, process.returncode

    def _execute_script(self, script):
        """执行批处理脚本"""
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.bat' if self.os_type == 'Windows' else '.sh',
            delete=False,
            encoding='gbk'
        ) as f:
            f.write(script)
            temp_path = f.name
        
        try:
            process = subprocess.Popen(
                temp_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True
            )
            stdout, stderr = process.communicate(timeout=60)
            output = stdout.strip()
            if process.returncode != 0:
                output += f"\n[错误 {process.returncode}] {stderr.strip()}"
            return output, process.returncode
        finally:
            os.remove(temp_path)

    def analyze_safety(self, command):
        """分析命令安全等级"""
        findings = []
        for category, data in self.SAFETY_LEVELS.items():
            if any(kw in command.lower() for kw in data['keywords']):
                findings.append((category, data['color']))
        return findings

class ModernUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.engine = CommandEngine()
        self.running = False
        self._configure_window()
        self._create_widgets()
        self._setup_style()
        self._bind_shortcuts()
    
    def _configure_window(self):
        """窗口配置"""
        self.title("Kimi 智能系统助手")
        self.geometry("1000x700")
        self.minsize(800, 600)
    
    def _create_widgets(self):
        """创建界面组件"""
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 输入区域
        input_frame = ttk.LabelFrame(main_frame, text=" 输入请求 ")
        input_frame.pack(fill=tk.X, pady=5)
        
        self.input_text = ModernScrolledText(input_frame, height=4)
        self.input_text.pack(fill=tk.BOTH, expand=True)
        
        # 命令显示
        self.cmd_display = ttk.Entry(
            main_frame,
            font=('Consolas', 11),
            foreground='#1E88E5',
            state='readonly'
        )
        self.cmd_display.pack(fill=tk.X, pady=5)
        
        # 控制面板
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=8)
        
        self.btn_run = ttk.Button(
            control_frame,
            text="执行 (Ctrl+Enter)",
            command=self.start_execution,
            style='Accent.TButton'
        )
        self.btn_run.pack(side=tk.LEFT, padx=3)
        
        self.btn_stop = ttk.Button(
            control_frame,
            text="停止 (Esc)",
            command=self.stop_execution,
            state=tk.DISABLED
        )
        self.btn_stop.pack(side=tk.LEFT, padx=3)
        
        self.progress = ttk.Progressbar(
            control_frame,
            mode='indeterminate',
            length=200
        )
        self.progress.pack(side=tk.RIGHT)
        
        # 输出区域
        output_frame = ttk.LabelFrame(main_frame, text=" 执行结果 ")
        output_frame.pack(fill=tk.BOTH, expand=True)
        
        self.output_text = ModernScrolledText(output_frame)
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # 状态栏
        self.status = ttk.Label(
            self,
            text="就绪",
            anchor=tk.W,
            style='Status.TLabel'
        )
        self.status.pack(side=tk.BOTTOM, fill=tk.X, padx=10)
    
    def _setup_style(self):
        """配置界面样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # 自定义颜色方案
        style.configure('.', background='#FFFFFF')
        style.configure('Accent.TButton', 
                       foreground='white', 
                       background='#2196F3',
                       font=('Segoe UI', 10, 'bold'))
        
        style.map('Accent.TButton',
                 background=[('active', '#1976D2'), ('disabled', '#BBDEFB')])
        
        style.configure('Status.TLabel',
                       background='#E3F2FD',
                       foreground='#0D47A1',
                       padding=5,
                       font=('Segoe UI', 9))
        
        style.configure('TLabelFrame', 
                       font=('Segoe UI', 10, 'bold'),
                       foreground='#616161')
    
    def _bind_shortcuts(self):
        """绑定快捷键"""
        self.bind('<Control-Return>', lambda e: self.start_execution())
        self.bind('<Escape>', lambda e: self.stop_execution())
    
    def start_execution(self):
        """启动执行流程"""
        if self.running:
            return
        
        user_input = self.input_text.get('1.0', tk.END).strip()
        if not user_input:
            messagebox.showwarning("输入错误", "请输入有效指令", parent=self)
            return
        
        self.running = True
        self._toggle_controls()
        self.clear_output()
        
        with ThreadPoolExecutor() as executor:
            future = executor.submit(self._process_command, user_input)
            future.add_done_callback(
                lambda f: self.after(0, self._handle_execution_complete)
            )
    
    def _process_command(self, user_input):
        """处理命令流程"""
        try:
            # 生成命令
            command = self.engine.generate_command(user_input)
            self.after(0, lambda: self._update_command_display(command))
            
            # 安全检查
            safety_issues = self.engine.analyze_safety(command)
            if safety_issues and not self._confirm_safety(safety_issues, command):
                self.after(0, lambda: self.append_output("用户取消执行"))
                return
            
            # 执行命令
            output, returncode = self.engine.execute(command)
            self.after(0, lambda: self._display_result(output, returncode))
            
            # 更新上下文
            self.engine.context.append({
                'request': user_input,
                'command': command,
                'result': output
            })
            if len(self.engine.context) > 5:
                self.engine.context = self.engine.context[-5:]
        
        except Exception as e:
            self.after(0, lambda: self.show_error(str(e)))
    
    def _update_command_display(self, command):
        """更新命令显示"""
        self.cmd_display.config(state=tk.NORMAL)
        self.cmd_display.delete(0, tk.END)
        self.cmd_display.insert(0, command)
        self.cmd_display.config(state='readonly')
    
    def _confirm_safety(self, safety_issues, command):
        """安全确认对话框"""
        categories = '\n'.join(
            f"• {cat[0]}" for cat in safety_issues
        )
        return messagebox.askyesno(
            "安全警告",
            f"检测到潜在风险：\n{categories}\n\n即将执行：\n{command}\n\n确认继续？",
            parent=self,
            icon='warning'
        )
    
    def _display_result(self, output, returncode):
        """显示执行结果"""
        tag = 'success' if returncode == 0 else 'error'
        self.append_output(f"退出代码：{returncode}\n{output}", tag)
    
    def append_output(self, text, tag=None):
        """追加输出内容"""
        self.output_text.config(state=tk.NORMAL)
        self.output_text.insert(tk.END, text + '\n' + '─'*80 + '\n\n', tag)
        self.output_text.see(tk.END)
        self.output_text.config(state=tk.DISABLED)
    
    def clear_output(self):
        """清空输出区域"""
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state=tk.DISABLED)
    
    def stop_execution(self):
        """停止当前执行"""
        if self.running:
            self.running = False
            self._toggle_controls()
            self.append_output("操作已中止", 'warning')
    
    def _toggle_controls(self):
        """切换控件状态"""
        state = tk.NORMAL if not self.running else tk.DISABLED
        self.btn_run.config(state=state)
        self.btn_stop.config(state=tk.NORMAL if self.running else tk.DISABLED)
        
        if self.running:
            self.progress.start()
            self.status.config(text="执行中...")
        else:
            self.progress.stop()
            self.status.config(text="就绪")
    
    def _handle_execution_complete(self, future):
        """处理执行完成"""
        try:
            future.result()
        except Exception as e:
            self.show_error(str(e))
        finally:
            self.running = False
            self._toggle_controls()
    
    def show_error(self, message):
        """显示错误信息"""
        messagebox.showerror("系统错误", message, parent=self)
        self.append_output(f"错误：{message}", 'error')

if __name__ == "__main__":
    app = ModernUI()
    app.mainloop()
