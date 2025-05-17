# 智能命令助手

一个基于AI的命令行工具生成器，支持多种大模型API。

## 功能特性

- 支持Moonshot、讯飞星火等多种AI模型
- 自动生成安全可靠的系统命令
- 危险命令风险提示
- 简洁美观的图形界面
- 智能命令生成引擎（支持上下文理解）
- 多轮对话记忆功能

## 环境配置

1. 安装Python 3.8+
2. 安装依赖包（在命令行中执行以下命令）：
   
   pip install -r requirements.txt
3. 创建.env文件并配置API密钥：
   ```
   # Moonshot配置
   MOONSHOT_API_KEY=your_api_key

   # 讯飞星火配置
   XFYUN_APPID=your_appid
   XFYUN_API_KEY=your_api_key
   XFYUN_API_SECRET=your_api_secret
   ```

## 支持的AI模型接口

- OpenAI API
- 讯飞星火API (Spark)
- Kimi (Moonshot)

## 使用说明

1. 运行程序：
   ```bash
   python main.py
   ```
2. 在输入框描述您想执行的命令（支持多轮对话）
3. 系统会自动维护对话上下文
4. 点击"生成并执行"按钮或按Ctrl+Enter
5. 查看生成的命令和执行结果

## 技术实现

- 采用聊天式API格式（role/content结构）
- 包含系统消息定义AI行为规范
- 支持上下文历史集成
- 完善的错误处理机制

## 注意事项

- 请勿泄露.env文件中的API密钥
- 执行危险命令前请确认风险提示
- 不同模型可能需要不同的API权限
- API调用失败时会自动进行错误处理
