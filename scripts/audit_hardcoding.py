"""
audit_hardcoding.py —— 硬编码业务词审计器（README5 §3.2 / P0-12 的执行者）

规则来源
========
README5 §3.2「词典设计」定下一条硬规则：

    **`engine/lexicon/*.json` 是唯一允许出现业务词汇的地方。**

也就是说：`engine/**` 的 Python 代码里不允许再出现"预约""设备""安全检查""实验室"
这类**具体业务词**。引擎必须通过词典（verbs / entities / lifecycle / clusters）
做通用匹配，教师改词典就能适配自己学校的项目命名，而不需要改代码。

违反这条规则的后果（README5 §1.2-② / §1.3）：换个非中文、非这 8 类词汇的项目，
模块名就会错；而且"同一套引擎能分析任何业务域"的卖点会直接失效。
P0-12 的验收标准正是本脚本要自动化的事：

    grep -rn "预约|设备|安全检查|实验室" engine/ --include=*.py
    → 只允许命中 lexicon 加载器与注释

本脚本检查什么
==============
1. **引擎侧（失败即 exit 1）**：扫描 `engine/**/*.py`，跳过 `engine/lexicon/`
   （词汇的合法归属地）与 `__pycache__`。
   判定方式是 **AST**，不是 grep：
   - 收集所有字符串常量（`ast.Constant`）与所有标识符名（变量名、函数名、类名、
     参数名、属性名、关键字参数名、import 别名、global/nonlocal、except as 等）；
   - 注释天然不在 AST 里，因此被排除；
   - **所有 docstring（模块/类/函数的第一个字符串）也被排除**——文档可以谈业务词，
     代码不能。于是"文件顶部模块 docstring 里解释业务词"不会被误报；
   - 命中的字符串常量若是多行，行号按命中位置精确换算。
2. **前端侧（默认只 WARNING，不影响退出码）**：扫描 `frontend/src/**/*.vue` 与
   `frontend/src/**/*.js`。
   前端与引擎的判定标准**故意不同**：前端的"预约管理""安全隐患"这类中文文案
   有一部分是**合法的数据**（来自 `demo/*.json`、词典的中文名 `cn` 字段、
   教师审核后覆盖的模块名），不能因为出现业务词就判失败。因此：
   - 默认只检查 `<script setup>` / `<script>` 代码块内的行；
   - 实现手法：逐行剥离 `<!-- ... -->` HTML 注释后，再看该行是否含业务词
     （"任何含该词、且不在 HTML 注释里的行"）；
   - 加 `--frontend-include-template` 可把 `<template>` 里的静态文案也一并列为 WARNING；
   - 加 `--include-frontend` 才会让前端命中**也**导致 exit 1（严格模式）。
3. **已删除的写死干扰项**：`天气预报 / 物流配送 / 游戏娱乐 / 音乐播放 / 视频点播 /
   即时通讯`（P0-04 从训练题里删掉的域外干扰项）。这些词无论出现在引擎还是前端，
   都说明"四关固定题"的死数据又回来了。

退出码
======
0 = 通过（或仅有前端 WARNING 且未开 --include-frontend）
1 = 引擎侧有命中，或（开启了 --include-frontend 时）前端有命中，或存在无法解析/读取的文件

用法
====
    cd D:\\learn_with_ai
    python scripts/audit_hardcoding.py
    python scripts/audit_hardcoding.py --include-frontend
    python scripts/audit_hardcoding.py --frontend-include-template
    python scripts/audit_hardcoding.py --root <项目根目录>
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Set, Tuple


# ============================================================
# 词表
# ============================================================

#: 引擎代码里禁止出现的具体业务词（README5 §3.2：只能待在 engine/lexicon/*.json）
BUSINESS_TERMS: Tuple[str, ...] = (
    "预约",
    "设备",
    "实验室",
    "安全检查",
    "隐患",
    "库存",
    "订单",
    "借还",
)

#: P0-04 已删除的写死干扰项（域外业务名），任何地方再出现都是回退
REMOVED_DISTRACTOR_TERMS: Tuple[str, ...] = (
    "天气预报",
    "物流配送",
    "游戏娱乐",
    "音乐播放",
    "视频点播",
    "即时通讯",
)

ALL_TERMS: Tuple[str, ...] = BUSINESS_TERMS + REMOVED_DISTRACTOR_TERMS

#: 技术复合词豁免：中文没有词边界，"库存"会命中"数据库**库存**储"这类纯技术短语。
#: 只有在命中位置确实落在这些更长的技术复合词内部时才豁免，避免把技术描述当业务泄漏。
FALSE_POSITIVE_COMPOUNDS: Dict[str, Tuple[str, ...]] = {
    "库存": ("数据库存储", "数据库库存"),
}

#: 目录名：永远跳过
SKIP_DIR_NAMES = {"__pycache__", "node_modules", "dist", ".git"}

#: engine/ 下允许放词汇的子目录（README5 §3.2 指定的唯一归属地）
LEXICON_DIR_NAME = "lexicon"


# ============================================================
# 数据结构
# ============================================================

@dataclass(frozen=True)
class Hit:
    """一条命中记录。"""

    path: str          # 相对项目根的 POSIX 路径
    lineno: int        # 1-based 行号
    term: str          # 命中的业务词
    kind: str          # "string" / "identifier" / "frontend"
    detail: str        # 命中上下文摘要
    in_script: bool = True   # 仅前端：是否位于 <script> 块内

    def format(self) -> str:
        scope = "" if self.in_script else "  (template)"
        return f"{self.path}:{self.lineno}: {self.term}  [{self.kind}] {self.detail}{scope}"


# ============================================================
# 公共工具
# ============================================================

def _is_suppressed(term: str, text: str, index: int) -> bool:
    """命中位置是否落在已知技术复合词内部（误报豁免）。"""
    for compound in FALSE_POSITIVE_COMPOUNDS.get(term, ()):
        start = text.find(compound)
        while start != -1:
            if start <= index < start + len(compound):
                return True
            start = text.find(compound, start + 1)
    return False


def _find_terms(text: str) -> Iterator[Tuple[str, int]]:
    """产出 text 中每一处业务词的 (term, index)。"""
    for term in ALL_TERMS:
        start = 0
        while True:
            index = text.find(term, start)
            if index < 0:
                break
            start = index + len(term)
            if not _is_suppressed(term, text, index):
                yield term, index


def _snippet(text: str, index: int, term: str, width: int = 20) -> str:
    """截取命中处附近的上下文，压成一行。"""
    low = max(0, index - width)
    high = min(len(text), index + len(term) + width)
    body = " ".join(text[low:high].split())
    prefix = "..." if low > 0 else ""
    suffix = "..." if high < len(text) else ""
    return f"{prefix}{body}{suffix}"


def _rel_posix(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _iter_files(base: Path, suffixes: Sequence[str]) -> List[Path]:
    """递归收集指定后缀的文件，跳过 SKIP_DIR_NAMES。"""
    if not base.is_dir():
        return []
    found: List[Path] = []
    for item in sorted(base.rglob("*")):
        if not item.is_file():
            continue
        if item.suffix.lower() not in suffixes:
            continue
        if any(part in SKIP_DIR_NAMES for part in item.parts):
            continue
        found.append(item)
    return found


# ============================================================
# 引擎侧：AST 扫描
# ============================================================

def _docstring_constants(tree: ast.AST) -> Set[int]:
    """收集所有 docstring 常量节点的 id（模块 / 类 / 函数的第一条语句）。

    文档可以谈业务词，代码不能——所以这些字符串不参与判定。
    """
    ids: Set[int] = set()
    holders = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if not isinstance(node, holders):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            if isinstance(first.value.value, str):
                ids.add(id(first.value))
    return ids


def _identifier_of(node: ast.AST) -> Optional[str]:
    """取出节点里的标识符名（一个节点可能带多个，用空格连起来）。"""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.arg):
        return node.arg
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.keyword):
        return node.arg
    if isinstance(node, ast.alias):
        parts = [p for p in (node.name, node.asname) if p]
        return " ".join(parts) if parts else None
    if isinstance(node, (ast.Global, ast.Nonlocal)):
        return " ".join(node.names)
    if isinstance(node, ast.ExceptHandler):
        return node.name
    if isinstance(node, ast.MatchAs):
        return node.name
    if isinstance(node, ast.MatchStar):
        return node.name
    if isinstance(node, ast.MatchMapping):
        return node.rest
    return None


def scan_python_file(path: Path, rel: str) -> Tuple[List[Hit], List[str]]:
    """扫描一个 Python 文件，返回 (命中列表, 错误列表)。"""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [], [f"{rel}: 无法读取 ({exc})"]

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [], [f"{rel}:{exc.lineno}: SyntaxError: {exc.msg}"]

    hits: List[Hit] = []
    doc_ids = _docstring_constants(tree)

    for node in ast.walk(tree):
        # 1) 字符串常量（含 f-string 的各段）——注释与 docstring 不在其中
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in doc_ids
        ):
            for term, index in _find_terms(node.value):
                lineno = node.lineno + node.value.count("\n", 0, index)
                hits.append(Hit(rel, lineno, term, "string", _snippet(node.value, index, term)))

        # 2) 标识符名
        name = _identifier_of(node)
        if name:
            for term, index in _find_terms(name):
                lineno = getattr(node, "lineno", 0) or 0
                hits.append(Hit(rel, lineno, term, "identifier", f"`{name}`"))

    return hits, []


def scan_engine(engine_dir: Path, root: Path) -> Tuple[List[Hit], List[str], int]:
    """扫描 engine/**，跳过 engine/lexicon/ 与 __pycache__。"""
    hits: List[Hit] = []
    errors: List[str] = []
    files = _iter_files(engine_dir, (".py",))
    scanned = 0

    for path in files:
        rel_parts = path.relative_to(engine_dir).parts
        if rel_parts and rel_parts[0] == LEXICON_DIR_NAME:
            continue  # 词汇的合法归属地
        scanned += 1
        file_hits, file_errors = scan_python_file(path, _rel_posix(path, root))
        hits.extend(file_hits)
        errors.extend(file_errors)

    hits.sort(key=lambda h: (h.path, h.lineno, h.term))
    return hits, errors, scanned


# ============================================================
# 前端侧：script 块 + HTML 注释
# ============================================================

def _strip_html_comments(line: str, in_comment: bool) -> Tuple[str, bool]:
    """剥离一行里的 `<!-- ... -->`，返回 (清理后的文本, 行末是否仍在注释中)。

    支持同一行多个注释、以及跨行的注释块。
    """
    out: List[str] = []
    index = 0
    while index < len(line):
        if in_comment:
            end = line.find("-->", index)
            if end == -1:
                return "".join(out), True
            index = end + 3
            in_comment = False
        else:
            start = line.find("<!--", index)
            if start == -1:
                out.append(line[index:])
                break
            out.append(line[index:start])
            index = start + 4
            in_comment = True
    return "".join(out), in_comment


_SCRIPT_OPEN_RE = re.compile(r"<script\b", re.IGNORECASE)
_SCRIPT_CLOSE_RE = re.compile(r"</script\s*>", re.IGNORECASE)


def _script_block_flags(lines: Sequence[str]) -> List[bool]:
    """标记每一行是否位于 `<script>` / `<script setup>` 代码块内。"""
    flags: List[bool] = [False] * len(lines)
    inside = False
    for index, line in enumerate(lines):
        if not inside and _SCRIPT_OPEN_RE.search(line):
            inside = True
        flags[index] = inside
        if inside and _SCRIPT_CLOSE_RE.search(line):
            inside = False
    return flags


def scan_frontend_file(
    path: Path,
    rel: str,
    include_template: bool,
) -> Tuple[List[Hit], List[str]]:
    """扫描前端文件（`.vue` / `.js`）。

    判定标准见模块 docstring：默认只看 `<script>` 块内、且不在 `<!-- -->` 里的行。
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [], [f"{rel}: 无法读取 ({exc})"]

    lines = text.splitlines()
    is_vue = path.suffix.lower() == ".vue"
    script_flags = _script_block_flags(lines) if is_vue else [True] * len(lines)

    hits: List[Hit] = []
    in_comment = False
    for index, raw in enumerate(lines):
        cleaned, in_comment = _strip_html_comments(raw, in_comment)
        in_script = script_flags[index]
        if not in_script and not include_template:
            continue
        for term, position in _find_terms(cleaned):
            hits.append(
                Hit(rel, index + 1, term, "frontend", _snippet(cleaned, position, term), in_script)
            )
    return hits, []


def scan_frontend(
    frontend_dir: Path,
    root: Path,
    include_template: bool,
) -> Tuple[List[Hit], List[str], int]:
    """扫描 frontend/src/**/*.vue 与 *.js。"""
    hits: List[Hit] = []
    errors: List[str] = []
    files = _iter_files(frontend_dir, (".vue", ".js"))
    for path in files:
        file_hits, file_errors = scan_frontend_file(
            path, _rel_posix(path, root), include_template
        )
        hits.extend(file_hits)
        errors.extend(file_errors)
    hits.sort(key=lambda h: (h.path, h.lineno, h.term))
    return hits, errors, len(files)


# ============================================================
# 报告
# ============================================================

def _print_hits(title: str, hits: Sequence[Hit], indent: str = "  ") -> None:
    print(f"\n{title} ({len(hits)})")
    if not hits:
        print(f"{indent}- 无")
        return
    for hit in hits:
        print(f"{indent}{hit.format()}")


def build_report(
    engine_hits: Sequence[Hit],
    engine_errors: Sequence[str],
    engine_scanned: int,
    frontend_hits: Sequence[Hit],
    frontend_errors: Sequence[str],
    frontend_scanned: int,
    frontend_dir_exists: bool,
    include_frontend: bool,
    include_template: bool,
) -> int:
    """打印报告并返回退出码。"""
    line = "=" * 72
    print(line)
    print("硬编码业务词审计 (README5 §3.2 / P0-12)")
    print(f"业务词: {'、'.join(BUSINESS_TERMS)}")
    print(f"已删干扰项: {'、'.join(REMOVED_DISTRACTOR_TERMS)}")
    print(line)

    print(f"\n[引擎] 扫描 {engine_scanned} 个 .py 文件（已跳过 engine/{LEXICON_DIR_NAME}/、__pycache__）")
    if engine_errors:
        print(f"\n[引擎] 无法解析/读取的文件 ({len(engine_errors)}) —— 审计不完整，计为失败")
        for err in engine_errors:
            print(f"  ERROR {err}")
    _print_hits("[引擎] 命中（判定为失败）", engine_hits)

    print(f"\n[前端] 扫描 {frontend_scanned} 个 .vue/.js 文件（frontend/src/）")
    if not frontend_dir_exists:
        print("  - 目录不存在，跳过")
    if frontend_errors:
        print(f"\n[前端] 无法读取的文件 ({len(frontend_errors)})")
        for err in frontend_errors:
            print(f"  WARNING {err}")
    scope = "含 <template> 文案" if include_template else "仅 <script> 块内（且不在 <!-- --> 中）"
    _print_hits(f"[前端] WARNING 命中（{scope}）", frontend_hits, indent="  WARNING ")

    engine_failed = bool(engine_hits) or bool(engine_errors)
    frontend_failed = bool(frontend_hits) and include_frontend
    failed = engine_failed or frontend_failed

    print("\n" + line)
    print("汇总：")
    print(f"  引擎命中: {len(engine_hits)} 条，解析错误: {len(engine_errors)} 个")
    print(f"  前端命中: {len(frontend_hits)} 条（"
          f"{'计入失败，因为开启了 --include-frontend' if include_frontend else '仅提示，不计入失败'}）")

    if failed:
        reasons = []
        if engine_hits:
            reasons.append(f"引擎代码里有 {len(engine_hits)} 处硬编码业务词")
        if engine_errors:
            reasons.append(f"有 {len(engine_errors)} 个文件无法解析")
        if frontend_failed:
            reasons.append(f"前端有 {len(frontend_hits)} 处业务词（--include-frontend）")
        print(f"  结果: FAIL —— {'；'.join(reasons)}")
        print("  修法: 把业务词移入 engine/lexicon/*.json，引擎只做通用匹配（README5 §3.2）")
    else:
        print("  结果: PASS —— 引擎代码里没有硬编码业务词")
        if frontend_hits:
            print("  提示: 前端仍有业务词，但按约定只提示不失败（可能来自数据）")
    print(line)
    return 1 if failed else 0


# ============================================================
# 入口
# ============================================================

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="审计 engine/ 与 frontend/src/ 里是否又有硬编码业务词（README5 §3.2）",
    )
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parent.parent),
        help="项目根目录（默认：本脚本所在目录的上一级）",
    )
    parser.add_argument(
        "--include-frontend",
        action="store_true",
        help="前端命中也算失败（默认只 WARNING）",
    )
    parser.add_argument(
        "--frontend-include-template",
        action="store_true",
        help="前端检查也覆盖 <template> 里的静态文案（默认只看 <script> 块）",
    )
    parser.add_argument(
        "--engine-only",
        action="store_true",
        help="完全跳过前端检查",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    engine_dir = root / "engine"
    frontend_dir = root / "frontend" / "src"

    if not engine_dir.is_dir():
        print(f"找不到引擎目录: {engine_dir}", file=sys.stderr)
        return 1

    engine_hits, engine_errors, engine_scanned = scan_engine(engine_dir, root)

    if args.engine_only:
        frontend_hits: List[Hit] = []
        frontend_errors: List[str] = []
        frontend_scanned = 0
        frontend_dir_exists = frontend_dir.is_dir()
    else:
        frontend_hits, frontend_errors, frontend_scanned = scan_frontend(
            frontend_dir, root, args.frontend_include_template
        )
        frontend_dir_exists = frontend_dir.is_dir()

    return build_report(
        engine_hits=engine_hits,
        engine_errors=engine_errors,
        engine_scanned=engine_scanned,
        frontend_hits=frontend_hits,
        frontend_errors=frontend_errors,
        frontend_scanned=frontend_scanned,
        frontend_dir_exists=frontend_dir_exists,
        include_frontend=args.include_frontend,
        include_template=args.frontend_include_template,
    )


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())
