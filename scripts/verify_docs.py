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
| D1 | 文档里反引号包起来的**路径必须真实存在**（除非当行明写「待建 / 已删除 / 不存在…」、在允许清单里，或被 `.gitignore` 忽略） | ERROR / 被忽略的路径 WARN |
| D2 | `§X.Y` 与「第 N 章」引用必须解析到真实标题；代码里 `README §X.Y` 同样解析 | README ERROR / 代码 WARN |
| D3 | 文档里的**应用版本号**必须等于 `backend/app/main.py` 的 `version`（单一来源） | ERROR |
| D4 | 文档里的验收数字必须与 `validation/acceptance_latest.json` 一致；**已淘汰的旧总数**不许裸写 | ERROR |
| D5 | 拆分后每个 `docs/*.md` 必须有 `> 更新触发：` 行（现在还没有 docs/，为软检查） | WARN |
| D6 | `文件:行号` 引用必须**指得到东西**：行号不越界，且同一行里的路径/标识符要出现在该行号附近 | ERROR |
| D7 | **文档清单完整性**：`docs/` 下每份文档都要被 `docs/00-index.md` 与 `README.md` 提到，清单里写的路径必须真实存在 | ERROR |
| D8 | **六阶段状态表一致性**：`HomeView.vue` 的阶段状态表 ↔ `docs/07` §16.3 未开始清单 ↔ 页面自己的「还没做的」自述（实现见 `scripts/check_stage_consistency.py`） | ERROR |
| D9 | **口径文案 ↔ 引擎机制**：`engine/logic_platform/verification_manifest.json` ↔ `verify.py` 的 `CHECKS` / `narration.py` 的四条把关规则 ↔ 两个前端组件里的说明常量 | ERROR |

D1 的降级范围（`WO-04` 一轮加，理由写在代码里）
---------------------------------------------
被 `.gitignore` 忽略的路径（`node_modules/…`、`validation/results/`、`frontend/.smoke-dist/` 这类
**依赖与产物**）在每一个新建的 worktree / 克隆里**必然不存在**，而文档里写它们是对的 ——
不降级的话每条线的门禁永远是红的，而**永远红的门禁等于没有门禁**。
降级**只限"确实被 git 忽略"这一种**：真写错的普通路径仍然报 ERROR（有负向对照钉着）。

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
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
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


#: 文档里的命令常先 `cd frontend` 再写相对路径（`node_modules/vite/bin/vite.js`），
#: 所以解析与"是否被忽略"的判断都要试这几个常见工作目录前缀 —— **同一份清单，两处共用**。
RELATIVE_PARENT_PREFIXES: tuple[str, ...] = ("frontend", "backend", "scripts")

#: 剥掉 `./` **前缀**。
#:
#: ⚠️ 这里以前写的是 `lstrip("./")`，而 `str.lstrip` 剥的是**字符集合**而不是前缀：
#: `'.ai_orchestrator/'.lstrip('./')` 得到 `'ai_orchestrator/'`，于是**任何点开头的
#: 目录 / 文件**（`.ai_orchestrator` / `.venv` 这类写法）都会被判成「路径不存在」，
#: 而且报出来的话术看起来像"文档写错了"，排查会朝错的方向走。
#: 实测与影响面见 `docs/08` §19.1 第 28 条（`WO-04` 一轮修掉，并补了负向对照）。
LEADING_DOT_SLASH = re.compile(r"^(?:\./)+")


def normalize_token(token: str) -> str:
    """文档里的路径写法 → 仓库相对写法（**只剥前缀**，不碰路径中段）。"""
    return LEADING_DOT_SLASH.sub("", token.replace("\\", "/"))


def resolve_token(token: str, index: dict[str, list[str]]) -> str | None:
    """返回命中的真实相对路径；``None`` = 找不到。"""
    if re.match(r"^[A-Za-z]:[\\/]", token) or token.startswith("/"):
        return "EXTERNAL"
    normalized = normalize_token(token)
    if (REPO_ROOT / normalized).exists():
        return normalized
    # 文档里的命令常先 `cd frontend` 再写相对路径（`node_modules/vite/bin/vite.js`），
    # 所以也按常见工作目录前缀试一遍。
    for prefix in RELATIVE_PARENT_PREFIXES:
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


