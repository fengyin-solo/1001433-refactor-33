"""公众诉求业务规则：状态流转、字段校验、筛选口径与超期统计都收在这里。

超期判定不在这里另写，统一走 app.services.deadline，受理、回复、统计共用一份。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.deadline import DEADLINE_FIELD, apply_deadline_view
from app.store import store

MODULE = "complaint"
REQUIRED_FIELDS = ["诉求编号", "诉求来源", "诉求内容"]
DETAIL_FIELDS = ["涉及设施", "受理人员", "处理措施", DEADLINE_FIELD]
STATUS_ORDER = ["待受理", "办理中", "已回复", "已关闭"]
ACTION_RULES = {"受理诉求": "办理中", "提交回复": "已回复", "关闭诉求": "已关闭"}
# 允许执行的状态流转；不在表里的动作一律拦下（已关闭是终态，不能回到办理中）。
TRANSITIONS: dict[str, set[str]] = {
    "受理诉求": {"待受理"},
    # 已回复也允许再次提交回复：重复回复只留一条（覆盖最新），不新增状态。
    "提交回复": {"办理中", "已回复"},
    "关闭诉求": {"办理中", "已回复"},
}
NEGATIVE_ACTIONS = []


class ComplaintService:
    # ---- 读取 -------------------------------------------------------------
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        overdue_only: bool = False,
        page: int = 1,
        size: int = 20,
        now: datetime | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [self._view(dict(row), now=now) for row in store.rows(MODULE)]
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("诉求编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if overdue_only:
            rows = [row for row in rows if row.get("is_overdue")]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int, *, now: datetime | None = None) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return None if entry is None else self._view(entry, now=now)

    # ---- 写入 -------------------------------------------------------------
    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        # 办理期限允许缺，缺时统一按「未定期限」展示，且不判超期。
        deadline = values.get(DEADLINE_FIELD)
        if deadline is not None and str(deadline).strip():
            entry[DEADLINE_FIELD] = str(deadline).strip()
        for field in DETAIL_FIELDS:
            entry.setdefault(field, None)
        entry["replies"] = []
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return self._view(entry), []

    def run_action(
        self,
        entry_id: int,
        action: str,
        *,
        reply: str | None = None,
        operator: str | None = None,
        now: datetime | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"诉求记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于公众诉求可执行范围"

        current = entry.get("status")
        # 已关闭是终态：受理、回复、关闭都不能再动，更不能回到办理中。
        if current == STATUS_ORDER[-1]:
            return None, "诉求已关闭，不能再受理或回复"
        if current not in TRANSITIONS[action]:
            return None, f"诉求当前为「{current}」，不能执行「{action}」"

        entry.setdefault("replies", [])
        moment = (now or datetime.now()).isoformat(timespec="seconds")

        if action == "受理诉求":
            if operator:
                entry["受理人员"] = operator
        elif action == "提交回复":
            return self._add_reply(entry, reply, moment, now=now)

        entry["status"] = ACTION_RULES[action]
        entry["pending"] = entry["status"] != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return self._view(entry, now=now), f"诉求记录已{action}"

    # ---- 统计 -------------------------------------------------------------
    def stats(self, *, now: datetime | None = None) -> dict[str, Any]:
        """受理、回复、统计三处共用的数字：全部基于同一份超期判定。"""
        rows = [self._view(dict(row), now=now) for row in store.rows(MODULE)]
        by_status = {status: 0 for status in STATUS_ORDER}
        for row in rows:
            by_status[str(row.get("status"))] = by_status.get(str(row.get("status")), 0) + 1
        overdue_rows = [row for row in rows if row.get("is_overdue")]
        return {
            "total": len(rows),
            "by_status": by_status,
            "overdue": len(overdue_rows),
            "overdue_ids": [int(row["id"]) for row in overdue_rows],
            "deadline_missing": sum(1 for row in rows if row.get("deadline_missing")),
        }

    # ---- 内部 -------------------------------------------------------------
    def _add_reply(
        self,
        entry: dict[str, Any],
        reply: str | None,
        moment: str,
        *,
        now: datetime | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        """提交回复：同一诉求的回复只保留一条，重复提交覆盖原回复，不新增。"""
        content = (reply or "").strip()
        if not content:
            return None, "回复内容不能为空"

        replies = entry.setdefault("replies", [])
        if replies:  # 重复回复：只留一条
            replies[0].update({"content": content, "replied_at": moment})
            message = "回复已更新（重复回复只保留最新一条）"
        else:
            replies.append({"content": content, "replied_at": moment})
            message = "诉求记录已提交回复"
        entry["处理措施"] = content
        entry["status"] = ACTION_RULES["提交回复"]
        entry["pending"] = False
        entry["abnormal"] = False
        return self._view(entry, now=now), message

    def _view(self, entry: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
        """统一出口：补齐状态展示字段并套用唯一超期判定。"""
        entry.setdefault("replies", [])
        entry["诉求状态"] = entry.get("status")
        return apply_deadline_view(entry, now=now)
