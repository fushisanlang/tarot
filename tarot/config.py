"""config.py — Flask 后端配置

所有密码从环境变量读取，默认值仅用于本地开发。
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── MySQL ──────────────────────────────────────────────────────
DB_USER = "tarot"
DB_PASSWORD = os.getenv("DB_PASSWORD", "tarot_pw_2026")
DB_HOST = os.getenv("DB_HOST", "10.0.14.155")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "tarot")
DB_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

# ── Redis ──────────────────────────────────────────────────────
REDIS_HOST = os.getenv("REDIS_HOST", "10.0.14.155")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "tarot_redis_pw_2026")
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# ── Rate Limiting ──────────────────────────────────────────────
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", "10"))

# ── CAPTCHA ────────────────────────────────────────────────────
CAPTCHA_TTL = 300  # 验证码有效期 5 分钟
CAPTCHA_LENGTH = int(os.getenv("CAPTCHA_LENGTH", "4"))  # token 长度

# ── Flask ──────────────────────────────────────────────────────
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5002"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"
