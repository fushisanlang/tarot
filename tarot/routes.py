"""routes.py — Flask API 路由

GET  /api/spreads       — 返回所有牌阵列表
POST /api/reading       — 执行占卜，SSE 流式输出
"""

import json
import os
import time
import random
import secrets
from datetime import date
from functools import wraps

import redis as redis_lib
from dotenv import load_dotenv
from flask import Blueprint, Response, jsonify, request, current_app

from tarot.config import (
    DAILY_LIMIT, REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB,
    CAPTCHA_TTL, CAPTCHA_LENGTH,
)
from tarot.ai_reader import AIReader, build_prompt
from tarot.models import Reading, RateLimit, db
from tarot.tarot_engine import TarotEngine

# ── 模块加载时一次载入 .env ────────────────────────────────────
_load_dotenv_done = False
def _ensure_env():
    global _load_dotenv_done
    if not _load_dotenv_done:
        load_dotenv(override=True)
        _load_dotenv_done = True

# ── Blueprint ──────────────────────────────────────────────────
api = Blueprint("api", __name__, url_prefix="/api")

# ── 首页 ──────────────────────────────────────────────────────
from flask import send_from_directory
page = Blueprint("page", __name__)

@page.route("/")
def index():
    return send_from_directory(current_app.static_folder, "index.html")

@page.route("/static/<path:filename>")
def static_files(filename):
    """Serve static files — needed because gunicorn doesn't serve Flask's built-in static."""
    return send_from_directory(current_app.static_folder, filename)

# ── Redis 连接（懒加载） ──────────────────────────────────────
def _get_redis():
    if "redis_client" not in current_app.extensions:
        pool = redis_lib.ConnectionPool(
            host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD,
            db=REDIS_DB, decode_responses=True,
        )
        current_app.extensions["redis_client"] = redis_lib.Redis(connection_pool=pool)
    return current_app.extensions["redis_client"]

