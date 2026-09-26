"""诉求超期判定的唯一口径。

受理页、回复页、统计页三处一律走这里，不允许各写一套。

口径（三处共用）：
- 以「办理期限」当天的下班时间（WORK_END_HOUR 点）为截止时刻；
- 已关闭的诉求不再计超期（关闭即终态）；
- 办理期限缺失或无法解析时，统一记为「未定期限」，且一律不算超期；
- 其余情况：now 严格晚于截止时刻即超期。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

WORK_END_HOUR = 18  # 下班时间：办理期限当天 18:00 为截止时刻
DEADLINE_FIELD = "办理期限"
NO_DEADLINE_TEXT = "未定期限"

_DEADLINE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d")


def parse_deadline(value: Any) -> date | None:
    """把办理期限解析成日期；空值或无法识别的格式一律返回 None（未定期限）。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in _DEADLINE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def deadline_cutoff(deadline: date) -> datetime:
    """办理期限当天的下班时刻，即超期判定的截止点。"""
    return datetime(deadline.year, deadline.month, deadline.day, WORK_END_HOUR)


def evaluate_deadline(entry: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """对单条诉求给出统一判定结果。

    返回字段：
    - deadline_date：办理期限（YYYY-MM-DD），未定期限时为 None；
    - deadline_label：展示口径，缺失时统一显示「未定期限」；
    - is_overdue：是否超期；
    - deadline_missing：办理期限是否缺失/无法解析。
    """
    moment = now or datetime.now()
    raw = entry.get(DEADLINE_FIELD)
    deadline = parse_deadline(raw)

    if deadline is None:
        return {
            "deadline_date": None,
            "deadline_label": NO_DEADLINE_TEXT,
            "is_overdue": False,  # 未定期限：统一不算超期
            "deadline_missing": True,
        }

    is_closed = entry.get("status") == "已关闭"
    overdue = (not is_closed) and moment > deadline_cutoff(deadline)
    return {
        "deadline_date": deadline.isoformat(),
        "deadline_label": deadline.isoformat(),
        "is_overdue": overdue,
        "deadline_missing": False,
    }


def apply_deadline_view(entry: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """把统一判定结果回填到诉求记录上，供列表/详情/统计直接消费。

    同时用「办理期限」的统一口径覆盖展示字段，保证列表与详情看到的期限一致。
    """
    verdict = evaluate_deadline(entry, now=now)
    entry["办理期限"] = verdict["deadline_label"]
    entry["is_overdue"] = verdict["is_overdue"]
    entry["deadline_missing"] = verdict["deadline_missing"]
    return entry
