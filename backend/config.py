"""
配置管理（支持环境变量覆盖）
"""
import os
from dotenv import load_dotenv

# 加载 .env 文件（如果存在）
load_dotenv()

# 数据库配置（建议通过环境变量 DB_* 覆盖）
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'database': os.getenv('DB_NAME', 'ENGLISH_1'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'ww123w456')
}

# 当前科目（可动态切换）
CURRENT_SUBJECT = '英语'


def set_current_subject(name: str):
    global CURRENT_SUBJECT
    CURRENT_SUBJECT = name


def get_current_subject() -> str:
    return CURRENT_SUBJECT

# DeepSeek AI 配置
# 可通过 .env 文件或系统环境变量设置：
#   DEEPSEEK_API_KEY=sk-your-key-here
#   DEEPSEEK_API_URL=https://api.deepseek.com/v1/chat/completions
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
DEEPSEEK_API_URL = os.getenv(
    'DEEPSEEK_API_URL',
    'https://api.deepseek.com/v1/chat/completions'
)