# ── 限频装饰器 ────────────────────────────────────────────────
def rate_limit(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        ip = _get_client_ip()
        today_str = date.today().isoformat()
        redis_key = f"rate_limit:{ip}:{today_str}"
        r = _get_redis()
        try:
            current_count = r.get(redis_key)
            if current_count is None:
                r.setex(redis_key, 86400, 1)
            else:
                current_count = int(current_count)
                if current_count >= DAILY_LIMIT:
                    return jsonify({"error": "今日次数已用完", "limit": DAILY_LIMIT}), 429
                r.incr(redis_key)
        except redis_lib.RedisError:
            current_app.logger.warning("Redis 不可用，降级到 MySQL 限频")
            try:
                rl = RateLimit.query.filter_by(ip=ip, date=date.today()).first()
                if rl is None:
                    rl = RateLimit(ip=ip, date=date.today(), count=0)
                    db.session.add(rl)
                if rl.count >= DAILY_LIMIT:
                    return jsonify({"error": "今日次数已用完", "limit": DAILY_LIMIT}), 429
                rl.count += 1
                db.session.commit()
            except Exception as e:
                current_app.logger.error(f"MySQL 限频降级失败: {e}")
        return f(*args, **kwargs)
    return decorated

# ── 获取客户端IP ──────────────────────────────────────────────
def _get_client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"


# ── 验证码生成 ────────────────────────────────────────────────
def _generate_captcha() -> tuple[str, str, int]:
    """Return (token, problem, answer)."""
    a = random.randint(1, 20)
    b = random.randint(1, 20)
    if random.choice([True, False]):
        problem = f"{a} + {b} = ?"
        answer = a + b
    else:
        if a < b:
            a, b = b, a
        problem = f"{a} - {b} = ?"
        answer = a - b
    token = secrets.token_hex(CAPTCHA_LENGTH)
    return token, problem, answer


@api.route("/captcha", methods=["GET"])
def get_captcha():
    """生成数学验证码，答案存 Redis（5 分钟有效）。"""
    token, problem, answer = _generate_captcha()
    try:
        r = _get_redis()
        r.setex(f"captcha:{token}", CAPTCHA_TTL, answer)
    except redis_lib.RedisError:
        # Redis 不可用时跳过验证码
        return jsonify({"token": "", "problem": ""})
    return jsonify({"token": token, "problem": problem})

# ── 路由：获取所有牌阵 ────────────────────────────────────────
@api.route("/spreads", methods=["GET"])
def get_spreads():
    engine = TarotEngine()
    spreads = engine.get_all_spreads()
    return jsonify({"spreads": spreads})

# ── 路由：执行占卜（SSE 流式输出） ──────────────────────────
@api.route("/reading", methods=["POST"])
@rate_limit
def create_reading():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请求体必须是 JSON"}), 400

    spread_id = data.get("spread_id", "").strip()
    question = data.get("question", "").strip()

    if not spread_id:
        return jsonify({"error": "spread_id 不能为空"}), 400
    if not question:
        return jsonify({"error": "question 不能为空"}), 400
    if len(question) > 500:
        return jsonify({"error": "问题长度不能超过 500 字"}), 400

    # ── 验证码校验 ──
    captcha_token = data.get("captcha_token", "").strip()
    captcha_answer = data.get("captcha_answer", "")
    if captcha_token:
        try:
            r = _get_redis()
            key = f"captcha:{captcha_token}"
            stored = r.get(key)
            if stored is None:
                return jsonify({"error": "验证码已过期，请刷新后重试"}), 400
            r.delete(key)
            if str(stored) != str(captcha_answer):
                return jsonify({"error": "验证码错误"}), 400
        except redis_lib.RedisError:
            pass  # Redis 不可用时跳过
    else:
        # Redis 可用时必须验证
        try:
            r = _get_redis()
            if r.ping():
                return jsonify({"error": "请先完成验证"}), 400
        except redis_lib.RedisError:
            pass  # Redis 不可用时跳过

    # ── 抽牌 ──
    engine = TarotEngine()
    try:
        reading_result = engine.draw_spread(spread_id, question)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    cards_data = reading_result.get("cards", [])
    spread_name = reading_result.get("spread_name", spread_id)

    # ── SSE 生成器 ──
    client_ip = _get_client_ip()

    def generate():
        _ensure_env()
        ip = client_ip
        duration = None
        full_response_text = ""
        reading_id = None
        start_time = time.time()

        # 第一步：立即发送牌面数据（先展示卡片，再慢慢读心）
        yield f"data: {json.dumps({'cards': cards_data, 'spread_name': spread_name}, ensure_ascii=False)}\n\n"

        try:
            api_key = os.environ.get("DEEPSEEK_API_KEY", "")
            if not api_key:
                yield f"data: {json.dumps({'token': 'API 密钥未配置'}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'done': True, 'reading_id': None}, ensure_ascii=False)}\n\n"
                return

            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
            system, user = build_prompt(reading_result)
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                stream=True,
                max_tokens=AIReader._max_tokens_for_card_count(len(cards_data)),
                temperature=0.7,
            )
            for chunk in response:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    content = delta.content or ""
                    if content:
                        full_response_text += content
                        yield f"data: {json.dumps({'token': content}, ensure_ascii=False)}\n\n"
            duration = time.time() - start_time
        except Exception as e:
            current_app.logger.error(f"AI 解读出错: {e}")
            yield f"data: {json.dumps({'token': '（AI 解读暂不可用，请稍后再试）'}, ensure_ascii=False)}\n\n"
            duration = time.time() - start_time

        # ── 保存记录 ──
        try:
            from tarot.app import create_app as _ca
            _tmp_app = _ca()
            with _tmp_app.app_context():
                reading = Reading(
                    ip=ip, spread_id=spread_id, spread_name=spread_name,
                    question=question, cards=cards_data, response=full_response_text or None,
                    tokens_used=None, duration=round(duration, 2) if duration else None,
                )
                db.session.add(reading)
                db.session.commit()
                reading_id = reading.id
        except Exception as e:
            import logging
            try:
                current_app.logger.error(f"保存占卜记录失败: {e}")
            except RuntimeError:
                logging.error(f"保存占卜记录失败（无应用上下文）: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass

        yield f"data: {json.dumps({'done': True, 'reading_id': reading_id}, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
