"""
文档门禁：让「文档说的」与「代码/实跑事实」对不上时**当场报错**

为什么需要它（README 阶段 0）
------------------------------
这份仓库的纪律（README 开头）要求"没有同步文档的改动视为没做完"，但**没有机制**。
结果是实测出来的这几类漂移（2026-09-25 审计）：

- **版本号三个值并存**：README 里 `0.3.0` / `0.4.0` / `0.5.0`，代码是 `0.5.0`；
- **章节引用悬空**：`§7.7` 被引用 2 次，而 §七 是纯编号列表、根本没有 7.x 子节；
- **验收数字手抄 108 处**：其中 4 个已淘汰的值（`13/13` / `31/31` / `41/41` / `71/71`）
  仍留在正文 13 处，同一大章里同一脚本出现两个数字；
- **代码里的路径引用烂掉**：约 283 处指向**已删除**的 `README5` / `README4` / …。

本脚本把上面四类做成**可复跑的检查**（D1–D4），并给每一条 finding 打印
`文件:行号` 与一句"为什么"。退出码 1 = 有 ERROR。

| 编号 | 检查 | 严重度 |
|---|---|---|
| D1 | 文档里反引号包起来的**路径必须真实存在**（除非当行明写「待建 / 已删除 / 不存在…」或在允许清单里） | ERROR |
| D2 | `§X.Y` 与「第 N 章」引用必须解析到真实标题；代码里 `README §X.Y` 同样解析 | README ERROR / 代码 WARN |
| D3 | 文档里的**应用版本号**必须等于 `backend/app/main.py` 的 `version`（单一来源） | ERROR |
| D4 | 文档里的验收数字必须与 `validation/acceptance_latest.json` 一致；**已淘汰的旧总数**不许裸写 | ERROR |
| D5 | 拆分后每个 `docs/*.md` 必须有 `> 更新触发：` 行（现在还没有 docs/，为软检查） | WARN |
| D6 | `文件:行号` 引用必须**指得到东西**：行号不越界，且同一行里的路径/标识符要出现在该行号附近 | ERROR |
| D7 | **文档清单完整性**：`docs/` 下每份文档都要被 `docs/00-index.md` 与 `README.md` 提到，清单里写的路径必须真实存在 | ERROR |

D2 里对**已删除旧文档**的引用（`README5 §3.2` 这一类）目前只报 WARN 并计数 ——
它们要靠「稳定 ID 引用规范」在阶段 2 统一处理，本脚本先把规模钉住。

用法
----
    python scripts/verify_docs.py
    python scripts/verify_docs.py --list-unresolved-code-refs   # 列出全部代码侧悬空引用
    python scripts/verify_docs.py --max-per-check 20

退出码：0 = 没有 ERROR；1 = 有 ERROR。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

ACCEPTANCE_JSON = REPO_ROOT / "validation" / "acceptance_latest.json"
MAIN_PY = REPO_ROOT / "backend" / "app" / "main.py"

DOC_FILES: tuple[str, ...] = ("README.md",)
DOC_GLOBS: tuple[str, ...] = ("docs/**/*.md",)

CODE_GLOBS: tuple[str, ...] = (
    "engine/**/*.py",
    "backend/**/*.py",
    "scripts/**/*.py",
    "scripts/**/*.mjs",
    "frontend/src/**/*.vue",
    "frontend/src/**/*.js",
)

#: 扫描仓库文件时永远跳过的目录
SKIP_DIRS = {
    "node_modules",
    ".venv",
    ".git",
    "__pycache__",
    ".smoke-dist",
    "dist",
    "validation/flask",
    "validation/urllib3",
}

#: 「这一行明写了它不存在」→ 不算漏报（标记必须与路径同一行，防止"没做也蒙混过关"）
MISSING_MARKERS: tuple[str, ...] = (
    "待建",
    "未建",
    "还没建",
    "还没做",
    "尚未建",
    "未创建",
    "未开始",
    "待实现",
    "尚未实现",
    "已删除",
    "已删",
    "不存在",
    "已移出",
    "已清理",
    "读完即删",
    "用完即删",
    "改名",
    "丢失",
)

#: `_` 前缀的文件不参与文档检查：`_bundle.md` 是打包产物、`_TEMPLATE.md` 是模板
GENERATED_DOC_PREFIX = "_"

#: 文档清单（manifest）必须列全每一份文档；这两份是"入口"，都要提到它
MANIFEST_DOCS = ("docs/00-index.md", "README.md")

#: 旧文档（已按附录 C 处置）：引用它们只报 WARN，不计 ERROR
OLD_DOC_TOKENS: tuple[str, ...] = (
    "README1.md", "README2.md", "README3.md", "README4.md", "README5.md",
    "README.v1.md", "README.bak.md", "ENHANCEMENTS_GUIDE.md",
    "LearnWithAI优化升级方案V2.0.md",
    "web/index.html",
    "demo/analysis_output.json",
)

#: 明确的允许清单：(相对路径片段, 理由)——新增一条就要写一条理由
PATH_ALLOWLIST: tuple[tuple[str, str], ...] = (
    ("D:\\keshenji\\README1.md", "仓库外路径（附录 C 记录已移出），本脚本无法也不应检查"),
    ("fact_table.csv", "根目录那份已在附录 C.1 删除；现行的是 validation/fact_table.csv"),
    ("frontend/README.md", "Vite 脚手架说明，附录 C 记录已删除"),
)

#: 已淘汰的验收总数（裸写即算 ERROR；要写必须带历史标记）
RETIRED_TOTALS: dict[str, str] = {
    "13/13": "已被 14/14 取代（A11 加入后）",
    "31/31": "已被 53/53 取代（优先级 4 二轮扩展后）",
    "41/41": "已被 45/45 取代（离线走查新增 4 条设计层断言后）",
    "71/71": "已被 99/99 取代（在线走查新增 28 条阶段四断言后）",
}

#: 「这一行讲的是历史/轮次口径」→ 旧数字允许保留
HISTORY_MARKERS: tuple[str, ...] = (
    "历史",
    "旧值",
    "曾",
    "之前",
    "原先",
    "已被",
    "已淘汰",
    "由",
    "→",
    "Sprint 4 后",
    "Sprint 5 后",
    "一轮",
    "二轮",
)

PATH_SUFFIXES = (
    ".py", ".js", ".mjs", ".cjs", ".vue", ".json", ".md", ".csv",
    ".ps1", ".txt", ".html", ".jsonl", ".yml", ".yaml",
)

BACKTICK = re.compile(r"`([^`\n]+)`")
SECTION_REF = re.compile(r"§\s?(\d+(?:\.\d+)*)")
CHAPTER_REF = re.compile(r"第\s*([一二三四五六七八九十]+)\s*章")
CODE_README_REF = re.compile(r"README\s*§\s?(\d+(?:\.\d+)*)")
OLD_DOC_REF = re.compile(r"\bREADME([1-5]|\.v1|\.bak)\b")
VERSION_TOKEN = re.compile(r"`(\d+\.\d+\.\d+)`")
VERSION_CONTEXT = re.compile(r"(?:应用版本|后端版本|版本已升到|version)[^\n]{0,24}?(\d+\.\d+\.\d+)")
TOTAL_PAIR = re.compile(r"(\d+)\s*/\s*(\d+)(?!\d)")
SCRIPT_NAME = re.compile(r"([A-Za-z0-9_\-]+\.(?:py|mjs))")
LINE_LOCATION = re.compile(r"(?::\d+(?:-\d+)?)+(?![0-9])")


@dataclass
class Finding:
    check: str
    severity: str  # ERROR / WARN
    where: str
    message: str


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    def add(self, check: str, severity: str, where: str, message: str) -> None:
        self.findings.append(Finding(check, severity, where, message))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "ERROR"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "WARN"]


# ============================================================
# 索引与读取
# ============================================================

def iter_repo_files() -> list[Path]:
    files: list[Path] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        if any(rel.startswith(skip) or f"/{skip}/" in f"/{rel}" for skip in SKIP_DIRS):
            continue
        files.append(path)
    return files


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def doc_paths() -> list[Path]:
    found: list[Path] = []
    for name in DOC_FILES:
        candidate = REPO_ROOT / name
        if candidate.is_file():
            found.append(candidate)
    for pattern in DOC_GLOBS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            # `_bundle.md`（打包产物）与 `_TEMPLATE.md`（模板）不参与检查
            if path.name.startswith(GENERATED_DOC_PREFIX):
                continue
            found.append(path)
    return found


# ============================================================
# D7 · 文档清单完整性（每份文档都要被入口提到，索引里提到的都要存在）
# ============================================================

def check_manifest(report: Report, docs: list[Path]) -> None:
    doc_rels = {p.relative_to(REPO_ROOT).as_posix() for p in docs if p.name != "README.md"}
    for entry in MANIFEST_DOCS:
        entry_path = REPO_ROOT / entry
        if not entry_path.is_file():
            report.add("D7", "ERROR", entry, "入口文档不存在")
            continue
        text = entry_path.read_text(encoding="utf-8")
        for rel in sorted(doc_rels):
            if rel not in text:
                report.add(
                    "D7",
                    "ERROR",
                    entry,
                    f"文档 {rel} 没有被这份入口提到（新增/改名文档必须同步清单，否则读者与 AI 都看不见它）",
                )
        # 反向：索引里写的 docs/*.md 必须真实存在（占位路径 `<>`、通配 `*`、`_` 产物除外）
        for mentioned in sorted(set(re.findall(r"`(docs/[^`]+\.md)`", text))):
            if any(ch in mentioned for ch in "<>*"):
                continue
            if Path(mentioned).name.startswith(GENERATED_DOC_PREFIX):
                continue
            if not (REPO_ROOT / mentioned).is_file():
                report.add("D7", "ERROR", entry, f"清单里列的 {mentioned} 在磁盘上不存在（死指针）")


def chinese_number(text: str) -> int | None:
    digits = {"〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9}
    if not text:
        return None
    if text == "十":
        return 10
    if "十" in text:
        head, _, tail = text.partition("十")
        tens = digits.get(head, 1) if head else 1
        ones = digits.get(tail, 0) if tail else 0
        return tens * 10 + ones
    if len(text) == 1:
        return digits.get(text)
    return None


def read_heading_ids(path: Path) -> dict[str, int]:
    """把标题解析成引用用的 id：``## 八、`` → ``8``；``### 8.3`` → ``8.3``；``## 附录 A`` → ``附录A``。"""
    ids: dict[str, int] = {}
    for lineno, line in enumerate(read_lines(path), start=1):
        if not line.startswith("#"):
            continue
        text = line.lstrip("#").strip()
        numbered = re.match(r"^(\d+(?:\.\d+)*)[\s、.·]", text)
        if numbered:
            ids.setdefault(numbered.group(1), lineno)
            continue
        cn = re.match(r"^([〇零一二三四五六七八九十]+)\s*[、.]", text)
        if cn:
            value = chinese_number(cn.group(1))
            if value is not None:
                ids.setdefault(str(value), lineno)
            continue
        appendix = re.match(r"^附录\s*([A-Za-z0-9]+)", text)
        if appendix:
            ids.setdefault(f"附录{appendix.group(1).upper()}", lineno)
    return ids


