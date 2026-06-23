"""
ai_reader.py — AI塔罗解读模块

使用 OpenAI SDK 调用 DeepSeek API 进行塔罗牌解读。
支持 streaming 打字机效果。
"""

import os
import time
from typing import Callable, Optional

from dotenv import load_dotenv
from openai import OpenAI


# ── 环境初始化 ────────────────────────────────────────────────

def _resolve_env() -> str:
    """Locate .env file and load it; return the API key."""
    # Try project root (parent of this file's directory)
    this_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.environ.get("DOTENV_PATH"),
        os.path.join(this_dir, "..", ".env"),
        os.path.join(this_dir, ".env"),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            load_dotenv(c, override=True)
            break
    else:
        # Last resort — try loading .env from working dir
        load_dotenv(override=True)

    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        raise ValueError(
            "DEEPSEEK_API_KEY not found. Set it in .env or export it."
        )
    return key


# ── 系统提示词（人设 + 固定块） ─────────────────────────────

SYSTEM_PROMPT = """你是「知我」——一位深谙塔罗智慧的高阶解读师。你拥有对 78 张塔罗牌的深刻理解，擅长将古老的符号体系与提问者的现实生活联结起来。

你的风格：温和而深刻、共情而不迎合、有洞察力而不武断。你既能看到牌面背后的原型能量，也能将其落地为具体的行动指引。

解读原则：
1. 始终从提问者的问题出发，不泛泛而谈
2. 对每张牌给出具体的象征解读，并联系牌阵位置的含义
3. 注意正逆位带来的能量差异——逆位不是"坏"，而是需要关注的内在卡点
4. 关注牌与牌之间的呼应或冲突，形成整合性的解读
5. 结尾给出可操作的建议或思考方向
6. 全程使用中文，语气温暖、专业、有共情力

重要规则——这是**一次性完整解读**：
- 用户只会提交一次问题，不会与你对话，没有后续回合
- 你必须给出**完整的、自成一体的**解读，不能反问、不能追问、不能请用户补充信息
- 不要以问句结尾，不要出现"你觉得呢""不妨思考一下""你是否也有同感"等邀请回应的语句
- 直接输出完整的解读内容，包含对每张牌的解读、整体分析、以及结论与建议
- 解读必须有始有终，读完后自然结束"""


def _build_spread_overview(reading_result: dict) -> str:
    """Build the spread + card context block (cache-friendly, deterministic)."""
    spread_name = reading_result.get("spread_name", "")
    question = reading_result.get("question", "")
    cards = reading_result.get("cards", [])

    lines = [f"## 牌阵：{spread_name}", f"## 问题：{question}", ""]

    for card in cards:
        pos = card.get("position", "")
        name = card.get("name", "")
        ctype = card.get("type", "")
        suit = card.get("suit") or ""
        orientation = "逆位" if card.get("isReversed") else "正位"
        meaning = card.get("meaning", "")

        line_parts = [
            f"### {pos}",
            f"牌：{name}（{orientation}）",
        ]
        if suit:
            line_parts.append(f"花色：{suit} / {ctype}")
        line_parts.append(f"核心含义：{meaning}")
        lines.append(" | ".join(line_parts))
        lines.append("")

    return "\n".join(lines)


def build_prompt(reading_result: dict) -> tuple[str, str]:
    """
    构建 system prompt + user prompt。

    Returns
    -------
    (system, user) — 两个字符串。
    固定块（system prompt + 牌阵说明）在前，用户问题在后。
    """
    spread_overview = _build_spread_overview(reading_result)
    user_prompt = (
        f"以下是我的塔罗牌面，请为我做一次完整的解读：\n\n"
        f"{spread_overview}\n"
        f"我的问题是「{reading_result.get('question', '')}」。"
        f"请直接输出完整解读，包含每张牌的含义、整体分析、以及给我的建议。"
        f"不要反问、不要追问，这是一次性解读。"
    )
    return SYSTEM_PROMPT, user_prompt


# ── AI 解读 ───────────────────────────────────────────────────

class AIReader:
    """AI 塔罗解读器，封装 DeepSeek API 调用。"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self._api_key = api_key or _resolve_env()
        self._base_url = base_url or "https://api.deepseek.com"
        self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)

    # ── 配置 ──────────────────────────────────────────────

    @staticmethod
    def _max_tokens_for_card_count(n: int) -> int:
        """三档 max_tokens：小牌阵(1-3张)=800, 中(4-7张)=1200, 大(8+)=2000"""
        if n <= 3:
            return 800
        elif n <= 7:
            return 1200
        return 2000

    # ── 解读 ──────────────────────────────────────────────

    def get_reading(
        self,
        reading_result: dict,
        question: Optional[str] = None,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        获得 AI 塔罗解读。

        Parameters
        ----------
        reading_result : dict
            来自 TarotEngine.draw_spread() 的结构化结果。
        question : str, optional
            覆盖问题。如不提供，使用 reading_result 中的 question。
        on_token : Callable[[str], None], optional
            流式回调，每次收到 token 时调用（打字机效果）。

        Returns
        -------
        str
            完整解读文本。
        """
        if question:
            reading_result = dict(reading_result)
            reading_result["question"] = question

        system, user = build_prompt(reading_result)

        card_count = len(reading_result.get("cards", []))
        max_tokens = self._max_tokens_for_card_count(card_count)

        start_time = time.monotonic()

        response = self._client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            stream=True,
            max_tokens=max_tokens,
            temperature=0.7,
        )

        full_text_parts: list[str] = []

        for chunk in response:
            if chunk.choices:
                delta = chunk.choices[0].delta
                content = delta.content or ""
                if content:
                    full_text_parts.append(content)
                    if on_token:
                        on_token(content)

        elapsed = time.monotonic() - start_time
        full_text = "".join(full_text_parts)

        # Attach metadata as private attribute (not serialized by default)
        object.__setattr__(full_text, "_meta", {
            "elapsed_seconds": round(elapsed, 2),
            "card_count": card_count,
            "max_tokens": max_tokens,
            "total_tokens": None,  # not available in streaming
        })

        return full_text
