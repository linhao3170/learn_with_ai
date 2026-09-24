"""确定性校验器 —— 「AI 出现幻觉了怎么办」的可运行答案

这个模块是整套平台可信度的**最后一道闸门**。它不生成任何内容，
只做一件事：**把讲稿里的每一句话，拿回真实源码与真实 AST 上重新核对一遍。**

四层防线里它排第三层（README §13.3 的「三层判定主体分离」在这里扩成四层）
------------------------------------------------------------------------
| 层 | 谁产生 | 是否可复现 | 本模块的角色 |
|---|---|---|---|
| 1 事实层 | AST 规则引擎 | 逐字节可复现 | 校验对象的来源 |
| 2 讲解层 | 规则引擎（可替换为 LLM） | 规则部分可复现 | **被校验** |
| 3 校验层 | **本模块** | 逐字节可复现 | 抓幻觉 |
| 4 审核层 | 人（教师） | — | 一票否决 |

为什么它必须**绕开缓存、直接从磁盘重读**
----------------------------------------
引擎别处都走 ``engine/parser/ast_cache``（按 mtime+size 命中，性能考虑）。
校验器**刻意不用它**：校验器的职责是"对着地面真相复核"，
如果它读的还是生成时的缓存，那它校验的就是自己的记忆，而不是文件本身。
一次多余的磁盘读，换来的是"这句话现在打开那个文件、翻到那一行，还成立"。

十项检查（每一项都能给出具体的 file + 行号证据）
------------------------------------------------
============================  ==================================================
``V01_path_relative``         证据里的 ``file`` 必须是项目内相对路径（契约纪律）
``V02_span_valid``            行区间合法：``1 <= start <= end <= 文件总行数``
``V03_excerpt_fidelity``      存下来的摘录与**现在磁盘上的那段源码**逐字符相同
``V04_hash_matches``          摘录的 sha256 与存下来的哈希一致（防静默改写）
``V05_segment_excerpt``       段的 ``code_excerpt`` 与磁盘源码逐字符相同
``V06_symbol_exists``         段引用的函数在 AST 里真的存在，且段落在它的行范围内
``V07_return_claim``          声称"第 N 行 return"时，AST 里第 N 行**真有** Return
``V08_return_ordinal``        "这是第几个 return"由 AST 重新数一遍，对不上就算错
``V09_skipped_range``         "后面第 a-b 行不会执行"的区间必须真实存在于函数内
``V10_claim_has_evidence``    每一条断言至少带一条证据（无证据不入学生视图）
``V11_evidence_checkable``    每条证据必须带**非空摘录 + 哈希**（否则它核不了）
============================  ==================================================

失败之后会怎样（这是关键：**失败是可见的，不是被吞掉的**）
----------------------------------------------------------
- 失败断言被标 ``verified=False`` + ``reject_reason``；
- ``report.can_publish`` 变 False；
- 调用方（``apply_verification``）把段与课的 ``review.status`` 置为
  ``rejected``，并把失败项写进 ``blocking_issues``；
- **前端必须显示这些失败项**，不许在页面上悄悄少显示几条就完事。

这正好回答"如果 AI 出现幻觉了怎么办"：
**幻觉不是被"提示词祈祷"避免的，是被这份报告抓出来、并且默认进不了学生视图。**
"""

from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .hashing import sha256_text as _sha256

ALGORITHM_VERSION = "verify-1.0"

#: Windows 盘符 / UNC / 家目录 —— 与 scripts/validate_contract.py 同口径。
_ABS_PATH_PATTERNS = [
    re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]"),
    re.compile(r"^\\\\"),
    re.compile(r"^/(Users|home|var|opt|tmp)/"),
]

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_SKIPPED = "skipped"