def build_heading_index(docs: list[Path]) -> dict[str, str]:
    """全文档集的标题索引：``16.1`` → 它所在的那一份文档（阶段 1 起章节会跨文件）。

    阶段 1 的拆分**刻意保留原章节号**（`§16.1` 仍叫 16.1，只是搬进了 `docs/04-...`），
    所以引用解析必须在整个文档集上做，而不是只看 README。
    """
    index: dict[str, str] = {}
    for doc in docs:
        rel = doc.relative_to(REPO_ROOT).as_posix()
        for heading_id in read_heading_ids(doc):
            index.setdefault(heading_id, rel)
    return index


# ============================================================
# D1 · 文档里的路径必须存在
# ============================================================

def looks_like_path(token: str) -> bool:
    """只把**带位置的**写法当路径声明。

    裸文件名（``main.py``、``design_submission.json``）在正文里通常是「名字」而不是
    「位置」，硬查会把大量正常文字判成错误；带 ``/`` 的才当声明来查。
    """
    token = token.strip().strip("（）()「」,，。；;")
    if not token or " " in token:
        return False
    if token.startswith(("-", "http://", "https://", "?", "--", "../", "..\\")):
        return False
    if any(ch in token for ch in "<>{}*$|"):
        return False
    if "/" not in token and "\\" not in token:
        return False
    if token.endswith("/"):
        return True
    return token.endswith(PATH_SUFFIXES)


