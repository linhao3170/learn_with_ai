"""LLM 讲解层 —— 契约与合并器（**引擎内零网络调用**）

为什么 LLM 代码放在这里、而调用放在后端
----------------------------------------
``engine/`` 有一条被测试强制的纪律：**无随机、无网络、无 LLM**。
``scripts/test_teaching_coverage.py`` / ``test_teaching_card_coverage.py`` /
``test_design_rubric.py`` 里写死了::

    FORBIDDEN_IMPORTS = ("requests","httpx","urllib","http","socket",
                         "openai","anthropic","random","time","datetime")

也就是说，**只要 ``engine/`` 里出现一次网络调用，那三个测试立刻红。**
所以本模块只做两件事，且都不联网：

1. **定义契约**：外部讲解器（后端服务）该收到什么、该返回什么；
2. **合并 + 把关**：把外部返回的讲解文字合进确定性讲稿，**并逐条把关**。

真正的模型调用在 ``backend/app/services/narration_service.py``（默认关闭）。
这样拆的好处是：把引擎的确定性测试跑在离线环境里依然全绿。

把关规则（这才是重点）
----------------------
README §13.3 允许 LLM 做「讲解稿」，但同一节也写死了红线：
**不许让 LLM 判定对错、给分数、或生成评分基准。**

于是本模块的合并逻辑遵守四条：

1. **模型只能给行号，不许给代码。**
   讲解文本里引用的代码摘录，**一律由本模块从磁盘重新读**。
   模型返回的 ``excerpt`` 字段即便提供也**被丢弃** ——
   否则模型可以凭空编一段"看起来像代码"的东西，而校验器拿它没辙。
2. **引用范围必须落在它所属的段里。**
   模型说"这句结论的依据是 ``a.py:88-90``"，那 88-90 必须落在该段的
   行范围内（或该段已有断言的证据范围内）。想引用别的文件？不允许 ——
   那意味着它在讲段外的话，属于越界。
3. **落不到证据上的断言，直接拒绝并留痕。**
   不是"警告一下照常显示"，而是进 ``rejected[]``、带 ``reason``、
   **不写进讲稿**。宁缺毋滥。
4. **合并完必须重跑校验器。**
   ``verify.verify_and_apply`` 会重新对磁盘源码逐条复核，
   并把 ``generated_by`` 标成 ``llm_draft``、``llm_claim_ratio`` 算出来、
   状态强制为 ``needs_review``（**LLM 产物自己永远拿不到通行证**）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import verify as _verify
from .hashing import sha256_text

ALGORITHM_VERSION = "narration-1.0"

#: 外部讲解器的产物标记。写进 ``lesson.review.generated_by``。
GENERATED_BY_LLM = "llm_draft"

#: 讲解器必须遵守的指令。**提示词里写死"给不出证据就跳过"**，
#: 这是 README §13.3「判断不了必须输出 unknown，不允许为了让学生感觉良好而给出正向判定」
#: 在讲解层的对应实现。
NARRATION_SYSTEM_PROMPT = """你在为一个「业务逻辑讲解」产品写讲稿。产品有一条硬规矩：
**每一句话都必须能回指到真实代码的文件与行号。**

你必须遵守：
1. 只解释给你的事实，**不许新增任何事实**（不许猜业务背景、不许猜调用方、不许推断未给出的行为）。
2. 每一条要点、每一句总结都必须附 `evidence`，元素形如
   {"file": "相对路径", "start_line": N, "end_line": M}，
   且这个行范围**必须落在你正在讲的这一段（segment）自己的行范围内**。
3. 如果你无法为某句话找到段内的证据 —— **直接不要写这句话**，不要编造行号。
   产品宁可少一条要点，也不要一条编的。
4. **不要输出代码**。只需要给行号，产品会自己去源码里取真实代码。
   你返回的任何代码文本都会被丢弃。
5. 不要判断对错、不要打分、不要评价代码质量好坏、不要写"这是一个好设计"之类的评价。
   只做「这段代码在业务上做了什么」的映射与措辞润色。
6. 分支的真假**不许断言**。静态阅读看不到运行时的输入，
   所以遇到 if 只能说"真假取决于输入"，不许说"这里条件成立"。
7. 全部用简体中文。保留产品的字面排版：要点标题是「重点记什么：」，
   总结标题是「一句话概括： 」（注意冒号后有一个空格）。

