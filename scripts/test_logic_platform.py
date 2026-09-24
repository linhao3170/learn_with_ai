"""业务逻辑分析平台 · 引擎自测与人工走查

用途
----
1. **机器断言**：大小分级、板块产出、讲稿生成、校验通过、确定性。
2. **人工走查**：把生成的讲稿按参考文档（``shuliyewu.txt``）的排版打印出来，
   让人直接看"像不像那份文档"，而不是只看 JSON。

用法
----
::

    # 用已构建的演示快照（推荐，秒级）
    python scripts/test_logic_platform.py

    # 指定项目
    python scripts/test_logic_platform.py --project python_dotenv

    # 现场重跑引擎分析（慢，但验的是当前代码）
    python scripts/test_logic_platform.py --project python_dotenv --live

    # 只打印讲稿（人工走查用）
    python scripts/test_logic_platform.py --render

退出码
------
0 = 全部断言通过；1 = 有失败项（与仓库其它测试脚本一致）。
"""

from __future__ import annotations

import argparse
import json
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

from engine.logic_platform import (  # noqa: E402
    PLATFORM_VERSION,
    analyze_project,
    build_lesson_for,
    verify,
    walkthrough,
)

DEFAULT_PROJECT = "python_dotenv"

DEMO_ROOT = REPO_ROOT / "frontend" / "public" / "demo"


class Report:
    def __init__(self) -> None:
        self.items: list[tuple[str, bool, str]] = []

    def check(self, name: str, passed: bool, detail: str = "") -> None:
        self.items.append((name, bool(passed), detail))

    @property
    def failed(self) -> bool:
        return any(not ok for _, ok, _ in self.items)

    def render(self) -> str:
        lines = []
        for name, ok, detail in self.items:
            mark = "PASS" if ok else "FAIL"
            suffix = f"  {detail}" if detail else ""
            lines.append(f"[{mark}] {name}{suffix}")
        return "\n".join(lines)


def _snapshot_path(project_id: str) -> Path:
    if project_id == "lab_safety_assistant":
        return DEMO_ROOT / "project_analysis.json"
    return DEMO_ROOT / "projects" / project_id / "project_analysis.json"


def _source_root(project_id: str) -> Path:
    if project_id == "lab_safety_assistant":
        return DEMO_ROOT / "source"
    return DEMO_ROOT / "projects" / project_id / "source"


def load_inputs(project_id: str, live: bool) -> tuple[dict, dict, Path]:
    """返回 ``(overview, graph, source_root)``。"""
    source_root = _source_root(project_id)
    if live:
        from engine.project_analyzer import ProjectAnalyzer

        source_dir = REPO_ROOT / "validation" / project_id
        if not source_dir.exists():
            source_dir = REPO_ROOT / "sample_projects" / project_id
        result = ProjectAnalyzer().analyze(str(source_dir))
        payload = result.to_dict()
        return payload.get("overview") or {}, payload.get("business_graph") or {}, source_dir

    snapshot = _snapshot_path(project_id)
    if not snapshot.exists():
        raise SystemExit(f"找不到快照：{snapshot}（先跑 scripts/build_demo_snapshots.py，或加 --live）")
    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    return payload.get("overview") or {}, payload.get("business_graph") or {}, source_root


