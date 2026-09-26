"""
六阶段状态表一致性检查（`WO-04` 门禁补强第 ② 件）

为什么需要它
------------
系统主页面（`frontend/src/views/HomeView.vue`）上有一张**六阶段状态表**：
每个阶段标 `已落地` 还是 `未开始`，**没落地的阶段不给按钮**（`disabled`，
`data-test="home-stage-todo"`）。这张表讲的是**项目事实**，不是页面自己的判断 ——
它的依据是 `docs/07-status-and-acceptance.md` §16.3 的「未开始」清单。

在此之前，"表里的状态"与"文档里的完成度"之间**没有任何机器守着**：
某条线把阶段三做完了、`status` 改成 `'done'`，却忘了删 §16.3 里那一行，
主页面就会同时说"阶段三已落地"和"阶段三未开始"——
这正是 `docs/features/ui-shell-redesign.md` §4 说的那种**假阳**（"把没做的说成做了"）。

检查什么（三条，全部可机器判定）
--------------------------------
| 编号 | 规则 | 反例 |
|---|---|---|
| S1 | `status: 'todo'` 的阶段**必须**能在 §16.3 里找到；`status: 'done'` 的阶段**不许**出现在 §16.3 里 | 阶段三做完了但 §16.3 还写着它 → 两处互相矛盾 |
| S2 | 主页面自己的「还没做的（如实列出）」抽屉里，`todo` 阶段必须被提到、`done` 阶段不许被提到 | 同一个文件里两句话打架 |
| S3 | 状态表必须覆盖**全部六个阶段**，且 `status` 只能是 `done` / `todo` | 表里漏掉阶段五；或出现一个第三态 `partial`（那要么补齐判定口径、要么写 `todo`） |

诚实边界（抓不到什么，如实写出来）
----------------------------------
- 它**只核"提到没提到"**，核不了那句话说得对不对（§16.3 的措辞、描述质量全靠人；
  同一份文档里 §16.1 / §16.2 对同一阶段的其他说法**不在本检查范围内**）。
- 阶段与文档词之间的对应关系是**人复核过的一张表**（`STAGE_DOC_KEYWORDS`）——
  新增一个阶段而没在这张表里登记，S1/S2 会报"没有登记指代词"，但**指代词选得准不准**
  仍然要靠人。
- 文档是**集成轮独占**的：本检查报红时，正确做法是让集成轮改 `docs/07`（或改前端表），
  **不许**把断言放宽（`docs/08` §19.4 第 4 条）。

用法
----
    python scripts/check_stage_consistency.py
    python scripts/check_stage_consistency.py --max-per-check 20

    # 给负向对照用：对着另一份 HomeView / 另一份状态文档跑（不改仓库里的文件）
    python scripts/check_stage_consistency.py --home-view <file> --status-doc <file>

退出码：0 = 一致；1 = 有 ERROR。

它也被 `scripts/verify_docs.py` 当作 **D8** 就地调用（一条门禁命令覆盖它）。
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]

HOME_VIEW = REPO_ROOT / "frontend" / "src" / "views" / "HomeView.vue"
STATUS_DOC = REPO_ROOT / "docs" / "07-status-and-acceptance.md"

#: §16.3 的标题（章节号刻意保留，见 `docs/00-index.md` 第二节的注）
STATUS_SECTION_HEADING = "### 16.3"

#: 「还没做的」抽屉的标题（主页面里那句自述）
TODO_GROUP_TITLE = "还没做的（如实列出）"

#: 阶段 key → 文档里指代它的词（**人复核过的对应关系**，两张文档都要能对上）
#: 每个词都必须能在两份文本里作为**阶段名**读通；改这里等于改检查口径，要写清理由。
STAGE_DOC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "orientation": ("阶段一", "项目认知"),
    "module-card": ("阶段二", "模块卡片"),
    "flow-sim": ("阶段三", "流程推演"),
    "design": ("阶段四", "设计画布"),
    "reconstruct": ("阶段六", "重构挑战"),
}

#: 状态表允许出现的取值（出现别的值必须停下来：要么补齐判定口径，要么写 todo）
ALLOWED_STATUS = ("done", "todo")

#: 六个阶段的编号必须都在表里出现（四 / 五 合并在同一行是刻意的，见 ui-shell-redesign）
REQUIRED_STAGE_NUMERALS = ("一", "二", "三", "四", "五", "六")

#: 从阶段名里取编号的两种写法：`阶段四`（独立一行）与 `阶段四 / 五`（合并行里那个裸编号）。
#: 合并行是刻意的（阶段四与阶段五同一条落地动线），所以这里**只认写法、不放宽要求**：
#: 六个编号少一个仍然报错。
NUMERAL_STANDALONE = re.compile(r"阶段([一二三四五六])")
NUMERAL_MERGED = re.compile(r"/\s*([一二三四五六])(?![一二三四五六])")

STAGES_ARRAY = re.compile(r"const TEACHING_STAGES = \[(.*?)\n\]", re.S)
STAGE_ENTRY = re.compile(r"\{[^{}]*?\bkey:\s*'([^']+)'(?:[^{}]*?)\}", re.S)
FIELD = {
    name: re.compile(rf"\b{name}:\s*'([^']*)'")
    for name in ("key", "name", "desc", "status")
}
EVIDENCE_GROUP = re.compile(
    rf"title:\s*'{re.escape(TODO_GROUP_TITLE)}',\s*lines:\s*\[(.*?)\],\s*\}}",
    re.S,
)
JS_STRING = re.compile(r"'([^']*)'")


@dataclass
class Finding:
    severity: str  # ERROR / WARN
    where: str
    message: str


@dataclass
class Stage:
    key: str
    name: str
    status: str
    where: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_stages(source: str, where: str) -> list[Stage]:
    """从 `HomeView.vue` 的 `TEACHING_STAGES` 里解析出阶段表。

    用"先切块、再逐字段取"的写法，而不是一个大正则 —— 少一个字段时要能**报出来**，
    而不是静默少解析一个阶段（那会让"表里漏了一个阶段"变成假绿）。
    """
    block_match = STAGES_ARRAY.search(source)
    if not block_match:
        return []
    block = block_match.group(1)

    stages: list[Stage] = []
    for index, chunk in enumerate(re.split(r"\n\s*\},\s*\n", block)):
        if "key:" not in chunk:
            continue
        values = {}
        for field, pattern in FIELD.items():
            found = pattern.search(chunk)
            values[field] = found.group(1) if found else ""
        stages.append(
            Stage(
                key=values["key"],
                name=values["name"],
                status=values["status"],
                where=f"{where}: TEACHING_STAGES[{index}]",
            )
        )
    return stages


def parse_todo_group_lines(source: str) -> list[str] | None:
    """取「还没做的（如实列出）」那一组抽屉里列出的句子；找不到返回 None。"""
    match = EVIDENCE_GROUP.search(source)
    if not match:
        return None
    return JS_STRING.findall(match.group(1))


def extract_status_section(doc: str) -> str | None:
    """取 `docs/07` §16.3（❌ 未开始）那一节到下一个 `### ` 标题之间的正文。"""
    start = doc.find(STATUS_SECTION_HEADING)
    if start < 0:
        return None
    rest = doc[start:]
    # 跳过标题行本身，再找下一个同级标题
    body_start = rest.find("\n")
    nxt = rest.find("\n### ", body_start + 1)
    return rest[body_start + 1 : nxt if nxt > 0 else len(rest)]


def check(
    home_view: Path = HOME_VIEW,
    status_doc: Path = STATUS_DOC,
) -> list[Finding]:
    """跑三条规则，返回 findings（ERROR 会让门禁 exit 1）。"""
    findings: list[Finding] = []
    home_rel = home_view.relative_to(REPO_ROOT).as_posix() if home_view.is_relative_to(REPO_ROOT) else str(home_view)
    doc_rel = status_doc.relative_to(REPO_ROOT).as_posix() if status_doc.is_relative_to(REPO_ROOT) else str(status_doc)

    if not home_view.is_file():
        findings.append(Finding("ERROR", home_rel, "阶段状态表所在的文件不存在"))
        return findings
    if not status_doc.is_file():
        findings.append(Finding("ERROR", doc_rel, "阶段完成度文档不存在"))
        return findings

    source = read_text(home_view)
    doc = read_text(status_doc)

    stages = parse_stages(source, home_rel)
    if not stages:
        findings.append(
            Finding("ERROR", home_rel, "解析不出 `TEACHING_STAGES` 阶段表（改名/改结构了？本检查会失效，必须同步改）")
        )
        return findings

    section = extract_status_section(doc)
    if section is None:
        findings.append(
            Finding("ERROR", doc_rel, f"找不到 `{STATUS_SECTION_HEADING}`（未开始清单）—— 章节号不许重排，请确认")
        )
        return findings

    todo_lines = parse_todo_group_lines(source)
    if todo_lines is None:
        findings.append(
            Finding(
                "ERROR",
                home_rel,
                f"找不到「{TODO_GROUP_TITLE}」那一组说明"
                "（它是主页面上的自我申报；删掉就等于没人再盯「把没做的说成做了」）",
            )
        )
        return findings

    # ---- S1 / S2：todo 必须在两处都出现、done 在两处都不许出现 ----
    for stage in stages:
        keywords = STAGE_DOC_KEYWORDS.get(stage.key)
        if not keywords:
            findings.append(
                Finding(
                    "ERROR",
                    stage.where,
                    f"阶段 `{stage.key}` 没有在 `STAGE_DOC_KEYWORDS` 里登记指代词 —— "
                    "新阶段必须先登记，否则本检查盯不住它",
                )
            )
            continue
        if stage.status not in ALLOWED_STATUS:
            findings.append(
                Finding(
                    "ERROR",
                    stage.where,
                    f"阶段 `{stage.key}` 的状态是 `{stage.status}`，不在允许取值 {ALLOWED_STATUS} 里 —— "
                    "要么补齐判定口径，要么如实写 todo",
                )
            )
            continue

        in_doc = any(kw in section for kw in keywords)
        in_todo_group = any(any(kw in line for kw in keywords) for line in todo_lines)

        if stage.status == "todo":
            if not in_doc:
                findings.append(
                    Finding(
                        "ERROR",
                        f"{stage.where} ↔ {doc_rel} {STATUS_SECTION_HEADING}",
                        f"状态表说 `{stage.key}`（{stage.name}）**未开始**，但 {doc_rel} 的未开始清单里"
                        f"找不到 {' / '.join(keywords)} —— 两处必须说同一件事",
                    )
                )
            if not in_todo_group:
                findings.append(
                    Finding(
                        "ERROR",
                        stage.where,
                        f"状态表说 `{stage.key}`（{stage.name}）**未开始**，但同一份文件里"
                        f"「{TODO_GROUP_TITLE}」没提到它 —— 页面自己两句话打架",
                    )
                )
        else:  # done
            if in_doc:
                findings.append(
                    Finding(
                        "ERROR",
                        f"{stage.where} ↔ {doc_rel} {STATUS_SECTION_HEADING}",
                        f"状态表说 `{stage.key}`（{stage.name}）**已落地**（页面会给按钮），"
                        f"但 {doc_rel} 的未开始清单里仍然写着 {' / '.join(keywords)} —— "
                        "这就是「把没做的说成做了」的反面：把做了的又说成没做，两处必须同步",
                    )
                )
            if in_todo_group:
                findings.append(
                    Finding(
                        "ERROR",
                        stage.where,
                        f"状态表说 `{stage.key}`（{stage.name}）**已落地**，但同一份文件里"
                        f"「{TODO_GROUP_TITLE}」仍然把它列成没做 —— 两句话必须同时改",
                    )
                )

    # ---- S3：六个阶段一个都不许漏 ----
    present: set[str] = set()
    for stage in stages:
        present.update(NUMERAL_STANDALONE.findall(stage.name))
        present.update(NUMERAL_MERGED.findall(stage.name))
    for numeral in REQUIRED_STAGE_NUMERALS:
        if numeral not in present:
            findings.append(
                Finding(
                    "ERROR",
                    home_rel,
                    f"阶段表里没有「阶段{numeral}」的编号 —— 六阶段必须一个不少"
                    "（阶段四 / 五 可以合并在同一行写成「阶段四 / 五」，但六个编号都要出现）",
                )
            )

    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="六阶段状态表 ↔ docs/07 §16.3 一致性检查")
    parser.add_argument("--home-view", default=str(HOME_VIEW), help="阶段状态表所在文件（默认 HomeView.vue）")
    parser.add_argument("--status-doc", default=str(STATUS_DOC), help="完成度文档（默认 docs/07）")
    parser.add_argument("--max-per-check", type=int, default=20, help="最多列几条（默认 20）")
    args = parser.parse_args(argv)

    home_view = Path(args.home_view)
    status_doc = Path(args.status_doc)
    if not home_view.is_absolute():
        home_view = REPO_ROOT / home_view
    if not status_doc.is_absolute():
        status_doc = REPO_ROOT / status_doc

    findings = check(home_view, status_doc)

    print("=" * 78)
    print("六阶段状态表一致性（S1 §16.3 / S2 页面自述 / S3 六阶段齐全）")
    print("=" * 78)
    print(f"阶段表：{home_view}")
    print(f"完成度：{status_doc}（{STATUS_SECTION_HEADING} ❌ 未开始）")

    errors = [f for f in findings if f.severity == "ERROR"]
    warnings = [f for f in findings if f.severity == "WARN"]
    print()
    for finding in (errors + warnings)[: args.max_per_check]:
        print(f"  [{finding.severity}] {finding.where}")
        print(f"      {finding.message}")
    hidden = len(errors) + len(warnings) - args.max_per_check
    if hidden > 0:
        print(f"  …还有 {hidden} 条")

    print()
    print("=" * 78)
    print(f"结果：ERROR {len(errors)} 条 / WARN {len(warnings)} 条")
    print("=" * 78)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