# ============================================================
# D1 的降级：被 .gitignore 忽略的路径只报 WARN（WO-04 一轮加）
# ============================================================
#
# 为什么：`node_modules/vite/bin/vite.js`、`validation/results/`、`frontend/.smoke-dist/`
# 这类路径在新 worktree / 新克隆里**必然不存在**（它们是依赖与构建产物，被 gitignore），
# 而文档里写它们是对的 —— 实测一个未改动的 `wave-0` worktree 上，D1 的 9 条 ERROR
# **全部**属于这一类。不降级的话，每条线的门禁永远是红的，而永远红的门禁等于没有门禁。
#
# 降级范围（写清楚，免得把真缺陷一起放过）：
#   - **只限"确实被 git 忽略"的路径** —— 不忽略的真写错的路径仍然报 ERROR；
#   - 判定用 `git check-ignore`，**问的是 git 自己**，不是本脚本猜一套模式；
#     （它在这个 Windows + `core.autocrlf=true` 的环境里有一个过宽的行为，见 `_git_ignored_paths`
#     里"空模式必须丢掉"那段 —— 已按实测证据挡掉）
#   - 判定时同时试 `frontend/` / `backend/` / `scripts/` 前缀（与 resolve_token 同口径），
#     因为文档里的 `node_modules/...` 其实就是从 `frontend/` 里写的；
#   - 拿不到 git（没装 / 不是仓库）→ 不降级，照旧 ERROR，并在摘要里说明。

GITIGNORE_TIMEOUT_SECONDS = 30