def check_engine_purity() -> tuple[bool, str]:
    """静态断言：``engine/logic_platform/`` 里没有联网 / LLM / 随机 / 时间依赖。

    为什么这条要单独写：仓库里已有的三个 ``FORBIDDEN_IMPORTS`` 检查
    （``test_teaching_coverage.py`` / ``test_teaching_card_coverage.py`` /
    ``test_design_rubric.py``）覆盖的是 ``engine/teaching`` 与 ``engine/design``，
    **不会**扫到新增的 ``engine/logic_platform``。少了这条，
    "引擎无 LLM"就只是我在文档里的一句承诺，而不是机器能验的事实。

    LLM 的**调用**放在 ``backend/app/services/narration_service.py``，
    本包只保留契约与把关（``narration.py``）—— 这正是为了过这一关。
    """
    forbidden = (
        "requests", "httpx", "urllib", "http", "socket",
        "openai", "anthropic", "dashscope", "zhipu", "deepseek",
        "random", "time", "datetime",
    )
    pattern = re.compile(r"^\s*(?:import|from)\s+([A-Za-z_][\w.]*)", re.MULTILINE)
    package = REPO_ROOT / "engine" / "logic_platform"
    offenders: list[str] = []
    scanned = 0
    for path in sorted(package.glob("*.py")):
        scanned += 1
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            root = match.group(1).split(".")[0]
            if root in forbidden:
                offenders.append(f"{path.name}: {match.group(0).strip()}")
    if offenders:
        return False, f"{len(offenders)} 处禁用导入：{'；'.join(offenders[:4])}"
    return True, f"扫描 {scanned} 个文件，0 处禁用导入"


def compare_snapshots() -> int:
    """把仓库里所有已建快照的项目横着跑一遍，打印分级与分流结果。

    README §21.3 那张实测表就是这条命令产出的 —— 让评审能自己复现，
    而不是相信文档里的数字（README §13.2 证据纪律第 3 条：数字必须能回指）。
    """
    demo_root = DEMO_ROOT
    targets: list[tuple[str, Path | None, Path]] = []
    default_snapshot = demo_root / "project_analysis.json"
    if default_snapshot.exists():
        targets.append(("lab_safety_assistant", default_snapshot, demo_root / "source"))
    projects_root = demo_root / "projects"
    if projects_root.exists():
        for child in sorted(projects_root.iterdir(), key=lambda p: p.name):
            snapshot = child / "project_analysis.json"
            if child.is_dir() and snapshot.exists():
                targets.append((child.name, snapshot, child / "source"))

    # 真实第三方项目（可能还没建快照）也一并现算，如实标注来源
    for name in ("python_dotenv", "flask", "urllib3"):
        source_dir = REPO_ROOT / "validation" / name
        if source_dir.exists() and not any(t[0] == name for t in targets):
            targets.append((name, None, source_dir))

    if not targets:
        print("没有可比较的项目（先跑 scripts/build_demo_snapshots.py）")
        return 1

    print("\n=== 分级与分流横向对照 ===")
    header = f"{'项目':22} {'行数':>7} {'级别':>5} {'策略':18} {'板块':>7} {'能力点':>9} {'课程':>6} {'成员函数':>8}"
    print(header)
    print("-" * len(header))

    rows = 0
    for project_id, snapshot, source_root in targets:
        try:
            if snapshot is not None:
                payload = json.loads(snapshot.read_text(encoding="utf-8"))
                overview = payload.get("overview") or {}
                graph = payload.get("business_graph") or {}
            else:
                from engine.project_analyzer import ProjectAnalyzer

                payload = ProjectAnalyzer().analyze(str(source_root)).to_dict()
                overview = payload.get("overview") or {}
                graph = payload.get("business_graph") or {}
        except Exception as exc:
            print(f"{project_id:22} 分析失败：{exc}")
            continue

        analysis = analyze_project(project_id, project_id, overview, graph)
        size = analysis["size"]
        counts = (analysis.get("sections") or {}).get("counts") or {}
        lines = (size.get("structure") or {}).get("total_lines", 0)
        print(
            f"{project_id:22} {lines:>7} {str(size.get('level') or '—'):>5} "
            f"{str(size.get('tier', {}).get('tier_label') or '—'):18} "
            f"{counts.get('sections', 0):>3}/{counts.get('sections_shown', 0):<3} "
            f"{counts.get('capabilities', 0):>4}/{counts.get('capabilities_shown', 0):<4} "
            f"{counts.get('walkthrough_available', 0):>6} "
            f"{counts.get('members', 0):>8}"
        )
        rows += 1

    print()
    print("「板块 / 能力点」列是 `总数/本次展示`：两份数字不一样，就说明该级策略发生了截断。")
    print("截断原因写在该项目的 sections.caveats 里，界面必须显示出来（不许静默少给）。")
    return 0 if rows else 1


