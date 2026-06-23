"""
models.py — SQLAlchemy ORM 模型

表:
  readings   — 占卜记录
  rate_limits — IP 日限频记录（MySQL 兜底，主防靠 Redis）
"""

from datetime import date, datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Reading(db.Model):
    """占卜记录"""

    __tablename__ = "readings"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ip = db.Column(db.String(45), nullable=False, index=True, comment="客户端 IP")
    spread_id = db.Column(db.String(64), nullable=False, comment="牌阵 ID")
    spread_name = db.Column(db.String(128), nullable=False, comment="牌阵名称")
    question = db.Column(db.Text, nullable=False, comment="用户问题")
    cards = db.Column(db.JSON, nullable=False, comment="抽取的牌（JSON 数组）")
    response = db.Column(db.Text, nullable=True, comment="AI 完整解读（LONGTEXT）")
    tokens_used = db.Column(db.Integer, nullable=True, comment="消耗 tokens 数")
    duration = db.Column(db.Float, nullable=True, comment="耗时（秒）")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ip": self.ip,
            "spread_id": self.spread_id,
            "spread_name": self.spread_name,
            "question": self.question,
            "cards": self.cards,
            "response": self.response,
            "tokens_used": self.tokens_used,
            "duration": self.duration,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RateLimit(db.Model):
    """IP 每日限频记录（MySQL 兜底，用于持久化统计）"""

    __tablename__ = "rate_limits"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ip = db.Column(db.String(45), nullable=False, comment="客户端 IP")
    date = db.Column(db.Date, nullable=False, default=date.today, comment="日期")
    count = db.Column(db.Integer, nullable=False, default=0, comment="当日已用次数")

    __table_args__ = (
        db.UniqueConstraint("ip", "date", name="uq_ip_date"),
    )
