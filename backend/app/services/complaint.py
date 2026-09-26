"""公众诉求业务规则：状态流转、字段校验、回复留痕与超期判定都收在这里。

超期口径只有一份（``is_overdue``），受理列表、回复详情与统计卡片都通过
``public_view`` / ``stats`` 调用它，避免三处各算各的：

* 以「办理期限」为准，到期日当天仍算按期，过了到期日才算超期；
* 办理期限缺失或无法解析时，统一显示为 ``DEADLINE_MISSING_LABEL``，且不算超期；
* 仅未办结诉求（待受理、办理中）参与超期判定，已回复、已关闭视为办结。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.store import store

MODULE = "complaint"
REQUIRED_FIELDS = ["诉求编号", "诉求来源", "诉求内容"]
DEADLINE_FIELD = "办理期限"
REPLY_FIELD = "回复内容"
REPLY_LOG_FIELD = "回复记录"
OVERDUE_FIELD = "是否超期"
DEADLINE_MISSING_LABEL = "未设期限"
STATUS_ORDER = ["待受理", "办理中", "已回复", "已关闭"]
# 已回复、已关闭都算办结，不再计超期。
OPEN_STATUSES = {"待受理", "办理中"}
ACTION_RULES = {"受理诉求": "办理中", "提交回复": "已回复", "关闭诉求": "已关闭"}
NEGATIVE_ACTIONS = []
_DEADLINE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d")


def parse_deadline(raw: Any) -> date | None:
    """把办理期限解析成日期；空值或无法解析一律返回 None（不抛错）。"""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    for fmt in _DEADLINE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def deadline_label(entry: dict[str, Any]) -> str:
    """办理期限的统一展示口径：有效值原样展示，缺失/非法值显示「未设期限」。"""
    raw = entry.get(DEADLINE_FIELD)
    if parse_deadline(raw) is None:
        return DEADLINE_MISSING_LABEL
    return str(raw).strip()


def is_overdue(entry: dict[str, Any], *, today: date | None = None) -> bool:
    """受理、回复、统计三处共用的超期判定。

    未办结且办理期限已过（不含到期日当天）才算超期；期限缺失或已办结均不超期。
    """
    if entry.get("status") not in OPEN_STATUSES:
        return False
    deadline = parse_deadline(entry.get(DEADLINE_FIELD))
    if deadline is None:
        return False
    return (today or date.today()) > deadline


def public_view(entry: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    """对外统一的诉求展示结构：办理期限走统一口径，并带上同一套超期结论。"""
    view = dict(entry)
    view[DEADLINE_FIELD] = deadline_label(entry)
    view[OVERDUE_FIELD] = is_overdue(entry, today=today)
    return view


class ComplaintService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
        today: date | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("诉求编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        page_rows = rows[start:start + size]
        return [public_view(row, today=today) for row in page_rows], total

    def get_entry(self, entry_id: int, *, today: date | None = None) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return public_view(entry, today=today)

    def stats(self, *, today: date | None = None) -> dict[str, int]:
        """统计卡片口径：各状态计数，超期件数直接调用同一份 is_overdue。"""
        rows = store.rows(MODULE)
        result = {f"{label}诉求": 0 for label in STATUS_ORDER}
        result["超期件数"] = 0
        for row in rows:
            label = f"{row.get('status')}诉求"
            if label in result:
                result[label] += 1
            if is_overdue(row, today=today):
                result["超期件数"] += 1
        return result

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry[REPLY_LOG_FIELD] = []
        rows.append(entry)
        return entry, []

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
        *,
        today: date | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        """执行状态流转动作，返回 (展示结构或 None, 说明)。

        规则：已关闭是终态，不允许再受理、回复或回到办理中；其余流转保持原有
        受理/回复口径不变。提交回复时相同内容只留一条，不重复登记。
        """
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"诉求记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于公众诉求可执行范围"
        target = ACTION_RULES[action]
        if str(entry.get("status") or "") == STATUS_ORDER[-1]:
            if action == "受理诉求":
                return None, "诉求已关闭，不能重新受理，也不能回到办理中"
            return None, "诉求已关闭，不能再回复或重复关闭"

        note = ""
        if action == "提交回复":
            replies = entry.setdefault(REPLY_LOG_FIELD, [])
            content = str((values or {}).get(REPLY_FIELD) or "").strip()
            if content:
                if content in replies:
                    note = "相同内容的回复已存在，未重复登记；"
                else:
                    replies.append(content)

        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return public_view(entry, today=today), f"{note}诉求记录已{action}"