def candidate_tokens(span: str) -> list[str]:
    cleaned = LINE_LOCATION.sub("", span)
    tokens: list[str] = []
    for raw in re.split(r"\s+", cleaned):
        raw = raw.strip().strip("（）()「」,，。；;：:、")
        if not raw:
            continue
        # `scripts/foo.py:12` 已经在上面被剥掉行号；剩下的取路径部分
        raw = raw.split("#")[0]
        raw = raw.rstrip(".,;:)")
        if looks_like_path(raw):
            tokens.append(raw)
    return tokens


def resolve_token(token: str, index: dict[str, list[str]]) -> str | None:
    """返回命中的真实相对路径；``None`` = 找不到。"""
    if re.match(r"^[A-Za-z]:[\\/]", token) or token.startswith("/"):
        return "EXTERNAL"
    normalized = token.replace("\\", "/").lstrip("./")
    if (REPO_ROOT / normalized).exists():
        return normalized
    # 文档里的命令常先 `cd frontend` 再写相对路径（`node_modules/vite/bin/vite.js`），
    # 所以也按常见工作目录前缀试一遍。
    for prefix in ("frontend", "backend", "scripts"):
        if (REPO_ROOT / prefix / normalized).exists():
            return f"{prefix}/{normalized}"
    basename = normalized.rstrip("/").split("/")[-1]
    if not basename:
        return None
    stem = basename.rsplit(".", 1)[0].lower()
    if stem in PLACEHOLDER_STEMS:
        return "PLACEHOLDER"
    # 目录写法（`engine/design/`）与同名多份（证据源码副本）都算命中：
    # 这份检查要抓的是「写了却哪儿都没有」，不是「同名文件不止一处」。
    hits = index.get(basename, [])
    if hits:
        return hits[0]
    suffix_hits = [h for h in hits if h.endswith(normalized)]
    return suffix_hits[0] if suffix_hits else None


