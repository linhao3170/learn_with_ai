"""业务逻辑分析平台 · 接口层自测

用 FastAPI TestClient 直接打接口，不需要起服务器。

用法
----
::

    python scripts/test_logic_platform_api.py
    python scripts/test_logic_platform_api.py --project python_dotenv

退出码：0 = 全部通过；1 = 有失败项。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend"))

#: 与 scripts/validate_contract.py 同口径的绝对路径检测（契约里不许出现开发机路径）
_ABS_PATTERNS = [
    re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]"),
    re.compile(r"^\\\\"),
    re.compile(r"^/(Users|home|var|opt|tmp)/"),
]


class Report:
    def __init__(self) -> None:
        self.items: list[tuple[str, bool, str]] = []

    def check(self, name: str, passed: bool, detail: str = "") -> None:
        self.items.append((name, bool(passed), detail))

    @property
    def failed(self) -> bool:
        return any(not ok for _, ok, _ in self.items)

    def render(self) -> str:
        return "\n".join(
            f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else "")
            for name, ok, detail in self.items
        )


def _iter_strings(obj, path: str = ""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str):
                yield f"{path}.{key}", value
            elif isinstance(value, (dict, list)):
                yield from _iter_strings(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            if isinstance(item, str):
                yield f"{path}[{index}]", item
            elif isinstance(item, (dict, list)):
                yield from _iter_strings(item, f"{path}[{index}]")


def _absolute_hits(payload) -> list[tuple[str, str]]:
    return [(p, v[:90]) for p, v in _iter_strings(payload) if any(x.search(v) for x in _ABS_PATTERNS)]


class _HttpResponse:
    """与 ``requests``/``TestClient`` 同形状的最小响应对象。"""

    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text

    def json(self):
        import json as _json

        return _json.loads(self.text)


class _HttpClient:
    """基于标准库的极小 HTTP 客户端。

    **刻意不加 httpx 依赖**：仓库的 requirements 很克制
    （fastapi / uvicorn / python-multipart），为了一个测试脚本引入新依赖不划算。
    而且打真实 uvicorn 比 ASGI 直连更接近上线形态 —— 序列化与状态码都是真的。
    """

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, params: dict | None = None, body: dict | None = None):
        import json as _json
        import urllib.error
        import urllib.parse
        import urllib.request

        url = self.base_url + path
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            if clean:
                url += "?" + urllib.parse.urlencode(clean)
        data = _json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"} if data else {},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return _HttpResponse(response.status, response.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            return _HttpResponse(exc.code, exc.read().decode("utf-8", errors="replace"))

    def get(self, path: str, params: dict | None = None):
        return self._request("GET", path, params=params)

    def post(self, path: str, json: dict | None = None):
        return self._request("POST", path, body=json if json is not None else {})


def main() -> int:
    parser = argparse.ArgumentParser(description="业务逻辑分析平台 · 接口层自测")
    parser.add_argument("--project", default="python_dotenv")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000",
                        help="后端地址（需先启动 uvicorn）")
    args = parser.parse_args()

    client = _HttpClient(args.base_url)
    report = Report()
    project = args.project

    print(f"\n=== 业务逻辑分析平台接口自测 · {project} ===")
    print(f"目标后端：{args.base_url}")

    try:
        client.get("/api/health")
    except Exception as exc:
        print(f"\n连不上后端（{args.base_url}）：{exc}")
        print("请先启动：cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000")
        return 1

    # ---- 健康检查与版本 ----
    health = client.get("/api/health").json()
    report.check("健康检查版本已升到 0.5.0", health.get("version") == "0.5.0", str(health.get("version")))

    # ---- 项目列表 ----
    listing = client.get("/api/logic-platform/projects").json()
    ids = [p.get("project_id") for p in listing.get("projects") or []]
    report.check("平台项目列表含目标项目", project in ids, f"{ids}")

    # ---- 讲解层默认关闭（这是要如实告诉评审的事实）----
    narration = client.get("/api/logic-platform/narration-status").json()
    report.check(
        "讲解层默认关闭 且 不在关键路径上",
        narration.get("enabled") is False and narration.get("llm_in_critical_path") is False,
        str(narration.get("reason"))[:70],
    )

    # ---- 大小分析 + 板块 ----
    response = client.get(f"/api/logic-platform/{project}/analysis")
    report.check("分析接口返回 200", response.status_code == 200, f"HTTP {response.status_code}")
    if response.status_code != 200:
        print(report.render())
        return 1
    analysis = response.json()

    size = analysis.get("size") or {}
    board = analysis.get("sections") or {}
    report.check("有复杂度级别", bool(size.get("level")), f"{size.get('level')} {size.get('level_label')}")
    report.check("有处理策略", bool((size.get("tier") or {}).get("tier_label")),
                 str((size.get("tier") or {}).get("tier_label")))
    sections = board.get("sections") or []
    report.check("有业务板块", len(sections) >= 1, f"{len(sections)} 个")

    report.check("契约里没有开发机绝对路径（analysis）", not _absolute_hits(analysis),
                 str(_absolute_hits(analysis)[:1]))

    # ---- 单个板块 ----
    first_section_id = sections[0].get("section_id") if sections else ""
    if first_section_id:
        single = client.get(f"/api/logic-platform/{project}/sections/{first_section_id}")
        report.check("单板块接口 200", single.status_code == 200, f"HTTP {single.status_code}")
    # 用 ASCII 占位 id：URL 路径必须是 ASCII（urllib 不做隐式百分号编码）
    missing = client.get(f"/api/logic-platform/{project}/sections/no_such_section_id")
    report.check("未知板块返回 404（不静默兜底）", missing.status_code == 404, f"HTTP {missing.status_code}")

    # ---- 找可做课程的能力点 ----
    target = None
    for section in sections:
        for capability in section.get("capabilities") or []:
            if (capability.get("walkthrough") or {}).get("available"):
                target = capability
                break
        if target:
            break
    report.check("存在可进入沉浸式学习的能力点", target is not None,
                 str(target.get("capability_id")) if target else "无")
    if target is None:
        print(report.render())
        return 1

    capability_id = target["capability_id"]

    # ---- 讲稿 ----
    lesson_response = client.get(f"/api/logic-platform/{project}/lessons/{capability_id}")
    report.check("讲稿接口 200", lesson_response.status_code == 200, f"HTTP {lesson_response.status_code}")
    if lesson_response.status_code != 200:
        print(report.render())
        return 1
    lesson = lesson_response.json()
    segments = lesson.get("segments") or []
    report.check("讲稿有多段", len(segments) >= 2, f"{len(segments)} 段")
    report.check(
        "讲稿带字面模板（一句话概括： 含尾随空格）",
        (lesson.get("render") or {}).get("summary_heading") == "一句话概括： ",
    )
    report.check("契约里没有开发机绝对路径（lesson）", not _absolute_hits(lesson),
                 str(_absolute_hits(lesson)[:1]))
    review = lesson.get("review") or {}
    report.check("引擎不自己发布（can_publish=False）", review.get("can_publish") is False)
    report.check("机械复核通过", review.get("verification_passed") is True,
                 f"通过 {review.get('verified_checks')} / 失败 {review.get('failed_checks')}")

    # ---- 校验接口 ----
    verify_response = client.post(f"/api/logic-platform/{project}/lessons/{capability_id}/verify")
    report.check("校验接口 200", verify_response.status_code == 200, f"HTTP {verify_response.status_code}")
    if verify_response.status_code == 200:
        vbody = verify_response.json()
        report.check(
            "校验报告零失败",
            (vbody.get("report") or {}).get("counts", {}).get("failed") == 0,
            str((vbody.get("report") or {}).get("counts")),
        )
        report.check("校验报告带给学生看的结论", bool((vbody.get("summary") or {}).get("conclusion")),
                     str((vbody.get("summary") or {}).get("conclusion"))[:80])

    # ---- 源码切片（证据跳转的落点）----
    source_ref = (segments[0].get("source") or {})
    src = client.get(
        f"/api/logic-platform/{project}/source",
        params={"path": source_ref.get("file"), "start": source_ref.get("start_line"), "end": source_ref.get("end_line")},
    )
    report.check("源码切片 200", src.status_code == 200, f"HTTP {src.status_code}")
    if src.status_code == 200:
        body = src.json()
        report.check("源码切片带行号文本", bool(body.get("lines")) and "number" in (body.get("lines") or [{}])[0],
                     f"{len(body.get('lines') or [])} 行（含上下文）")
        report.check(
            "切片内容与讲稿摘录一致（证据可回看）",
            "\n".join(
                line["text"] for line in body["lines"]
                if int(source_ref.get("start_line") or 0) <= line["number"] <= int(source_ref.get("end_line") or 0)
            ) == (segments[0].get("code_excerpt") or ""),
        )
    traversal = client.get(f"/api/logic-platform/{project}/source", params={"path": "../../etc/passwd"})
    report.check("路径穿越被拒（400）", traversal.status_code == 400, f"HTTP {traversal.status_code}")

    # ---- LLM 讲解接口：默认必须 503 且说清原因 ----
    narr = client.post(f"/api/logic-platform/{project}/lessons/{capability_id}/narration", json={})
    report.check("未启用讲解层时返回 503", narr.status_code == 503, f"HTTP {narr.status_code}")
    detail = ""
    try:
        detail = str(narr.json().get("detail") or "")
    except Exception:
        pass
    report.check("503 说明了原因（不静默降级）", "未启用" in detail or "默认关闭" in detail, detail[:80])

    # ---- 教师审核 ----
    claim_id = ""
    for segment in segments:
        for claim in segment.get("must_remember") or []:
            claim_id = claim.get("claim_id") or ""
            break
        if claim_id:
            break
    confirm = client.post(
        f"/api/teacher/logic-platform/{project}/lessons/{capability_id}/review",
        json={"status": "confirmed", "reviewer": "自测", "claims": {claim_id: {"decision": "confirm"}} if claim_id else {}},
    )
    report.check("教师确认 200", confirm.status_code == 200, f"HTTP {confirm.status_code}")
    if confirm.status_code == 200:
        cbody = confirm.json()
        report.check("确认后状态为 approved", cbody.get("status") == "approved", str(cbody.get("status")))
        report.check("确认后 can_publish=True（发布权在教师）", cbody.get("can_publish") is True,
                     str(cbody.get("can_publish")))

    bad = client.post(
        f"/api/teacher/logic-platform/{project}/lessons/{capability_id}/review",
        json={"status": "confirmed", "claims": {"不存在的claim": {"decision": "confirm"}}},
    )
    report.check("未知 claim_id 被拒（400，不猜）", bad.status_code == 400, f"HTTP {bad.status_code}")

    bad_status = client.post(
        f"/api/teacher/logic-platform/{project}/lessons/{capability_id}/review",
        json={"status": "随便写的"},
    )
    report.check("非法 status 被拒（400）", bad_status.status_code == 400, f"HTTP {bad_status.status_code}")

    # 复位，避免影响后续手动演示；并断言复位后**确实**回到不可发布。
    # 这是刚修掉的一个真 bug 的回归护栏：曾经「重置审核」只清了 human_review，
    # 却把磁盘上那份 can_publish=True 原样写回，于是"已重置"的课仍是可发布状态。
    reset = client.post(
        f"/api/teacher/logic-platform/{project}/lessons/{capability_id}/review",
        json={"status": "reset"},
    )
    report.check("重置审核 200", reset.status_code == 200, f"HTTP {reset.status_code}")
    if reset.status_code == 200:
        rbody = reset.json()
        report.check(
            "重置审核后 can_publish 必须回到 False（没有教师确认就不许发布）",
            rbody.get("can_publish") is False,
            f"can_publish={rbody.get('can_publish')} status={rbody.get('status')}",
        )
        report.check(
            "重置审核后状态回到 needs_review",
            rbody.get("status") == "needs_review",
            str(rbody.get("status")),
        )

    # ---- 未知分析 404 ----
    unknown = client.get("/api/logic-platform/lp_doesnotexist/analysis")
    report.check("未知分析返回 404", unknown.status_code == 404, f"HTTP {unknown.status_code}")

    # ---- 前端实际依赖的字段路径（防止前后端字段静默错位）----
    # 这些路径是 frontend/src/components/logic-platform/*.vue 真的会读的。
    # 少一个，界面就会静默显示空白而不是报错 —— 所以必须在接口层钉住。
    def has_path(obj, dotted: str) -> bool:
        """按点分路径取字段，支持 ``a.0.b`` 形式的数组下标。

        注意：数字段是**数组下标**，取完下标要直接进入下一轮，
        不能再去字典里找键 ``"0"`` —— 第一版就是这么写的，
        于是所有 ``x.0.y`` 形式的断言全部误报为"字段缺失"。
        """
        cur = obj
        for part in dotted.split('.'):
            if isinstance(cur, list):
                if part.isdigit():
                    index = int(part)
                    if index >= len(cur):
                        return False
                    cur = cur[index]
                    continue
                if not cur:
                    return False
                cur = cur[0]
            if not isinstance(cur, dict) or part not in cur:
                return False
            cur = cur[part]
        return True

    ui_paths = [
        "size.level", "size.level_known", "size.level_label", "size.level_basis",
        "size.structure_rows.0.source", "size.structure_rows.0.note", "size.structure_rows.0.label",
        "size.tier.tier_label", "size.tier.rationale", "size.tier.student_note", "size.tier.caveat",
        "size.tier.section_budget", "size.tier.walkthrough_capability_budget",
        "size.tier.segments_per_lesson_cap", "size.tier.statements_per_segment_cap",
        "size.complexity.level", "size.caveats",
        "sections.sections.0.section_id", "sections.sections.0.name_cn", "sections.sections.0.role",
        "sections.sections.0.is_core", "sections.sections.0.confidence",
        "sections.sections.0.objective", "sections.sections.0.does_not",
        "sections.sections.0.capabilities.0.capability_id",
        "sections.sections.0.capabilities.0.importance_reasons",
        "sections.sections.0.capabilities.0.members.0.file",
        "sections.sections.0.capabilities.0.members.0.start_line",
        "sections.sections.0.capabilities.0.members.0.end_line",
        "sections.sections.0.capabilities.0.walkthrough.available",
        "sections.sections.0.capabilities.0.walkthrough.state",
        "sections.sections.0.capabilities.0.card.does_not",
        "sections.sections.0.capabilities.0.card.does_not_confidence",
        "sections.budget.section_budget.truncated", "sections.budget.capability_budget.truncated",
        "sections.budget.walkthrough_budget.truncated",
        "sections.counts.sections", "sections.counts.capabilities_shown", "sections.caveats",
    ]
    missing_paths = [p for p in ui_paths if not has_path(analysis, p)]
    report.check("前端依赖的分析字段路径全部存在", not missing_paths,
                 f"缺 {len(missing_paths)} 个：{missing_paths[:4]}")

    lesson_paths = [
        "render.header_format", "render.bullets_heading", "render.summary_heading",
        "render.know_enough_heading", "render.lesson_recap_heading",
        "intro", "one_line_frame", "summary_diagram", "lesson_recap", "consolidate",
        "segments.0.segment_id", "segments.0.order", "segments.0.title", "segments.0.title_status",
        "segments.0.header_text", "segments.0.segment_kind", "segments.0.lead_in",
        "segments.0.code_excerpt", "segments.0.code_excerpt_hash",
        "segments.0.source.file", "segments.0.source.start_line", "segments.0.source.end_line",
        "segments.0.must_remember.0.claim_text", "segments.0.must_remember.0.category",
        "segments.0.must_remember.0.evidence.0.evidence_id",
        "segments.0.must_remember.0.evidence.0.file",
        "segments.0.must_remember.0.evidence.0.start_line",
        "segments.0.must_remember.0.evidence.0.end_line",
        "segments.0.must_remember.0.evidence.0.excerpt_hash",
        "segments.0.one_sentence_summary.claim_text",
        "review.status", "review.can_publish", "review.verification_passed",
        "review.verified_checks", "review.failed_checks", "review.generated_by",
        "review.blocking_issues", "review.human_review.status",
        "verification.counts.passed", "verification.checks.0.check_id",
        "verification.rejected_claim_ids", "caveats",
        "members_covered.0.symbol", "truncated",
    ]
    missing_lesson = [p for p in lesson_paths if not has_path(lesson, p)]
    report.check("前端依赖的讲稿字段路径全部存在", not missing_lesson,
                 f"缺 {len(missing_lesson)} 个：{missing_lesson[:4]}")

    print()
    print(report.render())
    print()
    if report.failed:
        print("结果：存在未通过项 ✗")
        return 1
    print("结果：全部通过 ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