输出必须是 JSON，结构见 user 消息里的 schema。不要输出 JSON 以外的任何内容。"""

#: 讲解器应当返回的结构（文档用；实际把关由 :func:`apply_narration` 做）。
NARRATION_RESPONSE_SCHEMA: Dict[str, Any] = {
    "lesson_id": "string（必须与请求里的一致）",
    "narrator": "string（提供方标识，例如 openai-compatible）",
    "model": "string",
    "segments": [
        {
            "segment_id": "string（必须来自请求里给出的段 id）",
            "bullets": [
                {
                    "text": "string（中文讲解，不含代码）",
                    "evidence": [{"file": "string", "start_line": 1, "end_line": 2}],
                }
            ],
            "summary": {
                "text": "string（一句话总结）",
                "evidence": [{"file": "string", "start_line": 1, "end_line": 2}],
            },
        }
    ],
}


@dataclass
class RejectedNarration:
    """被拦下的讲解条目 —— 保留原文，便于评审者看到「系统抓到了什么」。"""

    segment_id: str = ""
    kind: str = ""          # bullet | summary
    text: str = ""
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "segment_id": self.segment_id,
            "kind": self.kind,
            "text": self.text,
            "reason": self.reason,
        }


@dataclass
class NarrationOutcome:
    lesson_id: str = ""
    applied: int = 0
    rejected: List[RejectedNarration] = field(default_factory=list)
    llm_claim_ratio: float = 0.0
    verification: Dict[str, Any] = field(default_factory=dict)
    caveats: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "narration_version": ALGORITHM_VERSION,
            "lesson_id": self.lesson_id,
            "applied": self.applied,
            "rejected_count": len(self.rejected),
            "rejected": [r.to_dict() for r in self.rejected],
            "llm_claim_ratio": round(self.llm_claim_ratio, 4),
            "verification": dict(self.verification),
            "caveats": list(self.caveats),
        }


def build_narration_request(lesson: Dict[str, Any]) -> Dict[str, Any]:
    """构造外部讲解器的输入。

    **只发事实，不发源码全文**：每个段给出它自己的行范围与"合法可引用的行范围"，
    讲解器据此写话；真正的代码摘录由讲解器按行号自己取不到 ——
    它只需要知道"这段在第几行到第几行"，而产品在合并时从磁盘读原文。
    """
    lesson = lesson if isinstance(lesson, dict) else {}
    segments: List[Dict[str, Any]] = []
    for segment in lesson.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        source = segment.get("source") if isinstance(segment.get("source"), dict) else {}
        segments.append(
            {
                "segment_id": str(segment.get("segment_id") or ""),
                "header_text": str(segment.get("header_text") or ""),
                "segment_kind": str(segment.get("segment_kind") or ""),
                "title": str(segment.get("title") or ""),
                "title_status": str(segment.get("title_status") or ""),
                "file": str(source.get("file") or ""),
                # 合法引用范围：模型只能在段内取证据
                "allowed_evidence_range": {
                    "start_line": int(source.get("start_line") or 0),
                    "end_line": int(source.get("end_line") or 0),
                },
                "branch_detail": segment.get("branch_detail"),
                "rule_based_bullets": [
                    str(c.get("claim_text") or "")
                    for c in (segment.get("must_remember") or [])
                    if isinstance(c, dict)
                ],
                "rule_based_summary": (
                    str((segment.get("one_sentence_summary") or {}).get("claim_text") or "")
                    if isinstance(segment.get("one_sentence_summary"), dict)
                    else ""
                ),
            }
        )
    return {
        "lesson_id": str(lesson.get("lesson_id") or ""),
        "capability_name": str(lesson.get("capability_name") or ""),
        "section_name": str(lesson.get("section_name") or ""),
        "title": str(lesson.get("title") or ""),
        "one_line_frame": str(lesson.get("one_line_frame") or ""),
        "segments": segments,
        "system_prompt": NARRATION_SYSTEM_PROMPT,
        "response_schema": NARRATION_RESPONSE_SCHEMA,
    }


def _segment_spans(lesson: Dict[str, Any]) -> Dict[str, Tuple[str, int, int]]:
    """``segment_id → (file, start_line, end_line)``。"""
    spans: Dict[str, Tuple[str, int, int]] = {}
    for segment in lesson.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        source = segment.get("source") if isinstance(segment.get("source"), dict) else {}
        spans[str(segment.get("segment_id") or "")] = (
            str(source.get("file") or ""),
            int(source.get("start_line") or 0),
            int(source.get("end_line") or 0),
        )
    return spans


def _read_excerpt(source_root: str, file_rel: str, start: int, end: int) -> Optional[str]:
    """**从磁盘读真实摘录** —— 绝不采用模型返回的代码文本。"""
    if not source_root or not file_rel:
        return None
    abs_path = os.path.join(source_root, file_rel.replace("/", os.sep))
    try:
        with open(abs_path, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    if not (1 <= start <= end <= len(lines)):
        return None
    return "\n".join(lines[start - 1 : end])


def _validate_citation(
    citation: Any,
    allowed: Tuple[str, int, int],
) -> Tuple[Optional[Dict[str, int]], str]:
    """校验一条引用是否落在允许范围内。返回 ``(范围, 失败原因)``。"""
    if not isinstance(citation, dict):
        return None, "引用格式不对（不是对象）"
    file_rel = str(citation.get("file") or "")
    try:
        start = int(citation.get("start_line") or 0)
        end = int(citation.get("end_line") or 0)
    except (TypeError, ValueError):
        return None, "行号不是整数"
    allowed_file, allowed_start, allowed_end = allowed
    if file_rel != allowed_file:
        return None, (
            f"引用文件越界：模型引用了 {file_rel!r}，"
            f"但它正在讲的这一段属于 {allowed_file!r}"
        )
    if not (start and end):
        return None, "缺少行号"
    if start < allowed_start or end > allowed_end or start > end:
        return None, (
            f"引用行范围越界：{start}-{end} 不在本段允许范围 "
            f"{allowed_start}-{allowed_end} 内"
        )
    return {"start_line": start, "end_line": end}, ""


def apply_narration(
    lesson: Dict[str, Any],
    narration: Optional[Dict[str, Any]],
    source_root: str,
) -> Tuple[Dict[str, Any], NarrationOutcome]:
    """把外部讲解合并进讲稿，逐条把关，然后**重跑校验器**。

    返回 ``(更新后的 lesson, 合并结果)``。``lesson`` 就地更新。
    """
    lesson = lesson if isinstance(lesson, dict) else {}
    outcome = NarrationOutcome(lesson_id=str(lesson.get("lesson_id") or ""))
    narration = narration if isinstance(narration, dict) else {}

    # 课 id 对不上 → 整体拒绝（防止把 A 课的讲解贴到 B 课上）
    incoming_lesson_id = str(narration.get("lesson_id") or "")
    if incoming_lesson_id and incoming_lesson_id != outcome.lesson_id:
        outcome.rejected.append(
            RejectedNarration(
                kind="lesson",
                text=incoming_lesson_id,
                reason=f"讲解的 lesson_id（{incoming_lesson_id}）与目标课（{outcome.lesson_id}）不一致",
            )
        )
        narration = {}

    spans = _segment_spans(lesson)
    segments_by_id = {
        str(s.get("segment_id") or ""): s
        for s in (lesson.get("segments") or [])
        if isinstance(s, dict)
    }

    total_claims = 0
    llm_claims = 0
    for segment in lesson.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        total_claims += len(segment.get("must_remember") or [])
        total_claims += len(segment.get("know_enough") or [])
        total_claims += 1 if segment.get("one_sentence_summary") else 0

    for item in narration.get("segments") or []:
        if not isinstance(item, dict):
            outcome.rejected.append(
                RejectedNarration(kind="segment", reason="段条目不是对象")
            )
            continue
        segment_id = str(item.get("segment_id") or "")
        if segment_id not in spans:
            outcome.rejected.append(
                RejectedNarration(
                    segment_id=segment_id, kind="segment",
                    reason="讲解指向了一个不存在的段 id",
                )
            )
            continue
        allowed = spans[segment_id]
        segment = segments_by_id[segment_id]

        # ---- 要点 ----
        for bullet in item.get("bullets") or []:
            if not isinstance(bullet, dict):
                continue
            text = str(bullet.get("text") or "").strip()
            if not text:
                continue
            citations = bullet.get("evidence") or []
            if not citations:
                outcome.rejected.append(
                    RejectedNarration(
                        segment_id=segment_id, kind="bullet", text=text,
                        reason="这条讲解没有给任何证据（产品规矩：无证据不入学生视图）",
                    )
                )
                continue
            merged_evidence: List[Dict[str, Any]] = []
            failure = ""
            for citation in citations:
                rng, failure = _validate_citation(citation, allowed)
                if rng is None:
                    break
                excerpt = _read_excerpt(
                    source_root, allowed[0], rng["start_line"], rng["end_line"]
                )
                if excerpt is None:
                    failure = (
                        f"引用行范围 {rng['start_line']}-{rng['end_line']} "
                        "在磁盘源码里取不到（文件缺失或越界）"
                    )
                    break
                # 摘录与哈希**由本模块从磁盘生成**，模型给的代码文本一律丢弃
                merged_evidence.append(
                    {
                        "file": allowed[0],
                        "start_line": rng["start_line"],
                        "end_line": rng["end_line"],
                        "symbol": "",
                        "excerpt": excerpt,
                        "excerpt_hash": sha256_text(excerpt),
                        "confidence": "verified",
                        "reason": "讲解层引用，由校验器从磁盘重读并复核",
                        "fact_id": "",
                    }
                )
            if failure or not merged_evidence:
                outcome.rejected.append(
                    RejectedNarration(
                        segment_id=segment_id, kind="bullet", text=text,
                        reason=failure or "没有任何一条引用通过校验",
                    )
                )
                continue

            claims = segment.setdefault("must_remember", [])
            claims.append(
                {
                    "claim_id": f"{segment_id}_llm{len(claims) + 1}",
                    "claim_text": text,
                    "category": "llm_narration",
                    "evidence": merged_evidence,
                    "confidence": "needs_review",
                    "verified": True,
                    "reject_reason": "",
                    "generated_by": GENERATED_BY_LLM,
                }
            )
            outcome.applied += 1
            llm_claims += 1

        # ---- 一句话总结 ----
        summary = item.get("summary")
        if isinstance(summary, dict):
            text = str(summary.get("text") or "").strip()
            citations = summary.get("evidence") or []
            if text and not citations:
                outcome.rejected.append(
                    RejectedNarration(
                        segment_id=segment_id, kind="summary", text=text,
                        reason="总结句没有给任何证据",
                    )
                )
            elif text:
                rng, failure = _validate_citation(citations[0], allowed)
                excerpt = (
                    _read_excerpt(source_root, allowed[0], rng["start_line"], rng["end_line"])
                    if rng
                    else None
                )
                if rng is None or excerpt is None:
                    outcome.rejected.append(
                        RejectedNarration(
                            segment_id=segment_id, kind="summary", text=text,
                            reason=failure or "引用的代码在磁盘上取不到",
                        )
                    )
                else:
                    original = segment.get("one_sentence_summary") or {}
                    segment["one_sentence_summary"] = {
                        "claim_id": f"{segment_id}_summary_llm",
                        "claim_text": text,
                        "category": "llm_narration",
                        "evidence": [
                            {
                                "file": allowed[0],
                                "start_line": rng["start_line"],
                                "end_line": rng["end_line"],
                                "symbol": "",
                                "excerpt": excerpt,
                                "excerpt_hash": sha256_text(excerpt),
                                "confidence": "verified",
                                "reason": "讲解层引用，由校验器从磁盘重读并复核",
                                "fact_id": "",
                            }
                        ],
                        "confidence": "needs_review",
                        "verified": True,
                        "reject_reason": "",
                        "generated_by": GENERATED_BY_LLM,
                        "rule_based_original": str(original.get("claim_text") or ""),
                    }
                    outcome.applied += 1
                    llm_claims += 1

    # ---- 标记来源与占比 ----
    review = lesson.get("review") if isinstance(lesson.get("review"), dict) else {}
    review["generated_by"] = GENERATED_BY_LLM
    review["narrator"] = str(narration.get("narrator") or "")
    review["narrator_model"] = str(narration.get("model") or "")
    review["llm_claim_ratio"] = round(
        llm_claims / (total_claims + llm_claims), 4
    ) if (total_claims + llm_claims) else 0.0
    lesson["review"] = review
    outcome.llm_claim_ratio = float(review["llm_claim_ratio"])

    # ---- 合并完必须重跑校验器（第 4 条把关规则）----
    updated = _verify.verify_and_apply(lesson, source_root)
    outcome.verification = dict(updated.get("verification") or {})

    outcome.caveats = [
        "讲解文字由外部模型生成（generated_by=llm_draft），**事实与摘录仍全部来自 AST 与磁盘源码**。",
        "模型返回的任何代码文本都被丢弃：讲稿里的每一段代码都是合并时从磁盘重读的。",
        "落不到段内证据上的讲解条目已被拦截，并保留在 rejected 清单里供评审查看。",
        "LLM 产物状态强制为 needs_review：它自己永远拿不到 can_publish=true，必须过教师确认。",
        "本模块不发任何网络请求；模型调用在后端服务里，且默认关闭。",
    ]
    return updated, outcome