def check_paths(report: Report, docs: list[Path], index: dict[str, list[str]]) -> None:
    old_doc_hits = 0
    for doc in docs:
        rel_doc = doc.relative_to(REPO_ROOT).as_posix()
        for lineno, line in enumerate(read_lines(doc), start=1):
            for span in BACKTICK.findall(line):
                for token in candidate_tokens(span):
                    if any(fragment in token for fragment, _ in PATH_ALLOWLIST):
                        continue
                    if any(old in token for old in OLD_DOC_TOKENS):
                        old_doc_hits += 1
                        continue
                    if any(marker in line for marker in MISSING_MARKERS):
                        continue
                    if resolve_token(token, index) is None:
                        report.add(
                            "D1",
                            "ERROR",
                            f"{rel_doc}:{lineno}",
                            f"路径不存在：`{token}`（当行也没有「待建 / 已删除 / 不存在」这类标记）",
                        )
    if old_doc_hits:
        report.add(
            "D1",
            "WARN",
            f"{docs[0].relative_to(REPO_ROOT).as_posix()} 等",
            f"提到已按附录 C 处置的旧文档/旧产物 {old_doc_hits} 处（历史说明，不算缺陷）",
        )


# ============================================================
# D2 · 章节引用必须解析
# ============================================================

def check_section_refs(
    report: Report, docs: list[Path], heading_index: dict[str, str], max_items: int
) -> None:
    cross_file: dict[str, int] = {}
    for doc in docs:
        rel_doc = doc.relative_to(REPO_ROOT).as_posix()
        for lineno, line in enumerate(read_lines(doc), start=1):
            if "README5" in line or "README4" in line or "README3" in line or "README2" in line:
                continue  # 旧文档引用，另有 D2b 计数
            for ref in SECTION_REF.findall(line):
                base = ref.split(".")[0]
                target = heading_index.get(ref) or (
                    heading_index.get(base) if "." not in ref else None
                )
                if target is None:
                    report.add(
                        "D2",
                        "ERROR",
                        f"{rel_doc}:{lineno}",
                        f"章节引用解析不到：§{ref}（整个文档集里都没有这个标题）",
                    )
                    continue
                if target != rel_doc:
                    cross_file[target] = cross_file.get(target, 0) + 1
            for ref in CHAPTER_REF.findall(line):
                value = chinese_number(ref)
                target = heading_index.get(str(value)) if value is not None else None
                if target is None:
                    report.add(
                        "D2",
                        "ERROR",
                        f"{rel_doc}:{lineno}",
                        f"章节引用解析不到：第{ref}章",
                    )
                elif target != rel_doc:
                    cross_file[target] = cross_file.get(target, 0) + 1
    if cross_file:
        detail = "、".join(f"{path} ←{count} 处" for path, count in sorted(cross_file.items()))
        report.add(
            "D2",
            "WARN",
            "（跨文件引用）",
            f"拆分后仍靠「章节号不变」维持的跨文件引用：{detail}。"
            "阶段 3 会换成稳定 ID（R-/D-/A- 编号），免得再拆一次又断一片",
        )