def render_lesson(lesson: dict) -> str:
    """按参考文档的排版打印一课 —— 人工走查用。"""
    out: list[str] = []
    out.append("=" * 72)
    out.append(f"第 {lesson.get('lesson_number')} 课：{lesson.get('title')}")
    out.append(f"（板块：{lesson.get('section_name')} · 级别：{lesson.get('level')}）")
    out.append("=" * 72)
    out.append("")
    out.append(lesson.get("intro", ""))
    out.append("")
    out.append(lesson.get("one_line_frame", ""))
    out.append("")
    for segment in lesson.get("segments") or []:
        if segment.get("lead_in"):
            out.append(f"【{segment['lead_in']}】")
        out.append(segment.get("header_text", ""))
        annotations = {
            int(a.get("line") or 0): a.get("text") for a in (segment.get("line_annotations") or [])
        }
        source = segment.get("source") or {}
        start = int(source.get("start_line") or 0)
        for offset, line in enumerate((segment.get("code_excerpt") or "").split("\n")):
            number = start + offset
            note = annotations.get(number)
            out.append(f"{number:>5}| {line}" + (f"    {note}" if note else ""))
        bullets = segment.get("must_remember") or []
        if bullets:
            out.append(walkthrough.RENDER_TEMPLATES["bullets_heading"])
            for bullet in bullets:
                flag = "" if bullet.get("verified", True) else "  ⚠️[已拦截]"
                out.append(f"- {bullet.get('claim_text')}{flag}")
        if segment.get("know_enough"):
            out.append(walkthrough.RENDER_TEMPLATES["know_enough_heading"])
            for item in segment.get("know_enough") or []:
                out.append(f"- {item.get('claim_text')}")
        summary = segment.get("one_sentence_summary") or {}
        if summary:
            out.append(f"一句话概括： {summary.get('claim_text')}")
        out.append("")
    out.append(lesson.get("summary_diagram", ""))
    out.append("")
    recap = lesson.get("lesson_recap") or []
    if recap:
        out.append(f"你现在需要记住的 {len(recap)} 个核心要点：")
        for index, item in enumerate(recap, 1):
            out.append(f"{index}. {item}")
        out.append("")
    out.append(lesson.get("consolidate", ""))
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="业务逻辑分析平台 · 引擎自测")
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--live", action="store_true", help="现场重跑引擎分析（慢）")
    parser.add_argument("--render", action="store_true", help="打印讲稿全文（人工走查）")
    parser.add_argument("--out", help="把讲稿写入指定文件（人工走查/存档用，如 .lp_render.txt）")
    parser.add_argument("--json", action="store_true", help="打印分析结果 JSON")
    parser.add_argument("--compare", action="store_true",
                        help="横向对照所有项目的分级与分流结果（README §21.3 那张表）")
    args = parser.parse_args()

    if args.compare:
        return compare_snapshots()

    report = Report()
    overview, graph, source_root = load_inputs(args.project, args.live)

    print(f"\n=== 业务逻辑分析平台自测 · {args.project}（live={args.live}） ===")
    print(f"platform_version={PLATFORM_VERSION}  源码根={source_root}")

    analysis = analyze_project(args.project, args.project, overview, graph)
    size = analysis["size"]
    board = analysis["sections"]

    # ---- 纪律：新包自己也不许联网 / 引入 LLM ----
    pure, pure_detail = check_engine_purity()
    report.check("engine/logic_platform 无联网/LLM/随机/时间依赖", pure, pure_detail)

    # ---- 阶段 1：大小 ----
    report.check("识别出复杂度级别", bool(size.get("level")), f"level={size.get('level')}")
    report.check(
        "结构规模七项以上",
        len(size.get("structure") or {}) >= 7,
        f"{len(size.get('structure') or {})} 项",
    )
    report.check(
        "每个数字都标了来源",
        all(row.get("source") in ("ast", "business_graph") for row in size.get("structure_rows") or []),
    )
    report.check("给了处理策略", bool(size.get("tier", {}).get("tier_label")),
                 f"tier={size.get('tier', {}).get('tier_label')}")

    # ---- 阶段 3：板块 ----
    sections = board.get("sections") or []
    report.check("产出了业务板块", len(sections) >= 1, f"{len(sections)} 个板块")
    caps = [c for s in sections for c in (s.get("capabilities") or [])]
    report.check("板块下有可点击的能力点", len(caps) >= 1, f"{len(caps)} 个能力点")
    report.check(
        "能力点带成员函数行号",
        all(
            m.get("file") and m.get("start_line")
            for c in caps for m in (c.get("members") or [])
        ),
        f"{sum(len(c.get('members') or []) for c in caps)} 个成员函数",
    )
    report.check(
        "证据路径都是相对路径",
        not any(
            ":" in str(m.get("file") or "") or str(m.get("file") or "").startswith("/")
            for c in caps for m in (c.get("members") or [])
        ),
    )
    # 分流：必须至少有一个能力点可做课程，且超出预算的显式标注
    available = [c for c in caps if (c.get("walkthrough") or {}).get("available")]
    beyond = [c for c in caps if (c.get("walkthrough") or {}).get("state") == "beyond_budget"]
    report.check("有可进入沉浸式学习的能力点", len(available) >= 1, f"{len(available)} 个")
    report.check(
        "超出预算的能力点带中文理由（截断可见）",
        all((c.get("walkthrough") or {}).get("reason") for c in beyond),
        f"{len(beyond)} 个未展开",
    )

    # ---- 阶段 4–5：讲稿 + 校验 ----
    target = available[0] if available else (caps[0] if caps else None)
    if target is None:
        report.check("能选出讲稿目标", False, "没有能力点")
        print(report.render())
        return 1

    built = build_lesson_for(analysis, target["capability_id"], str(source_root), graph=graph)
    report.check("讲稿生成成功", built.get("ok"), str(built.get("error") or ""))
    lesson = built.get("lesson") or {}
    segments = lesson.get("segments") or []

    report.check("讲稿切成了多段", len(segments) >= 2, f"{len(segments)} 段")
    report.check(
        "段头格式符合参考文档",
        all(
            str(s.get("header_text", "")).startswith(f"第 {s.get('order')} 段：")
            and "（" in str(s.get("header_text")) and " 行）" in str(s.get("header_text"))
            for s in segments
        ),
        segments[0].get("header_text") if segments else "",
    )
    report.check(
        "每段都带真实代码摘录",
        all(s.get("code_excerpt") and s.get("code_excerpt_hash") for s in segments),
    )
    report.check(
        "每段都有「重点记什么」",
        all(len(s.get("must_remember") or []) >= 1 for s in segments),
    )
    report.check(
        "每段都有「一句话概括」",
        all((s.get("one_sentence_summary") or {}).get("claim_text") for s in segments),
    )
    report.check(
        "每条断言都带证据",
        all(
            c.get("evidence")
            for s in segments
            for c in (s.get("must_remember") or []) + (s.get("know_enough") or [])
        ),
    )

    # ---- 证据的四个身份字段必须齐：evidence_id + fact_id + 行区间 + 哈希 ----
    all_evidence = [
        item
        for s in segments
        for c in (s.get("must_remember") or []) + (s.get("know_enough") or [])
        for item in (c.get("evidence") or [])
    ] + [
        item
        for s in segments
        for item in ((s.get("one_sentence_summary") or {}).get("evidence") or [])
    ]
    report.check(
        "每条证据都有稳定 evidence_id（ev_ 前缀）",
        bool(all_evidence) and all(str(e.get("evidence_id") or "").startswith("ev_") for e in all_evidence),
        f"{len(all_evidence)} 条证据",
    )
    report.check(
        "每条证据都有行区间与摘录哈希",
        all(
            int(e.get("start_line") or 0) > 0 and int(e.get("end_line") or 0) > 0 and e.get("excerpt_hash")
            for e in all_evidence
        ),
    )
    # fact_id 必须**真的**指向图谱里的事实，不许编一个看起来像的 id
    graph_fact_ids = {str(f.get("fact_id")) for f in (graph.get("facts") or []) if isinstance(f, dict)}
    linked = [e for e in all_evidence if str(e.get("fact_id") or "")]
    bogus = sorted({str(e.get("fact_id")) for e in linked} - graph_fact_ids)
    report.check(
        "非空的 fact_id 全部真实存在于图谱事实表中（不是编的）",
        not bogus,
        f"{len(linked)}/{len(all_evidence)} 条挂到了事实表，编造的 id：{bogus[:3]}",
    )
    # 字面模板必须与参考文档一致（含「一句话概括：」冒号后的那个半角空格）
    templates = lesson.get("render") or {}
    report.check(
        "字面模板与参考文档一致",
        templates.get("bullets_heading") == "重点记什么："
        and templates.get("summary_heading") == "一句话概括： "
        and templates.get("header_format") == "第 {order} 段：{title}（{start}-{end} 行）",
        repr(templates.get("summary_heading")),
    )

    verification = lesson.get("verification") or {}
    counts = verification.get("counts") or {}
    report.check(
        "确定性校验零失败",
        counts.get("failed", 1) == 0,
        f"通过 {counts.get('passed')} / 失败 {counts.get('failed')}",
    )
    report.check(
        "机械复核通过（verification_passed）",
        bool(lesson.get("review", {}).get("verification_passed")),
        f"通过 {counts.get('passed')} / 失败 {counts.get('failed')}",
    )
    report.check(
        "引擎不给自己发通行证（can_publish 必须为 False，发布权归教师）",
        lesson.get("review", {}).get("can_publish") is False,
        f"status={lesson.get('review', {}).get('status')}",
    )

    # ---- 确定性：同一份输入跑两次，结果逐字节一致 ----
    again = build_lesson_for(analysis, target["capability_id"], str(source_root), graph=graph)
    report.check(
        "确定性：两次生成逐字节一致",
        json.dumps(built, ensure_ascii=False, sort_keys=True)
        == json.dumps(again, ensure_ascii=False, sort_keys=True),
    )

    # ---- 防幻觉：篡改一行代码后，校验器必须抓到 ----
    import copy

    tampered = copy.deepcopy(lesson)
    for segment in tampered.get("segments") or []:
        if segment.get("must_remember"):
            # 模拟"AI 编了一段不存在的代码"
            segment["code_excerpt"] = "def 这段代码根本不存在():\n    pass"
            break
    tampered_report = verify.verify_lesson(tampered, str(source_root))
    report.check(
        "篡改摘录后校验器能抓到（这是防幻觉的核心证据）",
        tampered_report.counts.get("failed", 0) > 0,
        f"失败 {tampered_report.counts.get('failed')} 项",
    )
    report.check(
        "篡改后 can_publish 变 False",
        tampered_report.can_publish is False,
    )

    # ---- 输出 ----
    print()
    print(report.render())
    print()
    print(f"级别 {size.get('level')}（{size.get('level_label')}）· 策略「{size.get('tier', {}).get('tier_label')}」")
    print(f"板块 {len(sections)} 个 / 能力点 {len(caps)} 个 / 可做课程 {len(available)} 个")
    print(f"讲稿 {len(segments)} 段 · 校验 {counts.get('passed')} 通过 / {counts.get('failed')} 失败")

    if args.json:
        print(json.dumps(analysis, ensure_ascii=False, indent=2)[:4000])
    if args.render or args.out:
        rendered = render_lesson(lesson)
        if args.out:
            Path(args.out).write_text(rendered, encoding="utf-8")
            print(f"\n讲稿已写入：{args.out}（{len(rendered)} 字符）")
        if args.render:
            print()
            print(rendered)

    print()
    if report.failed:
        print("结果：存在未通过项 ✗")
        return 1
    print("结果：全部通过 ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
