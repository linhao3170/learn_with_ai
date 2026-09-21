"""
实测验证报告生成器 —— 事实表核对 + 错误归类 + 自动汇总。

使用流程：
  1. 用 export_fact_table.py 生成事实表 CSV
  2. 在事实表中加一列 "is_error"（是=1，否=0/空）和 "error_type"（错误类型）
  3. 用本脚本生成验证报告

错误类型（参考 README2 D2-D4 核对表）：
  - module_miscluster    模块划分错误（聚类错了/漏了/多了）
  - call_missing         调用链遗漏
  - call_wrong           调用链错误（错调用/解析不了动态调用）
  - state_false_positive 状态读写误报
  - state_false_negative 状态读写漏报
  - module_desc_wrong    模块职责描述与代码不符
  - approach_wrong       实现思路推断错误（关键词贴标签导致的错判）
  - pattern_false_positive 设计模式误报
  - flow_missing         业务流程遗漏
  - flow_wrong           业务流程步骤错误
  - other                其他错误

使用方式：
  # 从已标记的事实表生成验证报告
  python scripts/validation_report.py --input validation/fact_table_marked.csv --output validation/report.md

  # 生成一个空的核对模板（带 is_error / error_type / notes 列）
  python scripts/validation_report.py --template --source validation/fact_table.csv --output validation/fact_table_template.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Tuple

# 修复 Windows 控制台中文/Unicode 编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


ERROR_TYPES = {
    "module_miscluster": "模块划分错误",
    "call_missing": "调用链遗漏",
    "call_wrong": "调用链错误",
    "state_false_positive": "状态读写误报",
    "state_false_negative": "状态读写漏报",
    "module_desc_wrong": "模块职责描述错误",
    "approach_wrong": "实现思路推断错误",
    "pattern_false_positive": "设计模式误报",
    "flow_missing": "业务流程遗漏",
    "flow_wrong": "业务流程步骤错误",
    "other": "其他错误",
}


@dataclass
class ValidationResult:
    """验证结果汇总。"""
    total_facts: int = 0
    total_errors: int = 0
    total_verified: int = 0  # verified 级别的事实数
    total_inferred: int = 0  # inferred 级别的事实数
    verified_errors: int = 0
    inferred_errors: int = 0

    errors_by_category: Dict[str, int] = field(default_factory=dict)
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    errors_by_source: Dict[str, int] = field(default_factory=dict)

    # 按类别统计错误率
    category_stats: Dict[str, Tuple[int, int]] = field(default_factory=dict)  # category -> (total, errors)

    error_details: List[dict] = field(default_factory=list)

    @property
    def overall_error_rate(self) -> float:
        if self.total_facts == 0:
            return 0.0
        return self.total_errors / self.total_facts

    @property
    def verified_error_rate(self) -> float:
        if self.total_verified == 0:
            return 0.0
        return self.verified_errors / self.total_verified

    @property
    def inferred_error_rate(self) -> float:
        if self.total_inferred == 0:
            return 0.0
        return self.inferred_errors / self.total_inferred


def read_facts(csv_path: str) -> List[dict]:
    """读取事实表 CSV。"""
    facts = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            facts.append(dict(row))
    return facts


def analyze_errors(facts: List[dict]) -> ValidationResult:
    """分析错误分布。"""
    result = ValidationResult()
    result.total_facts = len(facts)

    cat_totals: Dict[str, int] = defaultdict(int)
    cat_errors: Dict[str, int] = defaultdict(int)

    for fact in facts:
        category = fact.get("category", "未知")
        confidence = fact.get("confidence", "verified")
        source = fact.get("source", "未知")
        is_error = fact.get("is_error", "") or fact.get("error", "") or "0"
        error_type = fact.get("error_type", "") or ""

        # 计数
        cat_totals[category] += 1

        if confidence == "verified":
            result.total_verified += 1
        else:
            result.total_inferred += 1

        # 判断是否为错误
        is_err = str(is_error).strip() in ("1", "true", "True", "是", "Y", "y")
        if not is_err and error_type:
            # 只要填了错误类型就算错误
            is_err = True

        if is_err:
            result.total_errors += 1
            cat_errors[category] += 1

            if confidence == "verified":
                result.verified_errors += 1
            else:
                result.inferred_errors += 1

            # 错误类型统计
            et = error_type.strip() if error_type.strip() else "other"
            et_label = ERROR_TYPES.get(et, et)
            result.errors_by_type[et_label] = result.errors_by_type.get(et_label, 0) + 1

            # 按类别统计
            result.errors_by_category[category] = result.errors_by_category.get(category, 0) + 1

            # 按来源模块统计
            result.errors_by_source[source] = result.errors_by_source.get(source, 0) + 1

            # 错误详情
            result.error_details.append({
                "fact_id": fact.get("fact_id", ""),
                "category": category,
                "type": fact.get("type", ""),
                "description": fact.get("description", ""),
                "error_type": et_label,
                "notes": fact.get("notes", "") or fact.get("remark", "") or "",
            })

    # 按类别统计（总数和错误数）
    for cat in sorted(cat_totals.keys(), key=lambda c: -cat_errors[c]):
        result.category_stats[cat] = (cat_totals[cat], cat_errors[cat])

    return result


def generate_markdown_report(result: ValidationResult, project_name: str = "") -> str:
    """生成 Markdown 格式的验证报告。"""
    lines = []

    lines.append(f"# 实测验证报告")
    if project_name:
        lines.append(f"")
        lines.append(f"**项目：** {project_name}")
    lines.append("")
    lines.append(f"**验证日期：** {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 总体概览
    lines.append("## 一、总体概览")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| 事实总数 | {result.total_facts} |")
    lines.append(f"| 错误数 | {result.total_errors} |")
    lines.append(f"| **总体错误率** | **{result.overall_error_rate:.1%}** |")
    lines.append("")

    # 按可信度拆分
    lines.append("### 按可信度拆分")
    lines.append("")
    lines.append("| 可信度 | 总数 | 错误数 | 错误率 |")
    lines.append("|--------|------|--------|--------|")
    lines.append(
        f"| verified（确定性结论） | {result.total_verified} | "
        f"{result.verified_errors} | {result.verified_error_rate:.1%} |"
    )
    lines.append(
        f"| inferred（推断结论） | {result.total_inferred} | "
        f"{result.inferred_errors} | {result.inferred_error_rate:.1%} |"
    )
    lines.append("")

    # 按类别统计
    lines.append("## 二、按事实类别统计")
    lines.append("")
    lines.append("| 类别 | 总数 | 错误数 | 错误率 |")
    lines.append("|------|------|--------|--------|")
    for cat, (total, errors) in sorted(
        result.category_stats.items(), key=lambda x: -x[1][1]  # 按错误数降序
    ):
        rate = errors / total if total > 0 else 0
        lines.append(f"| {cat} | {total} | {errors} | {rate:.1%} |")
    lines.append("")

    # 错误类型分布
    lines.append("## 三、错误类型分布")
    lines.append("")
    lines.append("| 错误类型 | 数量 | 占比 |")
    lines.append("|----------|------|------|")
    sorted_types = sorted(result.errors_by_type.items(), key=lambda x: -x[1])
    for etype, count in sorted_types:
        pct = count / result.total_errors if result.total_errors > 0 else 0
        lines.append(f"| {etype} | {count} | {pct:.1%} |")
    lines.append("")

    # 按分析模块统计
    lines.append("## 四、按分析模块统计")
    lines.append("")
    lines.append("| 模块 | 错误数 |")
    lines.append("|------|--------|")
    for source, count in sorted(result.errors_by_source.items(), key=lambda x: -x[1]):
        lines.append(f"| {source} | {count} |")
    lines.append("")

    # 错误详情
    if result.error_details:
        lines.append("## 五、错误详情")
        lines.append("")
        # 按错误类型分组
        by_type: Dict[str, List[dict]] = defaultdict(list)
        for err in result.error_details:
            by_type[err["error_type"]].append(err)

        for etype in sorted(by_type.keys(), key=lambda t: -len(by_type[t])):
            errs = by_type[etype]
            lines.append(f"### {etype}（{len(errs)} 条）")
            lines.append("")
            lines.append("| ID | 类别 | 描述 | 备注 |")
            lines.append("|----|------|------|------|")
            for err in errs[:20]:  # 最多显示 20 条
                desc = err["description"][:60] + "..." if len(err["description"]) > 60 else err["description"]
                notes = err["notes"][:40] if err["notes"] else "-"
                lines.append(f"| {err['fact_id']} | {err['category']} | {desc} | {notes} |")
            if len(errs) > 20:
                lines.append(f"| ... | （还有 {len(errs) - 20} 条） | ... | ... |")
            lines.append("")

    # 结论与建议
    lines.append("## 六、结论与建议")
    lines.append("")

    overall = result.overall_error_rate
    if overall < 0.05:
        lines.append("- ✅ 总体错误率很低，引擎表现优秀")
    elif overall < 0.15:
        lines.append("- ⚠️ 总体错误率可控，主要集中在推断类结论")
    else:
        lines.append("- ❌ 总体错误率偏高，需重点关注")

    if result.inferred_error_rate > 0.3:
        lines.append("- ⚠️ 推断类结论（inferred）错误率较高，建议在 UI 上明确标注待确认")

    # 找出错误率最高的类别
    worst_cat = ""
    worst_rate = 0
    for cat, (total, errors) in result.category_stats.items():
        if total >= 5:  # 至少 5 条才算有统计意义
            rate = errors / total
            if rate > worst_rate:
                worst_rate = rate
                worst_cat = cat
    if worst_cat:
        lines.append(f"- 🎯 错误率最高的类别：**{worst_cat}**（{worst_rate:.1%}），建议优先优化")

    # 找出最常见的错误类型
    if sorted_types:
        top_type = sorted_types[0][0]
        lines.append(f"- 🔧 最常见的错误类型：**{top_type}**，可针对性改进对应模块")

    lines.append("")

    return "\n".join(lines)


def generate_template(source_path: str, output_path: str):
    """生成带核对列的空模板。"""
    facts = read_facts(source_path)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        # 原有列 + 核对列
        fieldnames = list(facts[0].keys()) if facts else Fact.headers()
        fieldnames += ["is_error", "error_type", "notes"]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for fact in facts:
            row = dict(fact)
            row["is_error"] = ""
            row["error_type"] = ""
            row["notes"] = ""
            writer.writerow(row)

    print(f"[OK] 核对模板已生成: {output_path}")
    print(f"     共 {len(facts)} 条事实，已添加 is_error / error_type / notes 列")
    print(f"")
    print(f"     错误类型可选值：")
    for code, name in ERROR_TYPES.items():
        print(f"       {code:<25} {name}")


# 简单的 Fact 列名引用（用于生成模板时的 fallback）
class Fact:
    @staticmethod
    def headers():
        return ["fact_id", "category", "type", "description", "location", "confidence", "evidence", "source"]


def main():
    parser = argparse.ArgumentParser(description="实测验证报告生成器")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", help="已标记错误的事实表 CSV 路径")
    group.add_argument("--template", action="store_true", help="生成核对模板")

    parser.add_argument("--source", help="模板模式下，源事实表 CSV 路径")
    parser.add_argument("--output", default="validation/report.md", help="输出文件路径")
    parser.add_argument("--project", default="", help="项目名称（用于报告标题）")
    parser.add_argument("--format", choices=["md", "json"], default="md", help="报告格式")

    args = parser.parse_args()

    if args.template:
        if not args.source:
            print("[!] 生成模板需要 --source 指定源事实表路径")
            sys.exit(1)
        generate_template(args.source, args.output)
        return

    # 生成报告
    print(f"[*] 读取事实表: {args.input}")
    facts = read_facts(args.input)
    print(f"    共 {len(facts)} 条事实")

    print("[*] 分析错误分布...")
    result = analyze_errors(facts)

    print(f"    错误数: {result.total_errors}")
    print(f"    总体错误率: {result.overall_error_rate:.1%}")
    print(f"    verified 错误率: {result.verified_error_rate:.1%}")
    print(f"    inferred 错误率: {result.inferred_error_rate:.1%}")

    if args.format == "json":
        import json
        report_data = {
            "project": args.project,
            "summary": {
                "total_facts": result.total_facts,
                "total_errors": result.total_errors,
                "overall_error_rate": result.overall_error_rate,
                "verified_error_rate": result.verified_error_rate,
                "inferred_error_rate": result.inferred_error_rate,
            },
            "errors_by_category": result.errors_by_category,
            "errors_by_type": result.errors_by_type,
            "errors_by_source": result.errors_by_source,
            "error_details": result.error_details,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        print(f"[OK] JSON 报告已保存: {args.output}")
    else:
        report = generate_markdown_report(result, args.project)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"[OK] Markdown 报告已保存: {args.output}")


if __name__ == "__main__":
    main()