def check_code_section_refs(report: Report, heading_index: dict[str, str], verbose: bool, max_items: int) -> None:
    heading_ids = set(heading_index)
    dangling_code: list[str] = []
    old_doc_hits: dict[str, int] = {}

    for pattern in CODE_GLOBS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            if any(skip in path.as_posix() for skip in SKIP_DIRS):
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            for lineno, line in enumerate(read_lines(path), start=1):
                for ref in CODE_README_REF.findall(line):
                    base = ref.split(".")[0]
                    if ref not in heading_ids and base not in heading_ids:
                        dangling_code.append(f"{rel}:{lineno} → README §{ref}")
                for name in OLD_DOC_REF.findall(line):
                    key = f"README{name}"
                    old_doc_hits[key] = old_doc_hits.get(key, 0) + 1

    for item in dangling_code[: max_items if not verbose else len(dangling_code)]:
        report.add("D2", "WARN", item.split(" ")[0], "代码里引用的 README 章节不存在（阶段 2 改稳定 ID 时一并处理）")
    if len(dangling_code) > (max_items if not verbose else len(dangling_code)):
        report.add("D2", "WARN", "（省略）", f"另有 {len(dangling_code) - max_items} 处代码侧悬空章节引用")

    total_old = sum(old_doc_hits.values())
    if total_old:
        detail = "、".join(f"{k}×{v}" for k, v in sorted(old_doc_hits.items()))
        report.add(
            "D2",
            "WARN",
            "（全仓库）",
            f"指向**已删除**旧文档的引用 {total_old} 处（{detail}）——这些指针今天无法解析，"
            "阶段 3 用稳定 ID（R-/D-/A- 编号）统一替换",
        )


# ============================================================
# D3 · 版本号单一来源
# ============================================================

