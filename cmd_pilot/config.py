from typing import Dict, List, TypedDict, Any

class ModelConfig(TypedDict):
    base_url: str
    model: str
    name: str
    env_vars: List[str]
    api_type: str

class SafetyRule(TypedDict):
    patterns: List[str]
    color: str

class ThemeConfig(TypedDict):
    bg: str
    text: str
    text_secondary: str
    primary: str
    success: str
    warning: str
    error: str
    font_family: str
    font_size: int

class UIStyle(TypedDict):
    TButton: Dict[str, Any]
    TCombobox: Dict[str, Any]

MODEL_CONFIGS = {
    "moonshot": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "name": "Moonshot AI",
        "env_vars": ["MOONSHOT_API_KEY"],
        "api_type": "openai"
    },
    "spark": {
        "base_url": "https://spark-api.xf-yun.com/v1.1",
        "model": "general",
        "name": "讯飞星火",
        "env_vars": ["SPARK_API_KEY"],
        "api_type": "spark"
    }
}

UI_THEME = {
    "bg": "#f5f5f5",
    "text": "#333333",
    "text_secondary": "#666666",
    "primary": "#4a6baf",
    "success": "#5cb85c",
    "warning": "#f0ad4e",
    "error": "#d9534f",
    "font_family": "Microsoft YaHei",
    "font_size": 12
}

UI_STYLE = {
    "TButton": {
        "padding": (10, 5),
        "borderwidth": 1,
        "relief": "raised"
    },
    "TCombobox": {
        "padding": (5, 2),
        "borderwidth": 1
    }
}

DEFAULT_SETTINGS = {
    "show_raw_output": False,
    "max_risk_level": "medium"
}

ALLOWED_COMMANDS = ["ls", "cd", "pwd", "cat", "grep", "find", "echo"]
