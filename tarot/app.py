"""
app.py — Flask 应用入口

创建 Flask 应用，注册蓝图，初始化数据库。
"""

import os
import sys

# 将项目根目录加入 sys.path，确保可以 import tarot
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from flask import Flask
from flask_cors import CORS

from tarot.config import DB_URI, FLASK_DEBUG, FLASK_HOST, FLASK_PORT
from tarot.models import db
from tarot.routes import api, page


def create_app() -> Flask:
    """创建并配置 Flask 应用。"""
    _static_path = os.path.join(os.path.dirname(__file__), "..", "static")
    app = Flask(__name__, static_folder=_static_path, static_url_path="/static")

    # ── 配置 ──
    app.config["SQLALCHEMY_DATABASE_URI"] = DB_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }

    # ── 扩展 ──
    CORS(app)
    db.init_app(app)

    # ── 蓝图 ──
    app.register_blueprint(api)
    app.register_blueprint(page)

    # ── 创建表 ──
    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