def current_app_version() -> str:
    if not MAIN_PY.is_file():
        return ""
    match = re.search(r'version\s*=\s*"([^"]+)"', MAIN_PY.read_text(encoding="utf-8"))
    return match.group(1) if match else ""


def check_versions(report: Report, docs: list[Path]) -> None:
    expected = current_app_version()
    if not expected:
        report.add("D3", "WARN", "backend/app/main.py", "读不到应用版本，版本一致性检查被跳过")
        return
    for doc in docs:
        rel_doc = doc.relative_to(REPO_ROOT).as_posix()
        for lineno, line in enumerate(read_lines(doc), start=1):
            claimed = set(VERSION_TOKEN.findall(line)) | set(VERSION_CONTEXT.findall(line))
            for version in sorted(claimed):
                if version == expected:
                    continue
                if any(marker in line for marker in ("历史", "旧值", "已淘汰", "曾被", "由 `")):
                    continue
                report.add(
                    "D3",
                    "ERROR",
                    f"{rel_doc}:{lineno}",
                    f"版本号 `{version}` ≠ 代码里的 `{expected}`（来源 backend/app/main.py:81）",
                )


# ============================================================
# D4 · 验收数字必须与报告一致
# ============================================================

def load_acceptance() -> dict | None:
    if not ACCEPTANCE_JSON.is_file():
        return None
    try:
        return json.loads(ACCEPTANCE_JSON.read_text(encoding="utf-8"))
    except Exception:
        return None


#: 「脚本名」与「它的数字」之间**只允许出现标点与空白**。
#: 中文文档一行里常并列多组事实（"`test_business_graph.py`（161/161）、阶段一 22/22、…"），
#: 若按"最近的脚本名"归属，后面的 22/22 会被错算到脚本头上。
NUMBER_GAP = re.compile(r"^[`\s（()【\[*：:·—\-]*$")

#: 占位名（`scripts\xxx.py` 这类示例）不算路径声明
PLACEHOLDER_STEMS = {"xxx", "xx", "foo", "bar", "name", "example", "yourfile", "file"}


def attribute_pairs(line: str, scripts: list[tuple[str, int, int]]) -> list[tuple[str, str, str]]:
    """把一行里的 ``N/M`` 归属到**紧邻其前**的脚本名。

    判据：脚本名与该数字之间只有标点/空白（见 ``NUMBER_GAP``）。
    返回 ``[(脚本名, 数字, 原文片段), …]``；归属不到脚本的数字不返回
    （它们由规则 B「已淘汰总数」与人工复核负责）。
    """
    attributed: list[tuple[str, str, str]] = []
    for match in TOTAL_PAIR.finditer(line):
        label = f"{match.group(1)}/{match.group(2)}"
        best: tuple[str, int] | None = None
        for name, _start, end in scripts:
            if end > match.start():
                continue
            gap = line[end: match.start()]
            if not NUMBER_GAP.match(gap):
                continue
            if best is None or end > best[1]:
                best = (name, end)
        if best is not None:
            attributed.append((best[0], label, line[max(0, best[1] - 12): match.end() + 4]))
    return attributed


