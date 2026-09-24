"""
契约校验器（Sprint 0 验收工具 / README5 §9.6）

用途：在生成前端快照或跑演示之前，机器化地检查"对外契约里不该出现的东西"。

检查项
------
1. ``contract_version`` 存在且为已知版本（README5 §4.1）；
2. **没有开发机绝对路径**（P0-10）—— 含 Windows 盘符、``/Users/``、``/home/``；
3. **没有 ``correct_answers``**（P0-11）—— 答案不下发浏览器；
4. **没有内部推断标记 ``_inferred_``**（P0-07）；
5. ``modules[].files`` 全部是项目内相对路径（P0-10）；
6. 训练题每题都带 ``source`` 字段（``data_driven`` / ``template``），便于诚实说明；
7. 训练题的 ``evidence[].file`` 是相对路径（P0-10）。

用法
----
    python scripts/validate_contract.py frontend/public/demo/project_analysis.json
    python scripts/validate_contract.py --project sample_projects/lab_safety_assistant

退出码：0 = 全部通过；1 = 有失败项。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
KNOWN_CONTRACT_VERSIONS = {"1.0"}

#: 匹配 Windows 盘符路径。
#: 注意 ``(?<![A-Za-z0-9])`` —— 否则 ``http://x`` 里的 ``p:/`` 会被误判成盘符。
ABS_PATH_PATTERNS = [
    re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]"),
    re.compile(r"^\\\\"),                  # UNC
    re.compile(r"^/(Users|home|var|opt|tmp)/"),
]

#: 路径类键名（与 engine/project_analyzer/main.py 的 _PATH_KEYS 保持一致）
PATH_KEYS = {"filepath", "file", "display_path", "source_file", "source_path"}
LOCATION_KEYS = {"location"}


class Report:
    def __init__(self) -> None:
        self.checks: list[tuple[str, bool, str]] = []

    def check(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append((name, passed, detail))

    @property
    def failed(self) -> bool:
        return any(not passed for _, passed, _ in self.checks)

    def render(self) -> str:
        lines = []
        for name, passed, detail in self.checks:
            mark = "PASS" if passed else "FAIL"
            suffix = f"  {detail}" if detail else ""
            lines.append(f"[{mark}] {name}{suffix}")
        return "\n".join(lines)


def _iter_strings(obj, path: str = ""):
    """深度遍历，产出 ``(字段路径, 键名, 字符串值)``。"""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str):
                yield f"{path}.{key}", key, value
            elif isinstance(value, (dict, list)):
                yield from _iter_strings(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            if isinstance(item, str):
                yield f"{path}[{index}]", "", item
            elif isinstance(item, (dict, list)):
                yield from _iter_strings(item, f"{path}[{index}]")


def _looks_absolute(value: str) -> bool:
    return any(pattern.search(value) for pattern in ABS_PATH_PATTERNS)


def _has_key(obj, name: str) -> bool:
    """深度检查是否存在某个键名。"""
    if isinstance(obj, dict):
        if name in obj:
            return True
        return any(_has_key(value, name) for value in obj.values())
    if isinstance(obj, list):
        return any(_has_key(item, name) for item in obj)
    return False


def validate_payload(payload: dict, source: str) -> Report:
    report = Report()

    # 1. contract_version
    version = payload.get("contract_version")
    report.check(
        "contract_version 存在且已知",
        version in KNOWN_CONTRACT_VERSIONS,
        f"version={version!r}",
    )

    # 2/5/7. 绝对路径
    # 2a. 路径类字段里不允许有绝对路径
    abs_hits: list[tuple[str, str]] = []
    for field_path, key, value in _iter_strings(payload):
        if key in PATH_KEYS or key in LOCATION_KEYS:
            candidate = value
            if key in LOCATION_KEYS and ":" in value:
                candidate = value.rsplit(":", 1)[0]
            if _looks_absolute(candidate):
                abs_hits.append((field_path, value))
    report.check(
        "契约里没有开发机绝对路径（路径类字段）",
        not abs_hits,
        f"{len(abs_hits)} 处，例如 {abs_hits[0] if abs_hits else ''}",
    )

    # 2b. **任意**字符串值里都不允许出现盘符/家目录路径。
    #     这一条专门抓"藏在讲解文本里的路径"——第 4 关的讲解曾经把
    #     `D:\learn_with_ai\...\reservation_manager.py` 直接印给学生。
    #     注意：必须在**解码后的值**上判断，不能对 json.dumps 的结果做正则，
    #     否则 `Args:\n` 这类转义会被误判成 `s:\` 盘符路径。
    embedded_hits: list[tuple[str, str]] = []
    for field_path, _key, value in _iter_strings(payload):
        if _looks_absolute(value):
            embedded_hits.append((field_path, value[:120]))
    report.check(
        "任意文本字段都不含盘符/家目录路径",
        not embedded_hits,
        f"{len(embedded_hits)} 处，例如 {embedded_hits[0] if embedded_hits else ''}",
    )

    # 3. correct_answers
    report.check(
        "契约不含 correct_answers（答案不下发，P0-11）",
        not any(key == "correct_answers" for _, key, _ in _iter_strings(payload))
        and not _has_key(payload, "correct_answers"),
        "",
    )

    # 4. _inferred_ 内部标记
    report.check(
        "契约不含 _inferred_ 内部标记（P0-07）",
        not any("_inferred_" in value for _, _key, value in _iter_strings(payload))
        and not _has_key(payload, "_inferred_"),
        "",
    )

    # 5. modules[].files 必须全部是相对路径
    module_files: list[str] = []
    for module in payload.get("modules", []) or []:
        module_files.extend(module.get("files", []) or [])
    bad_files = [f for f in module_files if _looks_absolute(f)]
    report.check(
        "modules[].files 全部为项目内相对路径",
        not bad_files,
        f"{len(bad_files)} 处异常",
    )

    # 6. 训练题 source 字段
    questions = (payload.get("training") or {}).get("questions", []) or []
    missing_source = [
        index for index, q in enumerate(questions) if "source" not in q
    ]
    report.check(
        "训练题每题都带 source 字段",
        not missing_source,
        f"{len(questions)} 题，缺 source 的下标 {missing_source}",
    )

    report.check(
        "训练题数量 > 0",
        len(questions) > 0,
        f"{len(questions)} 题",
    )

    # 7. 训练题 evidence 的文件路径
    bad_evidence: list[str] = []
    for q in questions:
        for item in q.get("evidence", []) or []:
            file_value = item.get("file", "")
            if file_value and _looks_absolute(file_value):
                bad_evidence.append(file_value)
    report.check(
        "训练题 evidence[].file 为相对路径",
        not bad_evidence,
        f"{len(bad_evidence)} 处异常",
    )

    # 8. 业务图谱（Sprint 1）：存在时必须是干净且结构完整的
    graph = payload.get("business_graph")
    if graph is None:
        report.check("business_graph（可选）", True, "本次契约不含业务图谱")
    else:
        report.check(
            "business_graph 状态正常（不是 failed）",
            graph.get("status") != "failed",
            f"status={graph.get('status')} {graph.get('error', '')}"[:120],
        )
        report.check(
            "business_graph 带 algorithm_version 与 source_hash",
            bool(graph.get("algorithm_version")) and bool(graph.get("source_hash")),
            f"level={graph.get('level')}",
        )
        domains = graph.get("domains", []) or []
        caps = graph.get("capabilities", []) or []
        report.check(
            "business_graph 有一级业务域与二级功能点",
            len(domains) >= 1 and len(caps) >= 1,
            f"{len(domains)} 域 / {len(caps)} 功能点",
        )
        graph_abs = [
            path for path, _key, value in _iter_strings(graph) if _looks_absolute(value)
        ]
        report.check(
            "business_graph 里没有绝对路径",
            not graph_abs,
            f"{len(graph_abs)} 处 {graph_abs[0] if graph_abs else ''}",
        )
        report.check(
            "business_graph 里没有 _inferred_ 内部标记",
            not any("_inferred_" in value for _, _key, value in _iter_strings(graph)),
        )

    # 9. 设计模式检测器的结论**不许**出现在学生可见文本里
    #    （README §16.2 / §19.1 #16 的决策：「误报高 → 不进学生视图、不作评分维度」）。
    #
    #    这条检查是被真实数据抓出来的：第 4 关的题干曾经直接把 ``design_approach``
    #    整句印出来，而那一句里含 "uses Repository Pattern"（未审核的推断），
    #    讲解里还有一条 "demonstrates Repository Pattern"。
    #    做法：从同一份契约里取出检测器报出的模式名，再扫学生可见字段。
    pattern_names = sorted({
        str(p.get("pattern_name") or "")
        for p in (((payload.get("deep_analysis") or {}).get("design_patterns") or {})
                  .get("patterns") or [])
        if str(p.get("pattern_name") or "").strip()
    })
    student_text: list[tuple[str, str]] = []
    for index, question in enumerate(questions):
        for key in ("title", "description", "explanation"):
            student_text.append((f"training.questions[{index}].{key}", str(question.get(key) or "")))
        for option in question.get("options", []) or []:
            student_text.append((f"training.questions[{index}].options", str(option.get("text") or "")))
    for index, impl in enumerate(
        ((payload.get("deep_analysis") or {}).get("key_implementations") or {}).get("implementations") or []
    ):
        student_text.append((f"key_implementations[{index}].design_approach", str(impl.get("design_approach") or "")))

    pattern_leaks = [
        (field_path, name)
        for field_path, text in student_text
        for name in pattern_names
        if name and name in text
    ]
    report.check(
        "学生可见文本里没有设计模式检测器的结论（未审核推断不进学生视图）",
        not pattern_leaks,
        f"{len(pattern_leaks)} 处，例如 {pattern_leaks[0] if pattern_leaks else ''}"
        if pattern_names else "本次契约里检测器没有报出任何模式",
    )

    print(f"\n=== 校验对象：{source} ===")
    print(report.render())
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 LearnWithAI 对外契约")
    parser.add_argument("json_path", nargs="?", help="要校验的 JSON 文件路径")
    parser.add_argument("--project", help="改为现场分析一个项目目录")
    args = parser.parse_args()

    if args.project:
        sys.path.insert(0, str(REPO_ROOT))
        from engine.project_analyzer import ProjectAnalyzer

        payload = ProjectAnalyzer().analyze(args.project).to_dict()
        source = f"<live> {args.project}"
    elif args.json_path:
        payload = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
        source = args.json_path
    else:
        parser.error("需要提供 json_path 或 --project")
        return 2

    report = validate_payload(payload, source)
    print()
    if report.failed:
        print("结果：存在未通过项 ✗")
        return 1
    print("结果：全部通过 ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