def _git_ignored_paths(candidates: list[str]) -> dict[str, str]:
    """问 git：这些路径里哪些被忽略？返回 ``{路径: ".gitignore:行号:模式"}``。

    输出重定向到临时文件再读 —— **不走管道**（§19.5：管道捕获原生程序输出会被拒）。
    """
    if not candidates:
        return {}
    handle, log_path = tempfile.mkstemp(prefix="lwai_gitignore_", suffix=".txt")
    os.close(handle)
    try:
        with open(log_path, "wb") as sink:
            completed = subprocess.run(
                [
                    "git",
                    "-c", f"safe.directory={REPO_ROOT.as_posix()}",
                    "-C", str(REPO_ROOT),
                    "check-ignore", "-v", "--", *candidates,
                ],
                stdin=subprocess.DEVNULL,
                stdout=sink,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=GITIGNORE_TIMEOUT_SECONDS,
            )
        # check-ignore：0 = 至少一个被忽略；1 = 一个都没有；其余 = 出错了
        if completed.returncode not in (0, 1):
            return {}
        text = Path(log_path).read_text(encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return {}
    finally:
        try:
            os.unlink(log_path)
        except OSError:  # pragma: no cover - 临时文件删不掉不该影响结论
            pass

    ignored: dict[str, str] = {}
    for line in text.splitlines():
        # 格式：`<.gitignore 路径>:<行号>:<模式>\t<被忽略的路径>`
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        origin, path = parts[0].strip(), parts[1].strip()
        pattern = origin.rpartition(":")[2]
        # ⚠️ **空模式必须丢掉**（`WO-04` 一轮实测到的过宽风险）
        #    `core.autocrlf=true` 的机器上，`git worktree add` 检出的 `.gitignore` 是 CRLF
        #    （主工作区里那份是 LF）。在这种 `.gitignore` 上，本机 git 会把**任何"不存在的
        #    目录写法"**（`examples/`、`docs/nope/`、`nonexistent_dir_xyz/`）都报成"被忽略"，
        #    而出处指向一个**空白行**（`.gitignore:76:` 后面什么都没有）。
        #    放它过去，等于把所有"写错的目录路径"都降级成 WARN —— 正是第 ⑤ 件要防的
        #    "把真缺陷一起放过"。所以：模式去空白后为空 → 不算忽略依据。
        if not pattern.strip():
            continue
        ignored[path] = origin
    return ignored


def ignored_reason(normalized: str, ignored: dict[str, str]) -> str | None:
    """这个（已归一化的）路径是否落在被 gitignore 的范围里？返回命中的候选写法。"""
    for candidate in (normalized, *(f"{p}/{normalized}" for p in RELATIVE_PARENT_PREFIXES)):
        if candidate in ignored:
            return f"{candidate}（{ignored[candidate]}）"
    return None


def check_paths(report: Report, docs: list[Path], index: dict[str, list[str]]) -> None:
    old_doc_hits = 0
    #: (文档, 行号, token) —— 先全部收集，最后**一次性**问 git（每个 token 起一个进程太慢）
    unresolved: list[tuple[str, int, str]] = []

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
                        unresolved.append((rel_doc, lineno, token))

    # 一次性把"归一化后的 token + 常见工作目录前缀写法"交给 git 判定
    candidates: set[str] = set()
    for _rel_doc, _lineno, token in unresolved:
        normalized = normalize_token(token)
        candidates.add(normalized)
        candidates.update(f"{prefix}/{normalized}" for prefix in RELATIVE_PARENT_PREFIXES)
    ignored = _git_ignored_paths(sorted(candidates))

    downgraded = 0
    for rel_doc, lineno, token in unresolved:
        reason = ignored_reason(normalize_token(token), ignored)
        if reason is not None:
            downgraded += 1
            report.add(
                "D1",
                "WARN",
                f"{rel_doc}:{lineno}",
                f"路径不在磁盘上，但它被 .gitignore 忽略：`{token}` → {reason} —— "
                "依赖 / 构建产物在新 worktree 与新克隆里必然不存在，这是环境事实不是文档缺陷"
                "（`WO-04` 一轮把这一类降级为 WARN；真写错的普通路径仍是 ERROR）",
            )
            continue
        report.add(
            "D1",
            "ERROR",
            f"{rel_doc}:{lineno}",
            f"路径不存在：`{token}`（当行也没有「待建 / 已删除 / 不存在」这类标记，且它没有被 .gitignore 忽略）",
        )

    if downgraded:
        report.add(
            "D1",
            "WARN",
            "（汇总）",
            f"其中 {downgraded} 条是**被 .gitignore 忽略**的依赖 / 产物路径（判据来自 `git check-ignore`，"
            "不是本脚本自己猜的模式）；它们在新 worktree 里必然不存在，所以只报 WARN",
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
# D8 · 六阶段状态表一致性（WO-04 门禁补强第 ② 件）
# ============================================================

def check_stage_consistency(report: Report) -> None:
    """把 `scripts/check_stage_consistency.py` 的三条规则就地跑一遍（S1/S2/S3）。

    抽成独立脚本是为了能单独跑、也能对着**别的文件**跑（负向对照用 `--home-view`）；
    这里只把它接进门禁，**不复制第二套判定**（否则就成了"两份实现"）。
    """
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from scripts import check_stage_consistency as stage_check
    except Exception as exc:  # pragma: no cover - 导入失败要如实报，不能静默跳过
        report.add(
            "D8", "ERROR", "scripts/check_stage_consistency.py",
            f"导入失败，六阶段状态表一致性没被检查：{exc!r}",
        )
        return
    for finding in stage_check.check():
        report.add("D8", finding.severity, finding.where, finding.message)


# ============================================================
# D9 · 口径文案 ↔ 引擎机制（WO-04 门禁补强第 ③ 件）
# ============================================================
#
# `docs/08` §19.1 第 26 条的缺口：讲稿与反幻觉面板上那些"机械复核到底检查了什么"的
# 说明，讲的是 `engine/logic_platform/` 里的机制。引擎改了检查项而前端文案没跟上，
# 页面就会**说错话**，而门禁抓不到 —— 原先只有一张人复核的对照表。
#
# 这里把那条链子变成可机器核对的（三段，每段都查）：
#
#     verify.py 的 CHECKS  →  verification_manifest.json 的 checks  →  两个组件里的说明常量
#
# **改文案不改断言**：任一段报红时，正确做法是改清单 / 改组件常量 / 改文案
# （`docs/08` §19.4 第 4 条：放宽断言比改一句文案危险得多）。

MANIFEST_PATH = REPO_ROOT / "engine" / "logic_platform" / "verification_manifest.json"
VERIFY_PY = REPO_ROOT / "engine" / "logic_platform" / "verify.py"
NARRATION_PY = REPO_ROOT / "engine" / "logic_platform" / "narration.py"

#: 说明文案的落点：**两个组件都要对同一台机器说同一句话**，所以两个都要查
MANIFEST_COMPONENT_FILES: tuple[str, ...] = (
    "frontend/src/components/logic-platform/ImmersiveLesson.vue",
    "frontend/src/components/logic-platform/VerificationPanel.vue",
)

#: 「四条把关规则」在 `narration.py` 模块 docstring 里的那一节的标题
NARRATION_RULES_SECTION = "把关规则（这才是重点）"

#: 规则条目形如 ``1. **模型只能给行号，不许给代码。**``
NARRATION_RULE_LINE = re.compile(r"^\s*\d+\.\s+\*\*(.+?)\*\*", re.M)

CAN_PUBLISH_STATEMENT = 'review["can_publish"] = False'


def _js_array_strings(source: str, const_name: str) -> list[str] | None:
    """取 ``const NAME = [ '...', ... ]`` 里的字符串（顺序原样返回）；找不到返回 None。"""
    match = re.search(rf"const\s+{re.escape(const_name)}\s*=\s*\[(.*?)\n\]", source, re.S)
    if not match:
        return None
    return re.findall(r"'([^']*)'", match.group(1))


def _js_string_const(source: str, const_name: str) -> str | None:
    match = re.search(rf"const\s+{re.escape(const_name)}\s*=\s*'([^']*)'", source)
    return match.group(1) if match else None


def _js_bool_const(source: str, const_name: str) -> bool | None:
    match = re.search(rf"const\s+{re.escape(const_name)}\s*=\s*(true|false)", source)
    return (match.group(1) == "true") if match else None


def _verify_py_checks() -> list[tuple[str, str]] | None:
    """用 `ast` **静态**读出 `verify.py` 的 `CHECKS`（不 import 引擎，避免副作用）。"""
    if not VERIFY_PY.is_file():
        return None
    try:
        tree = ast.parse(VERIFY_PY.read_text(encoding="utf-8"))
    except SyntaxError:
        return None
    for node in tree.body:
        if not isinstance(node, ast.AnnAssign) and not isinstance(node, ast.Assign):
            continue
        targets = [node.target] if isinstance(node, ast.AnnAssign) else list(node.targets)
        if not any(isinstance(t, ast.Name) and t.id == "CHECKS" for t in targets):
            continue
        try:
            value = ast.literal_eval(node.value)
        except ValueError:
            return None
        return [(str(item[0]), str(item[1])) for item in value]
    return None


def _narration_rule_summaries() -> list[str] | None:
    """取 `narration.py` 模块 docstring 里「把关规则」一节那几条的加粗原句。"""
    if not NARRATION_PY.is_file():
        return None
    try:
        tree = ast.parse(NARRATION_PY.read_text(encoding="utf-8"))
    except SyntaxError:
        return None
    docstring = ast.get_docstring(tree) or ""
    start = docstring.find(NARRATION_RULES_SECTION)
    if start < 0:
        return None
    return NARRATION_RULE_LINE.findall(docstring[start:])


def check_contract_wording(report: Report) -> None:
    """D9 主体：清单 ↔ 引擎 ↔ 组件说明常量，逐项比对。"""
    # ---- 0) 清单本身 ----
    if not MANIFEST_PATH.is_file():
        report.add(
            "D9", "ERROR", "engine/logic_platform/verification_manifest.json",
            "口径清单不存在：讲稿 / 反幻觉面板的说明文案失去了机器可核对的唯一来源",
        )
        return
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        report.add(
            "D9", "ERROR", "engine/logic_platform/verification_manifest.json",
            f"清单不是合法 JSON：{exc!r}",
        )
        return
    manifest_rel = "engine/logic_platform/verification_manifest.json"

    # ---- 1) 清单 source_of_truth 里写的文件必须真的在 ----
    for key, entry in (manifest.get("source_of_truth") or {}).items():
        rel = (entry or {}).get("file")
        if not rel:
            report.add("D9", "ERROR", manifest_rel, f"source_of_truth.{key} 没写 file")
            continue
        if not (REPO_ROOT / rel).is_file():
            report.add(
                "D9", "ERROR", manifest_rel,
                f"source_of_truth.{key} 指向的 `{rel}` 在磁盘上不存在（清单过期了）",
            )

    # ---- 2) 清单 checks ↔ verify.py 的 CHECKS ----
    engine_checks = _verify_py_checks()
    manifest_checks = manifest.get("checks") or []
    manifest_ids = [str(c.get("id") or "") for c in manifest_checks]
    manifest_names = [str(c.get("name") or "") for c in manifest_checks]
    manifest_summaries = [str(c.get("student_facing") or "") for c in manifest_checks]

    if engine_checks is None:
        report.add(
            "D9", "ERROR", "engine/logic_platform/verify.py",
            "读不出 `CHECKS`（结构变了？）—— 口径清单就失去了可比对的上游，请同步本检查",
        )
    else:
        engine_ids = [cid for cid, _ in engine_checks]
        engine_names = [name for _, name in engine_checks]
        if manifest_ids != engine_ids:
            report.add(
                "D9", "ERROR", manifest_rel,
                f"清单的检查项与引擎不一致：清单 {manifest_ids}，引擎 {engine_ids} —— "
                "引擎加了 / 删了检查项，清单与前端文案必须同轮跟上",
            )
        if manifest_names != engine_names:
            report.add(
                "D9", "ERROR", manifest_rel,
                f"清单里检查项的**名称**与引擎 `CHECKS` 不一致（同一条目同一下标必须同名）："
                f"清单 {manifest_names}，引擎 {engine_names}",
            )

    # ---- 3) 清单的四条把关规则 ↔ narration.py 的 docstring ----
    rules = manifest.get("narration_gating_rules") or []
    rule_ids = [str(r.get("id") or "") for r in rules]
    rule_summaries = [str(r.get("summary") or "") for r in rules]
    doc_rules = _narration_rule_summaries()
    if doc_rules is None:
        report.add(
            "D9", "ERROR", "engine/logic_platform/narration.py",
            f"读不出「{NARRATION_RULES_SECTION}」四条规则（改标题或改写法了？）—— 请同步本检查",
        )
    else:
        if len(doc_rules) != len(rule_summaries):
            report.add(
                "D9", "ERROR", manifest_rel,
                f"把关规则条数不一致：引擎 docstring 里 {len(doc_rules)} 条，清单里 {len(rule_summaries)} 条",
            )
        elif doc_rules != rule_summaries:
            report.add(
                "D9", "ERROR", manifest_rel,
                "把关规则的**原句**与引擎 docstring 不一致（清单里的 summary 必须逐字抄自引擎）："
                f"引擎 {doc_rules}，清单 {rule_summaries}",
            )
    declared_count = ((manifest.get("source_of_truth") or {}).get("narration_gating_rules") or {}).get("count")
    if declared_count != len(rules):
        report.add(
            "D9", "ERROR", manifest_rel,
            f"source_of_truth 里写的是 {declared_count} 条把关规则，实际列了 {len(rules)} 条",
        )

    # ---- 4) can_publish 恒假：清单声明的，与引擎源码里的那一行 ----
    can_publish = manifest.get("can_publish") or {}
    if can_publish.get("always_false") is not True:
        report.add("D9", "ERROR", manifest_rel, "清单没有声明 `can_publish.always_false = true`")
    if VERIFY_PY.is_file():
        verify_src = VERIFY_PY.read_text(encoding="utf-8")
        if CAN_PUBLISH_STATEMENT not in verify_src:
            report.add(
                "D9", "ERROR", "engine/logic_platform/verify.py",
                f"引擎里找不到 `{CAN_PUBLISH_STATEMENT}` —— 「引擎永远不把可发布置为真」这条口径"
                "已经与实现不符，前端文案与清单必须同轮改",
            )
    else:
        report.add("D9", "ERROR", "engine/logic_platform/verify.py", "文件不存在，can_publish 口径无法核对")

    # ---- 5) 清单 ↔ 两个组件里的说明常量 ----
    for rel in MANIFEST_COMPONENT_FILES:
        path = REPO_ROOT / rel
        if not path.is_file():
            report.add("D9", "ERROR", rel, "说明文案所在的组件不存在")
            continue
        source = path.read_text(encoding="utf-8")

        version = _js_string_const(source, "VERIFICATION_MANIFEST_VERSION")
        if version is None:
            report.add("D9", "ERROR", rel, "缺少常量 `VERIFICATION_MANIFEST_VERSION`（说明文案与清单的绑定关系断了）")
        elif version != str(manifest.get("manifest_version") or ""):
            report.add(
                "D9", "ERROR", rel,
                f"组件认的清单版本是 `{version}`，清单自己是 `{manifest.get('manifest_version')}` —— "
                "两边必须同时升，否则组件在读一份它不认识的清单",
            )

        ids = _js_array_strings(source, "VERIFIED_CHECK_IDS")
        if ids is None:
            report.add("D9", "ERROR", rel, "缺少常量 `VERIFIED_CHECK_IDS`")
        elif ids != manifest_ids:
            report.add(
                "D9", "ERROR", rel,
                f"组件声明的检查项与清单不一致：组件 {ids}，清单 {manifest_ids} —— "
                "**改文案，不是改断言**（docs/08 §19.4 第 4 条）",
            )

        summaries = _js_array_strings(source, "VERIFIED_CHECK_SUMMARIES")
        if summaries is None:
            report.add("D9", "ERROR", rel, "缺少常量 `VERIFIED_CHECK_SUMMARIES`")
        elif summaries != manifest_summaries:
            report.add(
                "D9", "ERROR", rel,
                "组件里逐项说明的措辞与清单 `student_facing` 不一致（同一下标必须同句）：\n"
                f"        组件 {summaries}\n        清单 {manifest_summaries}",
            )

        suffix = _js_string_const(source, "VERIFIED_CHECKS_SUFFIX")
        if suffix != str(manifest.get("checks_suffix") or ""):
            report.add(
                "D9", "ERROR", rel,
                f"`VERIFIED_CHECKS_SUFFIX` 与清单的 `checks_suffix` 不一致：组件 `{suffix}`，"
                f"清单 `{manifest.get('checks_suffix')}`",
            )

        rule_ids_in_component = _js_array_strings(source, "NARRATION_GATE_RULE_IDS")
        if rule_ids_in_component is None:
            report.add("D9", "ERROR", rel, "缺少常量 `NARRATION_GATE_RULE_IDS`")
        elif rule_ids_in_component != rule_ids:
            report.add(
                "D9", "ERROR", rel,
                f"四条把关规则的 id 不一致：组件 {rule_ids_in_component}，清单 {rule_ids}",
            )

        always_false = _js_bool_const(source, "CAN_PUBLISH_ALWAYS_FALSE")
        if always_false is None:
            report.add("D9", "ERROR", rel, "缺少常量 `CAN_PUBLISH_ALWAYS_FALSE`")
        elif always_false is not bool(can_publish.get("always_false")):
            report.add(
                "D9", "ERROR", rel,
                f"`CAN_PUBLISH_ALWAYS_FALSE = {always_false}`，清单是 {can_publish.get('always_false')}",
            )

        # 「说明是拼出来的」这件事本身也要钉住：否则常量还在、文案却已经被手抄成另一句，
        # 上面几条会全绿而页面照样说错话（这正是本检查要防的失败模式）。
        if "VERIFIED_CHECK_SUMMARIES.join('、')" not in source:
            report.add(
                "D9", "ERROR", rel,
                "说明文案不是由 `VERIFIED_CHECK_SUMMARIES.join('、')` 拼出来的 —— "
                "常量成了摆设：改引擎检查项时页面不会再跟着变（把逐项说明写成硬编码字符串就会这样）",
            )


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
    print("       （D6 行号锚点 / D7 文档清单 / D8 六阶段状态表 / D9 口径文案↔引擎机制）")
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
    check_stage_consistency(report)
    check_contract_wording(report)

    for check_id in ("D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9"):
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