def check_numbers(report: Report, docs: list[Path]) -> None:
    payload = load_acceptance()
    if payload is None:
        report.add(
            "D4",
            "WARN",
            "validation/acceptance_latest.json",
            "没有验收报告，数字一致性检查被跳过 —— 先跑 `python scripts/build_acceptance_report.py`",
        )
        return

    by_script: dict[str, str] = {}
    for check in payload.get("checks", []):
        if check.get("total") is None:
            continue
        by_script[Path(check["script"].split()[0]).name] = f"{check['passed']}/{check['total']}"

    for doc in docs:
        rel_doc = doc.relative_to(REPO_ROOT).as_posix()
        for lineno, line in enumerate(read_lines(doc), start=1):
            # 规则 A：紧跟在脚本名后面的数字（≤40 字符）必须与验收报告一致
            scripts = [(m.group(1), m.start(), m.end()) for m in SCRIPT_NAME.finditer(line)]
            for script, label, context in attribute_pairs(line, scripts):
                expected = by_script.get(script)
                if expected is None or label == expected:
                    continue
                if any(marker in line for marker in HISTORY_MARKERS):
                    continue
                report.add(
                    "D4",
                    "ERROR",
                    f"{rel_doc}:{lineno}",
                    f"`{script}` 后面跟的数字是 {label}，验收报告里是 {expected}（原文：…{context.strip()}…）",
                )
            # 规则 B：已淘汰的旧总数不许裸写
            for passed, total in TOTAL_PAIR.findall(line):
                label = f"{passed}/{total}"
                if label not in RETIRED_TOTALS:
                    continue
                if any(marker in line for marker in HISTORY_MARKERS):
                    continue
                # `13/13` 现在是「13 个脚本全部通过」这个**另一个口径**的合法数字，
                # 所以按上下文放行（验收报告自己就是这么打印的）。
                if "脚本" in line and ("通过" in line or "个" in line):
                    continue
                report.add(
                    "D4",
                    "ERROR",
                    f"{rel_doc}:{lineno}",
                    f"旧总数 {label} 裸写（{RETIRED_TOTALS[label]}）；要么改成当前值，要么写明「历史：<轮次>」",
                )


# ============================================================
# D6 · `文件:行号` 引用必须指得到东西
# ============================================================

#: 文档里形如 `backend/app/main.py:255` / `main.py:81` / `TrainingView.vue:118` 的引用
FILE_LINE_REF = re.compile(r"`?([A-Za-z0-9_./\\\-]+\.(?:py|vue|js|mjs|json|md)):(\d+)(?:-(\d+))?`?")

#: 「锚点候选」：同一行里出现的路由片段（`teaching/module-card/task`）或长标识符（`grade_answer`）
ANCHOR_PATH = re.compile(r"[a-z][a-z0-9_\-]*(?:/[a-z0-9_\-]+){1,}")
ANCHOR_SYMBOL = re.compile(r"`([a-z_][a-z0-9_]{5,})`")

#: 引用的行号附近多少行内应能见到锚点
ANCHOR_WINDOW = 5


def _file_lines(rel: str) -> list[str] | None:
    path = REPO_ROOT / rel
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None


def check_line_refs(report: Report, docs: list[Path], index: dict[str, list[str]]) -> None:
    for doc in docs:
        rel_doc = doc.relative_to(REPO_ROOT).as_posix()
        for lineno, line in enumerate(read_lines(doc), start=1):
            for match in FILE_LINE_REF.finditer(line):
                raw, start = match.group(1), int(match.group(2))
                resolved = resolve_token(raw, index)
                if resolved in (None, "EXTERNAL", "PLACEHOLDER"):
                    continue
                lines = _file_lines(resolved)
                if lines is None:
                    continue
                if start > len(lines):
                    report.add(
                        "D6",
                        "ERROR",
                        f"{rel_doc}:{lineno}",
                        f"`{raw}:{start}` 越界：该文件只有 {len(lines)} 行",
                    )
                    continue
                # 锚点：同一行里的路径片段或长标识符，应当出现在被引行号附近。
                # 排除两类误报源：① 被引文件自己的名字；② 同一行提到的**别的**路径
                # （表格行常同时说"脚本 A 写文件 B"，B 不能当 A 的锚点）。
                ref_name = Path(raw).name
                other_paths = {
                    tok.rstrip("/")
                    for span in BACKTICK.findall(line)
                    for tok in candidate_tokens(span)
                }
                anchors = {a for a in ANCHOR_PATH.findall(line) if "/" in a and len(a) >= 8}
                anchors |= {s for s in ANCHOR_SYMBOL.findall(line) if len(s) >= 6}
                anchors = {
                    a for a in anchors
                    if ref_name not in a
                    and a not in raw
                    and not any(a.startswith(p) or p.startswith(a) for p in other_paths)
                }
                if not anchors:
                    continue
                window = "\n".join(lines[max(0, start - 1 - ANCHOR_WINDOW): start + ANCHOR_WINDOW])
                present_elsewhere = [a for a in anchors if a in "\n".join(lines) and a not in window]
                if present_elsewhere and not any(a in window for a in anchors):
                    report.add(
                        "D6",
                        "ERROR",
                        f"{rel_doc}:{lineno}",
                        f"`{raw}:{start}` 指错了地方：这一行的 `{present_elsewhere[0]}` "
                        f"在 ±{ANCHOR_WINDOW} 行内找不到（该文件里确实有它，说明行号过期）",
                    )


