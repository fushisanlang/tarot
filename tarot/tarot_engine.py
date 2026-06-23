"""
tarot_engine.py — 塔罗抽牌引擎

负责加载塔罗数据、洗牌、按牌阵抽牌。
"""

import json
import random
import time
import os
from typing import Any, Optional


def _find_data_file() -> str:
    """Locate tarot-data.json relative to this file or via an env var."""
    env_path = os.environ.get("TAROT_DATA_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    # Relative to this file:  ../data/tarot-data.json
    this_dir = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(this_dir, "..", "data", "tarot-data.json")
    if os.path.isfile(candidate):
        return os.path.normpath(candidate)

    # Fallback: project-root / data / tarot-data.json
    root = os.path.abspath(os.path.join(this_dir, ".."))
    candidate2 = os.path.join(root, "data", "tarot-data.json")
    if os.path.isfile(candidate2):
        return candidate2

    raise FileNotFoundError(
        f"Cannot locate tarot-data.json. Checked:\n"
        f"  env TAROT_DATA_PATH\n"
        f"  {candidate}\n"
        f"  {candidate2}"
    )


class TarotEngine:
    """塔罗抽牌引擎 —— 加载数据、洗牌、按牌阵抽牌。"""

    def __init__(self, data_path: Optional[str] = None):
        self._data_path = data_path or _find_data_file()
        self._data: dict = {}
        self._major_cards: list = []
        self._minor_cards: list = []
        self._pool: list = []  # combined full deck
        self._spreads: dict = {}
        self._load_data()

    # ── 数据加载 ──────────────────────────────────────────────

    def _load_data(self) -> None:
        with open(self._data_path, "r", encoding="utf-8") as f:
            self._data = json.load(f)

        self._major_cards = self._data.get("cards", [])
        self._minor_cards = self._data.get("cards_minor", [])
        self._spreads = self._data.get("spreads", {})
        self._rebuild_pool()

    def reload(self) -> None:
        """Re-read the JSON file from disk (useful after file updates)."""
        self._load_data()

    def _rebuild_pool(self) -> None:
        """Combine major + minor into the full drawing pool."""
        self._pool = list(self._major_cards + self._minor_cards)

    # ── 洗牌 ──────────────────────────────────────────────────

    def shuffle_deck(self) -> list[dict]:
        """Fisher-Yates shuffle of the internal pool. Returns the shuffled list."""
        cards = self._pool[:]  # copy
        for i in range(len(cards) - 1, 0, -1):
            j = random.randint(0, i)
            cards[i], cards[j] = cards[j], cards[i]
        return cards

    # ── 获取信息 ──────────────────────────────────────────────

    def get_all_spreads(self) -> list[dict]:
        """Return structured list of all spreads."""
        result = []
        for sid, s in self._spreads.items():
            result.append(
                {
                    "id": sid,
                    "name": s.get("name", ""),
                    "description": s.get("description", ""),
                    "cardCount": s.get("cardCount", 0),
                    "positions": s.get("positions", []),
                    "defaultQuestions": s.get("defaultQuestions", []),
                }
            )
        return result

    def get_spread(self, spread_id: str) -> Optional[dict]:
        """Return a single spread definition or None."""
        raw = self._spreads.get(spread_id)
        if raw is None:
            return None
        return {
            "id": spread_id,
            "name": raw.get("name", ""),
            "description": raw.get("description", ""),
            "cardCount": raw.get("cardCount", 0),
            "positions": raw.get("positions", []),
            "defaultQuestions": raw.get("defaultQuestions", []),
        }

    # ── 抽牌 ──────────────────────────────────────────────────

    def draw_spread(
        self,
        spread_id: str,
        question: Optional[str] = None,
    ) -> dict:
        """
        按牌阵抽牌，返回完整结构化的读取结果。

        Parameters
        ----------
        spread_id : str
            牌阵 ID（如 'three', 'love', 'celtic' 等）。
        question : str, optional
            用户的问题。如未提供，使用牌阵的第一个 defaultQuestion。

        Returns
        -------
        dict
            格式：
            {
                "spread_id": ...,
                "spread_name": ...,
                "question": ...,
                "cards": [
                    {"number": ..., "name": ..., "type": ..., "suit": ...,
                     "isReversed": bool, "position": ..., "meaning": ...},
                    ...
                ],
                "timestamp": <int>
            }
        """
        spread = self._spreads.get(spread_id)
        if spread is None:
            raise ValueError(f"Unknown spread_id: {spread_id!r}. "
                             f"Available: {list(self._spreads.keys())}")

        card_count: int = spread["cardCount"]
        positions: list[str] = spread.get("positions", [])
        default_qs: list[str] = spread.get("defaultQuestions", [])

        # Determine question
        if not question:
            question = default_qs[0] if default_qs else "请给我指引"

        # Shuffle & draw unique cards
        shuffled = self.shuffle_deck()
        drawn_cards = shuffled[:card_count]

        # Ensure we have enough positions (pad if needed)
        while len(positions) < len(drawn_cards):
            positions.append(f"位置{len(positions) + 1}")

        cards_result = []
        for i, card in enumerate(drawn_cards):
            is_reversed = random.random() < 0.5
            meaning_key = "reversed" if is_reversed else "upright"
            meaning = card.get(meaning_key, "")
            cards_result.append(
                {
                    "number": card.get("number", 0),
                    "name": card.get("name", ""),
                    "type": card.get("type", ""),
                    "suit": card.get("suit"),
                    "isReversed": is_reversed,
                    "position": positions[i] if i < len(positions) else f"位置{i + 1}",
                    "meaning": meaning,
                }
            )

        return {
            "spread_id": spread_id,
            "spread_name": spread.get("name", ""),
            "question": question,
            "cards": cards_result,
            "timestamp": int(time.time()),
        }
