"""
文档打包器：把模块化文档按索引顺序拼成**单文件**，用于一次性投喂给 AI 助手

为什么需要它
------------
文档按「变更频率 + 读者」切成了十份（`docs/`），这对人和门禁都更好，
但"一次性交给 AI 做全面升级"往往只能给一个文件。于是本脚本按
`docs/00-index.md` 里那张清单的顺序把文档拼成 `docs/_bundle.md`：

- 顺序固定（入口 → 教学 → 架构 → 契约 → 接口 → 平台 → 手册 → 现状 → 债 → 纪律 → 存档），
  并在每份之间插入分隔标题，让模型知道"章节号属于哪一份"；
- 自动跳过 `_` 前缀的文件（`_bundle.md` 自己、`_TEMPLATE.md` 模板不参与打包）；
- 头部写清生成命令与总量统计，**文件本身是产物，不要手改**（`scripts/verify_docs.py` 不检查它）。

用法
----
    python scripts/pack_docs.py                    # → docs/_bundle.md
    python scripts/pack_docs.py --out docs/_x.md   # 指定输出
    python scripts/pack_docs.py --list             # 只列顺序与体量，不写文件

退出码：0 正常；1 = 索引里列了但磁盘上没有的文档（**先修文档再打包**）。
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
DOCS_DIR = REPO_ROOT / "docs"
INDEX = DOCS_DIR / "00-index.md"
DEFAULT_OUT = "docs/_bundle.md"

README = "README.md"

#: 排序：README 打头 → 索引 → 其余按文件名前缀（00/01/…/09/90）→ features 模板收尾
def ordered_docs() -> list[Path]:
    files = [REPO_ROOT / README, INDEX]
    files += sorted(
        p for p in DOCS_DIR.glob("*.md") if not p.name.startswith("_") and p != INDEX
    )
    template = DOCS_DIR / "features" / "_TEMPLATE.md"
    if template.is_file():
        files.append(template)
    return files


def index_mentions() -> set[str]:
    """从索引文件里抓出它列出的所有 `docs/*.md`（用于核对清单完整性）。

    过滤两类：占位路径（`docs/features/<功能>.md`）与 `_` 前缀的产物/模板
    （它们不参与打包，也不该被当成"缺文件"）。
    """
    if not INDEX.is_file():
        return set()
    text = INDEX.read_text(encoding="utf-8")
    found = set(re.findall(r"`(docs/[^`]+\.md)`", text))
    return {
        rel for rel in found
        if "<" not in rel and not Path(rel).name.startswith("_")
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把 docs/ 按索引顺序拼成单文件（供一次性交付）")
    parser.add_argument("--out", default=DEFAULT_OUT, help=f"输出路径（默认 {DEFAULT_OUT}）")
    parser.add_argument("--list", action="store_true", help="只列顺序与体量，不写文件")
    parser.add_argument("--no-readme", action="store_true", help="不打包 README.md")
    args = parser.parse_args(argv)

    files = ordered_docs()
    if args.no_readme:
        files = [p for p in files if p.name != "README.md"]

    missing = [p for p in files if not p.is_file()]
    if missing:
        for path in missing:
            print(f"[错误] 找不到 {path.relative_to(REPO_ROOT).as_posix()}")
        return 1

    listed = index_mentions()
    on_disk = {
        p.relative_to(REPO_ROOT).as_posix()
        for p in DOCS_DIR.rglob("*.md")
        if not p.name.startswith("_")
    }
    not_listed = sorted(on_disk - listed)
    listed_missing = sorted(listed - on_disk)

    print("打包顺序：")
    total_bytes = 0
    parts: list[str] = []
    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        total_bytes += len(text.encode("utf-8"))
        print(f"  {rel:<40} {len(text.splitlines()):>5} 行  {len(text.encode('utf-8')):>7} 字节")
        parts.append(f"\n\n<!-- ===== 以下来自 {rel} ===== -->\n\n" + text.rstrip("\n") + "\n")

    if not_listed:
        print("\n⚠️ 磁盘上存在但索引没列的文档（先补进 docs/00-index.md 的清单）：")
        for rel in not_listed:
            print(f"  - {rel}")
    if listed_missing:
        print("\n⚠️ 索引里列了但磁盘上没有的文档：")
        for rel in listed_missing:
            print(f"  - {rel}")

    if args.list:
        print(f"\n合计 {total_bytes} 字节（未写文件）")
        return 1 if listed_missing else 0

    header = (
        "<!-- 机器生成，请勿手改：python scripts/pack_docs.py -->\n\n"
        "# LearnWithAI · 文档全集（单文件打包）\n\n"
        f"> 由 `python scripts/pack_docs.py` 按 `docs/00-index.md` 的顺序拼成；含 {len(files)} 份文档、"
        f"{total_bytes} 字节。\n"
        "> **接手这个项目的 AI 助手请先读 `docs/00-index.md`（本文件第二部分）**："
        "里面有硬约束、门禁命令、完成定义与禁止事项。\n"
        "> 单个章节的实际归属看每段前的 `<!-- 以下来自 ... -->` 注释；章节号（`§16.1` 这类）在各文档间是连续的。\n"
    )
    out_path = REPO_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(header + "".join(parts), encoding="utf-8", newline="\n")
    print(f"\n已写入 {args.out}（{out_path.stat().st_size} 字节）")
    return 1 if listed_missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