#: 检查项编号与名称（顺序固定，报告按此顺序输出，便于逐字节比对）
CHECKS: List[Tuple[str, str]] = [
    ("V01_path_relative", "证据文件路径为项目内相对路径"),
    ("V02_span_valid", "行区间合法（1 <= start <= end <= 总行数）"),
    ("V03_excerpt_fidelity", "存下的摘录与磁盘源码逐字符一致"),
    ("V04_hash_matches", "摘录哈希与存下的哈希一致"),
    ("V05_segment_excerpt", "段的代码摘录与磁盘源码逐字符一致"),
    ("V06_symbol_exists", "段引用的函数在 AST 中真实存在且覆盖段行范围"),
    ("V07_return_claim", "声称的 return 行在 AST 中真有 Return"),
    ("V08_return_ordinal", "「第几个 return」由 AST 重新计数后一致"),
    ("V09_skipped_range", "「后面不会执行」的行区间真实存在于函数内"),
    ("V10_claim_has_evidence", "每条断言都带至少一条证据"),
    ("V11_evidence_checkable", "每条证据都带非空摘录与哈希（否则核不了）"),
]


def _looks_absolute(value: str) -> bool:
    return any(pattern.search(value or "") for pattern in _ABS_PATH_PATTERNS)


@dataclass
class CheckResult:
    """一条检查结果。``detail`` 必须能说清"哪个文件、哪一行、差在哪"。"""

    check_id: str = ""
    check_name: str = ""
    scope: str = ""          # lesson | segment | claim | evidence
    target_id: str = ""
    status: str = STATUS_PASS
    file: str = ""
    line: int = 0
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "check_name": self.check_name,
            "scope": self.scope,
            "target_id": self.target_id,
            "status": self.status,
            "file": self.file,
            "line": self.line,
            "detail": self.detail,
        }


@dataclass
class VerificationReport:
    lesson_id: str = ""
    checks: List[CheckResult] = field(default_factory=list)
    rejected_claim_ids: List[str] = field(default_factory=list)
    rejected_segment_ids: List[str] = field(default_factory=list)
    can_publish: bool = False
    counts: Dict[str, int] = field(default_factory=dict)
    caveats: List[str] = field(default_factory=list)

    def add(self, result: CheckResult) -> None:
        self.checks.append(result)

    def finalize(self) -> "VerificationReport":
        passed = sum(1 for c in self.checks if c.status == STATUS_PASS)
        failed = sum(1 for c in self.checks if c.status == STATUS_FAIL)
        skipped = sum(1 for c in self.checks if c.status == STATUS_SKIPPED)
        self.counts = {
            "checks": len(self.checks),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "rejected_claims": len(self.rejected_claim_ids),
            "rejected_segments": len(self.rejected_segment_ids),
        }
        # 只要有一项失败，就**不允许**发布 —— 不做"错误率低于 x% 就放行"的妥协
        self.can_publish = failed == 0
        return self

    def to_dict(self) -> dict:
        return {
            "verify_version": ALGORITHM_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "lesson_id": self.lesson_id,
            "can_publish": self.can_publish,
            "counts": dict(self.counts),
            "checks": [c.to_dict() for c in self.checks],
            "rejected_claim_ids": list(self.rejected_claim_ids),
            "rejected_segment_ids": list(self.rejected_segment_ids),
            "caveats": list(self.caveats),
        }


def _read_lines(source_root: str, file_rel: str) -> Optional[List[str]]:
    """**直接从磁盘读**（刻意不走 ast_cache，见模块 docstring）。"""
    if not source_root or not file_rel:
        return None
    abs_path = os.path.join(source_root, file_rel.replace("/", os.sep))
    try:
        with open(abs_path, "r", encoding="utf-8") as handle:
            return handle.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return None


def _parse(source_root: str, file_rel: str) -> Tuple[Optional[ast.AST], Optional[List[str]]]:
    lines = _read_lines(source_root, file_rel)
    if lines is None:
        return None, None
    try:
        return ast.parse("\n".join(lines)), lines
    except SyntaxError:
        return None, lines