# ============================================================
# D5 · 拆分后每篇文档要有更新触发行（现在还没有 docs/，软检查）
# ============================================================

def check_docs_headers(report: Report, docs: list[Path]) -> None:
    for doc in docs:
        rel_doc = doc.relative_to(REPO_ROOT).as_posix()
        if not rel_doc.startswith("docs/"):
            continue
        head = "\n".join(read_lines(doc)[:8])
        if "更新触发" not in head:
            report.add("D5", "WARN", rel_doc, "缺 `> 更新触发：… | 上次更新：…` 行（拆分方案要求每篇都有）")


# ============================================================
# 入口
# ============================================================

def build_index() -> dict[str, list[str]]:
    """文件名 / 目录名 → 仓库里的相对路径（用于"只写名字不写位置"的引用）。"""
    index: dict[str, list[str]] = {}
    for path in iter_repo_files():
        index.setdefault(path.name, []).append(path.relative_to(REPO_ROOT).as_posix())
    for path in REPO_ROOT.rglob("*"):
        if not path.is_dir():
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        if any(skip in rel.split("/") for skip in SKIP_DIRS):
            continue
        index.setdefault(path.name, []).append(rel + "/")
    return index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="文档门禁：路径 / 章节引用 / 版本号 / 验收数字")
    parser.add_argument("--max-per-check", type=int, default=12, help="每类最多列几条（默认 12）")
    parser.add_argument("--list-unresolved-code-refs", action="store_true",
                        help="列出全部代码侧悬空章节引用（不止前 N 条）")
    args = parser.parse_args(argv)

    docs = doc_paths()
    report = Report()
    print("=" * 78)
    print("文档门禁（D1 路径 / D2 章节引用 / D3 版本号 / D4 验收数字 / D5 更新触发行）")
    print("=" * 78)
    print(f"检查文档：{', '.join(p.relative_to(REPO_ROOT).as_posix() for p in docs)}")
    print("检查代码引用：README §X.Y（代码）、已删除旧文档引用")

    index = build_index()
    heading_index = build_heading_index(docs)
    check_paths(report, docs, index)
    check_section_refs(report, docs, heading_index, args.max_per_check)
    check_code_section_refs(report, heading_index, args.list_unresolved_code_refs, args.max_per_check)
    check_versions(report, docs)
    check_numbers(report, docs)
    check_line_refs(report, docs, index)
    check_docs_headers(report, docs)
    check_manifest(report, docs)

    for check_id in ("D1", "D2", "D3", "D4", "D5", "D6", "D7"):
        items = [f for f in report.findings if f.check == check_id]
        errors = [f for f in items if f.severity == "ERROR"]
        warnings = [f for f in items if f.severity == "WARN"]
        print()
        print(f"--- {check_id}：ERROR {len(errors)} / WARN {len(warnings)} ---")
        for finding in (errors + warnings)[: args.max_per_check]:
            print(f"  [{finding.severity}] {finding.where}  {finding.message}")
        hidden = len(errors) + len(warnings) - args.max_per_check
        if hidden > 0:
            print(f"  …还有 {hidden} 条（--max-per-check 调大或看 --list-unresolved-code-refs）")

    print()
    print("=" * 78)
    print(f"结果：ERROR {len(report.errors)} 条 / WARN {len(report.warnings)} 条")
    print("=" * 78)
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