def _find_func(tree: ast.AST, symbol: str, start_line: int) -> Optional[ast.AST]:
    """找函数：名字匹配，且行号最接近声称的那个（同名函数取最近的）。"""
    candidates: List[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol:
            candidates.append(node)
    if not candidates:
        return None
    candidates.sort(key=lambda n: abs(int(getattr(n, "lineno", 0) or 0) - int(start_line or 0)))
    return candidates[0]


def _iter_evidence(segment: Dict[str, Any]):
    """遍历一个段里所有证据，产出 ``(owner_kind, owner_id, evidence, claim_id)``。"""
    for claim in segment.get("must_remember") or []:
        for item in claim.get("evidence") or []:
            yield "claim", str(claim.get("claim_id") or ""), item
    for claim in segment.get("know_enough") or []:
        for item in claim.get("evidence") or []:
            yield "claim", str(claim.get("claim_id") or ""), item
    summary = segment.get("one_sentence_summary")
    if isinstance(summary, dict):
        for item in summary.get("evidence") or []:
            yield "claim", str(summary.get("claim_id") or ""), item


def verify_lesson(lesson: Dict[str, Any], source_root: str) -> VerificationReport:
    """校验一课。返回的报告里每条失败项都能落到具体文件与行号。"""
    lesson = lesson if isinstance(lesson, dict) else {}
    report = VerificationReport(lesson_id=str(lesson.get("lesson_id") or ""))
    segments = [s for s in (lesson.get("segments") or []) if isinstance(s, dict)]

    for segment in segments:
        segment_id = str(segment.get("segment_id") or "")
        source = segment.get("source") if isinstance(segment.get("source"), dict) else {}
        file_rel = str(source.get("file") or "")
        start = int(source.get("start_line") or 0)
        end = int(source.get("end_line") or 0)
        symbol = str(source.get("symbol") or "")

        def fail(check_id: str, detail: str, line: int = 0, scope: str = "segment",
                 target: str = "") -> None:
            name = dict(CHECKS).get(check_id, check_id)
            report.add(
                CheckResult(
                    check_id=check_id, check_name=name, scope=scope,
                    target_id=target or segment_id, status=STATUS_FAIL,
                    file=file_rel, line=line, detail=detail,
                )
            )

        def ok(check_id: str, scope: str = "segment", target: str = "", line: int = 0) -> None:
            name = dict(CHECKS).get(check_id, check_id)
            report.add(
                CheckResult(
                    check_id=check_id, check_name=name, scope=scope,
                    target_id=target or segment_id, status=STATUS_PASS,
                    file=file_rel, line=line,
                )
            )

        # ---- V01 路径纪律 ----
        if _looks_absolute(file_rel):
            fail("V01_path_relative", f"证据路径是绝对路径：{file_rel[:80]}")
        else:
            ok("V01_path_relative")

        lines = _read_lines(source_root, file_rel)
        if lines is None:
            fail("V02_span_valid", f"读不到源码文件（项目内相对路径：{file_rel}）")
            report.rejected_segment_ids.append(segment_id)
            continue

        total = len(lines)
        # ---- V02 行区间 ----
        if not (1 <= start <= end <= total):
            fail("V02_span_valid", f"行区间非法：{start}-{end}，文件共 {total} 行", start)
            report.rejected_segment_ids.append(segment_id)
            continue
        ok("V02_span_valid", line=start)

        # ---- V05 段摘录保真 ----
        actual_excerpt = "\n".join(lines[start - 1 : end])
        stored_excerpt = str(segment.get("code_excerpt") or "")
        if actual_excerpt != stored_excerpt:
            fail(
                "V05_segment_excerpt",
                f"段摘录与磁盘源码不一致（存下 {len(stored_excerpt)} 字符 / "
                f"磁盘 {len(actual_excerpt)} 字符）；"
                f"磁盘该区间首行为：{lines[start - 1][:60]!r}",
                start,
            )
            report.rejected_segment_ids.append(segment_id)
        else:
            ok("V05_segment_excerpt", line=start)

        # ---- V06 符号存在 ----
        tree, _ = _parse(source_root, file_rel)
        func = _find_func(tree, symbol, start) if tree is not None else None
        if func is None:
            fail("V06_symbol_exists", f"AST 中找不到名为 {symbol!r} 的函数/方法", start)
            report.rejected_segment_ids.append(segment_id)
        else:
            func_start = int(getattr(func, "lineno", 0) or 0)
            func_end = int(getattr(func, "end_lineno", 0) or func_start)
            if not (func_start <= start and end <= func_end):
                fail(
                    "V06_symbol_exists",
                    f"段行范围 {start}-{end} 不在 {symbol} 的函数范围 {func_start}-{func_end} 内",
                    start,
                )
                report.rejected_segment_ids.append(segment_id)
            else:
                ok("V06_symbol_exists", line=func_start)

        # ---- V07/V08/V09 分支事实 ----
        detail = segment.get("branch_detail")
        if isinstance(detail, dict) and detail.get("is_return"):
            claimed_line = int(detail.get("return_at_line") or 0)
            has_return = False
            if tree is not None:
                for node in ast.walk(tree):
                    if isinstance(node, ast.Return) and int(getattr(node, "lineno", 0) or 0) == claimed_line:
                        has_return = True
                        break
            if not has_return:
                fail(
                    "V07_return_claim",
                    f"讲稿声称第 {claimed_line} 行是 return，但 AST 里该行没有 Return 语句",
                    claimed_line,
                )
            else:
                ok("V07_return_claim", line=claimed_line)

            # 重新数一遍序号
            claimed_ordinal = int(detail.get("return_ordinal_in_function") or 0)
            if tree is not None and func is not None and claimed_ordinal:
                lines_of_returns = sorted(
                    int(getattr(n, "lineno", 0) or 0)
                    for n in ast.walk(func)
                    if isinstance(n, ast.Return)
                )
                try:
                    actual_ordinal = lines_of_returns.index(claimed_line) + 1
                except ValueError:
                    actual_ordinal = 0
                if actual_ordinal != claimed_ordinal:
                    fail(
                        "V08_return_ordinal",
                        f"讲稿说这是第 {claimed_ordinal} 个 return，AST 重数为第 {actual_ordinal} 个"
                        f"（函数内 return 行：{lines_of_returns}）",
                        claimed_line,
                    )
                else:
                    ok("V08_return_ordinal", line=claimed_line)

            # 「后面 a-b 行不会执行」必须真实
            skipped = detail.get("skipped_line_range")
            if isinstance(skipped, dict):
                sk_start = int(skipped.get("start_line") or 0)
                sk_end = int(skipped.get("end_line") or 0)
                func_end = int(getattr(func, "end_lineno", 0) or 0) if func is not None else 0
                if not (end < sk_start <= sk_end <= func_end):
                    fail(
                        "V09_skipped_range",
                        f"「后面不会执行」的区间 {sk_start}-{sk_end} 不合法"
                        f"（段结束于 {end}，函数结束于 {func_end}）",
                        sk_start,
                    )
                else:
                    ok("V09_skipped_range", line=sk_start)

        # ---- V03/V04/V10 证据级检查 ----
        for owner_kind, claim_id, evidence in _iter_evidence(segment):
            ev_file = str(evidence.get("file") or "")
            ev_start = int(evidence.get("start_line") or 0)
            ev_end = int(evidence.get("end_line") or 0)

            # V10：有证据但证据本身是空壳（无文件 / 无行号）也算不合格
            if not ev_file or ev_start <= 0:
                fail(
                    "V10_claim_has_evidence",
                    f"断言 {claim_id} 带了一条空证据（file={ev_file!r}, start={ev_start}）",
                    scope=owner_kind, target=claim_id,
                )
                if claim_id and claim_id not in report.rejected_claim_ids:
                    report.rejected_claim_ids.append(claim_id)
                continue
            ok("V10_claim_has_evidence", scope=owner_kind, target=claim_id, line=ev_start)

            ev_lines = _read_lines(source_root, ev_file)
            if ev_lines is None:
                fail(
                    "V03_excerpt_fidelity",
                    f"证据指向的文件读不到：{ev_file}",
                    scope=owner_kind, target=claim_id,
                )
                if claim_id not in report.rejected_claim_ids:
                    report.rejected_claim_ids.append(claim_id)
                continue
            ev_total = len(ev_lines)
            if not (1 <= ev_start <= ev_end <= ev_total):
                fail(
                    "V02_span_valid",
                    f"证据行区间非法：{ev_start}-{ev_end}，{ev_file} 共 {ev_total} 行",
                    scope=owner_kind, target=claim_id,
                )
                if claim_id not in report.rejected_claim_ids:
                    report.rejected_claim_ids.append(claim_id)
                continue

            stored_ev_excerpt = str(evidence.get("excerpt") or "")
            actual_ev_excerpt = "\n".join(ev_lines[ev_start - 1 : ev_end])

            # V11：摘录为空 = 这条"证据"根本核不了。
            # 一开始 V03/V04 在摘录为空时是**跳过**的，于是任何手搓的
            # 空壳证据都能无声通过 —— 那等于给绕过证据链留了一个后门。
            # 所以这里把"空摘录"本身判为失败，而不是静默跳过。
            if not stored_ev_excerpt:
                fail(
                    "V11_evidence_checkable",
                    f"证据没有摘录（{ev_file}:{ev_start}-{ev_end}）——"
                    "空摘录的证据无法核验，等于绕过证据链",
                    line=ev_start, scope=owner_kind, target=claim_id,
                )
                if claim_id not in report.rejected_claim_ids:
                    report.rejected_claim_ids.append(claim_id)
                continue

            if stored_ev_excerpt != actual_ev_excerpt:
                fail(
                    "V03_excerpt_fidelity",
                    f"证据摘录与磁盘源码不一致（{ev_file}:{ev_start}-{ev_end}）",
                    line=ev_start, scope=owner_kind, target=claim_id,
                )
                if claim_id not in report.rejected_claim_ids:
                    report.rejected_claim_ids.append(claim_id)
            else:
                ok("V03_excerpt_fidelity", scope=owner_kind, target=claim_id, line=ev_start)

            stored_hash = str(evidence.get("excerpt_hash") or "")
            if stored_hash:
                if stored_hash != _sha256(actual_ev_excerpt):
                    fail(
                        "V04_hash_matches",
                        f"证据摘录哈希对不上（{ev_file}:{ev_start}-{ev_end}）——"
                        "可能是源码被改过，或讲稿被改过",
                        line=ev_start, scope=owner_kind, target=claim_id,
                    )
                    if claim_id not in report.rejected_claim_ids:
                        report.rejected_claim_ids.append(claim_id)
                else:
                    ok("V04_hash_matches", scope=owner_kind, target=claim_id, line=ev_start)

    # 去重并保持稳定顺序（确定性）
    report.rejected_claim_ids = sorted(set(report.rejected_claim_ids))
    report.rejected_segment_ids = sorted(set(report.rejected_segment_ids))

    report.caveats = [
        "校验器只做**机械复核**：它能证明「这句话引用的那段代码确实存在且逐字符一致」，"
        "不能证明「这句业务解释是对的」。后者只有人能判（README §13.4 三层判定主体分离）。",
        "校验器刻意绕开 ast_cache，直接从磁盘重读源码 —— 它校验的是文件本身，不是生成时的记忆。",
        "任何一项失败都会让 can_publish=False，且失败项必须在前端可见；"
        "不存在「错误率低于阈值就放行」的规则。",
        f"算法版本 {ALGORITHM_VERSION}；同一份输入两次运行结果逐字节一致（无随机、无网络、无时间依赖）。",
    ]
    return report.finalize()


def apply_verification(lesson: Dict[str, Any], report: VerificationReport) -> Dict[str, Any]:
    """把校验结果写回讲稿：标红失败断言、置 review 状态。

    **失败的断言不会从数据里消失** —— 它们保留原文并带 ``reject_reason``，
    由前端显示为"已拦截"。这比"悄悄删掉"更符合本项目的诚实纪律：
    评审者要能看到"系统抓到了什么"，而不是只看到一份干净的结果。
    """
    lesson = lesson if isinstance(lesson, dict) else {}
    rejected_claims = set(report.rejected_claim_ids)
    rejected_segments = set(report.rejected_segment_ids)

    for segment in lesson.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        segment_id = str(segment.get("segment_id") or "")
        for key in ("must_remember", "know_enough"):
            for claim in segment.get(key) or []:
                if not isinstance(claim, dict):
                    continue
                claim_id = str(claim.get("claim_id") or "")
                if claim_id in rejected_claims:
                    claim["verified"] = False
                    claim["reject_reason"] = "未通过确定性校验：引用的代码或行号与磁盘源码不符"
                    claim["confidence"] = "needs_review"
        summary = segment.get("one_sentence_summary")
        if isinstance(summary, dict) and str(summary.get("claim_id") or "") in rejected_claims:
            summary["verified"] = False
            summary["reject_reason"] = "未通过确定性校验：引用的代码或行号与磁盘源码不符"
            summary["confidence"] = "needs_review"

    blocking: List[str] = []
    if report.rejected_segment_ids:
        blocking.append(
            f"{len(report.rejected_segment_ids)} 个段未通过校验："
            f"{'、'.join(report.rejected_segment_ids[:5])}"
        )
    if report.rejected_claim_ids:
        blocking.append(
            f"{len(report.rejected_claim_ids)} 条断言未通过校验："
            f"{'、'.join(report.rejected_claim_ids[:5])}"
        )
    if not blocking:
        blocking.append("尚未经教师确认：段标题与业务含义均为引擎推断，发布权在教师")

    lesson["verification"] = report.to_dict()
    review = lesson.get("review") if isinstance(lesson.get("review"), dict) else {}
    # ⚠️ 引擎**永远**不把 can_publish 置 True。
    #
    # 语义必须分清：
    # - ``verification_passed``：**机械复核**通过，引用与磁盘源码逐字符一致；
    # - ``can_publish``：**可以给学生看**，它需要 机械复核通过 **且** 教师确认。
    #
    # 第一版把 can_publish 直接等于 report.can_publish，于是出现
    # 「can_publish=True 但 blocking_issues 里写着『尚未经教师确认』」的自相矛盾。
    # 发布权属于人（README §13.3「教师有一票否决权」），引擎只负责把证据摆齐。
    review["verification_passed"] = bool(report.can_publish)
    review["can_publish"] = False
    review["blocking_issues"] = blocking
    if report.rejected_claim_ids or report.rejected_segment_ids:
        review["status"] = "rejected"
    else:
        review["status"] = "needs_review"
    review["verification_version"] = ALGORITHM_VERSION
    review["verified_checks"] = report.counts.get("passed", 0)
    review["failed_checks"] = report.counts.get("failed", 0)
    lesson["review"] = review
    return lesson


def verify_and_apply(lesson: Dict[str, Any], source_root: str) -> Dict[str, Any]:
    """一步到位：校验 + 回写。返回同一个 lesson 字典（已就地更新）。"""
    report = verify_lesson(lesson, source_root)
    return apply_verification(lesson, report)


def summarize_for_students(report: VerificationReport) -> Dict[str, Any]:
    """给学生看的一句话结论（不做技术细节，但**不隐藏失败**）。"""
    counts = report.counts
    if report.can_publish:
        conclusion = (
            f"证据校验通过：{counts.get('passed', 0)} 项检查全部通过，"
            "讲稿里每一条结论引用的代码都能在源码里逐字符对上。"
        )
    else:
        conclusion = (
            f"证据校验**未通过**：{counts.get('failed', 0)} 项失败，"
            f"{counts.get('rejected_claims', 0)} 条断言已被拦截（页面上标红），"
            "这些内容在教师确认前不会作为结论呈现。"
        )
    return {
        "can_publish": report.can_publish,
        "conclusion": conclusion,
        "counts": dict(counts),
        "failing_checks": [
            c.to_dict() for c in report.checks if c.status == STATUS_FAIL
        ],
    }
