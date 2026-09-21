"""
错误类型归类器

辅助工具，用于在 D2-D4 实测验证时记录和归类错误。

用法：
    1. 运行实测时，每发现一个错误，运行：
       python scripts/error_classifier.py add <项目名> <事实编号> <错误类型> <原因>

    2. 完成所有实测后，生成分布表：
       python scripts/error_classifier.py report

错误类型：
    - dynamic_call: 动态调用解析失败
    - module_boundary: 模块边界误判
    - pattern_false_positive: 设计模式误报
    - state_tracking_miss: 状态追踪漏报
    - semantic_inference: 语义推断错误
    - other: 其他

示例：
    python scripts/error_classifier.py add project_a 调用链#5 dynamic_call "getattr 动态调用"
    python scripts/error_classifier.py add project_b 模块#2 module_boundary "两个类在同一文件"
    python scripts/error_classifier.py report
"""

import sys
import json
import os
from collections import defaultdict
from datetime import datetime

ERROR_LOG_PATH = 'validation/error_log.json'
ERROR_TYPES = {
    'dynamic_call': {
        'name': '动态调用解析失败',
        'fixable': False,
        'reason': '架构限制：静态分析无法处理 getattr/eval/exec'
    },
    'module_boundary': {
        'name': '模块边界误判',
        'fixable': True,
        'reason': '聚类算法可优化，增加上下文权重'
    },
    'pattern_false_positive': {
        'name': '设计模式误报',
        'fixable': True,
        'reason': '已降级为 inferred，需教师确认'
    },
    'state_tracking_miss': {
        'name': '状态追踪漏报',
        'fixable': 'partial',
        'reason': '嵌套层级 >2 时追踪复杂度高'
    },
    'semantic_inference': {
        'name': '语义推断错误',
        'fixable': True,
        'reason': '命名启发式不准，已改为证据驱动'
    },
    'algorithm_inference': {
        'name': '算法类型推断错误',
        'fixable': True,
        'reason': '已标注为 inferred，附推断依据'
    },
    'cross_file_call': {
        'name': '跨文件调用追踪失败',
        'fixable': 'partial',
        'reason': '复杂导入路径难以解析'
    },
    'other': {
        'name': '其他',
        'fixable': 'unknown',
        'reason': '需具体分析'
    }
}


def load_errors():
    """加载错误日志"""
    if not os.path.exists(ERROR_LOG_PATH):
        return []
    with open(ERROR_LOG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_errors(errors):
    """保存错误日志"""
    os.makedirs(os.path.dirname(ERROR_LOG_PATH), exist_ok=True)
    with open(ERROR_LOG_PATH, 'w', encoding='utf-8') as f:
        json.dump(errors, f, ensure_ascii=False, indent=2)


def add_error(project, fact_id, error_type, reason):
    """添加一条错误记录"""
    if error_type not in ERROR_TYPES:
        print(f"错误：未知的错误类型 '{error_type}'")
        print(f"可用类型: {', '.join(ERROR_TYPES.keys())}")
        return 1

    errors = load_errors()
    errors.append({
        'project': project,
        'fact_id': fact_id,
        'error_type': error_type,
        'reason': reason,
        'timestamp': datetime.now().isoformat()
    })
    save_errors(errors)

    print(f"[OK] 已记录错误:")
    print(f"  项目: {project}")
    print(f"  事实: {fact_id}")
    print(f"  类型: {ERROR_TYPES[error_type]['name']}")
    print(f"  原因: {reason}")
    return 0


def generate_report():
    """生成错误分布报告"""
    errors = load_errors()

    if not errors:
        print("错误日志为空，尚未记录任何错误。")
        return 1

    total = len(errors)

    # 按类型统计
    by_type = defaultdict(int)
    by_project = defaultdict(int)

    for error in errors:
        by_type[error['error_type']] += 1
        by_project[error['project']] += 1

    # 生成 Markdown 表格
    print("\n" + "="*80)
    print("错误类型分布报告")
    print("="*80)
    print(f"\n总错误数: {total}")
    print(f"涉及项目: {len(by_project)}")
    print()

    # 分布表
    print("## 错误类型分布表\n")
    print("| 错误类型 | 出现次数 | 占比 | 是否可修 | 典型案例 |")
    print("|---------|---------|------|---------|---------|")

    sorted_types = sorted(by_type.items(), key=lambda x: -x[1])

    for error_type, count in sorted_types:
        percentage = count * 100 / total
        type_info = ERROR_TYPES.get(error_type, ERROR_TYPES['other'])

        fixable_icon = {
            True: '[OK] 可调优',
            False: '[X] 架构限制',
            'partial': '[!] 部分可修',
            'unknown': '-'
        }.get(type_info['fixable'], '-')

        # 找一个典型案例
        example = next((e for e in errors if e['error_type'] == error_type), None)
        example_text = example['reason'][:30] if example else '-'

        print(f"| {type_info['name']} | {count} | {percentage:.1f}% | {fixable_icon} | {example_text} |")

    # 按项目分布
    print("\n## 按项目分布\n")
    print("| 项目名 | 错误数 | 占比 |")
    print("|-------|-------|------|")

    for project, count in sorted(by_project.items(), key=lambda x: -x[1]):
        percentage = count * 100 / total
        print(f"| {project} | {count} | {percentage:.1f}% |")

    # 详细错误列表（前 20 条）
    print("\n## 详细错误列表（前 20 条）\n")
    print("| 项目 | 事实ID | 错误类型 | 原因分析 |")
    print("|------|--------|---------|---------|")

    for error in errors[:20]:
        type_name = ERROR_TYPES.get(error['error_type'], ERROR_TYPES['other'])['name']
        print(f"| {error['project']} | {error['fact_id']} | {type_name} | {error['reason']} |")

    if len(errors) > 20:
        print(f"\n... 还有 {len(errors) - 20} 条错误未显示")

    print("\n" + "="*80)

    # 导出 CSV
    csv_path = 'validation/error_distribution.csv'
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        import csv
        writer = csv.writer(f)
        writer.writerow(['错误类型', '出现次数', '占比(%)', '是否可修', '修复说明'])

        for error_type, count in sorted_types:
            percentage = count * 100 / total
            type_info = ERROR_TYPES.get(error_type, ERROR_TYPES['other'])
            fixable_text = {
                True: '可调优',
                False: '架构限制',
                'partial': '部分可修',
                'unknown': '待分析'
            }.get(type_info['fixable'], '未知')

            writer.writerow([
                type_info['name'],
                count,
                f"{percentage:.1f}",
                fixable_text,
                type_info['reason']
            ])

    print(f"\n[OK] CSV 报告已导出: {csv_path}")

    # 生成材料用的精简版
    summary_path = 'validation/error_summary_for_submission.md'
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("# 实测错误类型分析\n\n")
        f.write(f"**总错误数**: {total}\n\n")
        f.write(f"**测试项目数**: {len(by_project)}\n\n")
        f.write("## 错误类型分布\n\n")
        f.write("| 错误类型 | 出现次数 | 占比 | 是否可修 | 应对措施 |\n")
        f.write("|---------|---------|------|---------|----------|\n")

        for error_type, count in sorted_types:
            percentage = count * 100 / total
            type_info = ERROR_TYPES.get(error_type, ERROR_TYPES['other'])

            fixable_icon = {
                True: '✓',
                False: '✗',
                'partial': '!',
                'unknown': '-'
            }.get(type_info['fixable'], '-')

            f.write(f"| {type_info['name']} | {count} | {percentage:.1f}% | {fixable_icon} | {type_info['reason']} |\n")

        f.write("\n## 关键发现\n\n")
        f.write("1. **我们不回避错误**：以上所有错误都是在真实项目上实测发现的，每条都能回溯到具体案例。\n\n")

        fixable_count = sum(count for et, count in sorted_types if ERROR_TYPES.get(et, {}).get('fixable') == True)
        fixable_pct = fixable_count * 100 / total if total > 0 else 0
        f.write(f"2. **{fixable_pct:.1f}% 的错误可通过优化修复**，已列入改进计划。\n\n")

        unfixable_count = sum(count for et, count in sorted_types if ERROR_TYPES.get(et, {}).get('fixable') == False)
        unfixable_pct = unfixable_count * 100 / total if total > 0 else 0
        f.write(f"3. **{unfixable_pct:.1f}% 的错误是静态分析的架构限制**（动态调用、反射、eval），这是业界共识，我们在文档中明确标注。\n\n")

        f.write("4. **所有语义推断类结论已标注为 `inferred`**，前端用黄色显示，教师可逐条确认或拒绝。\n\n")

    print(f"[OK] 材料用摘要已导出: {summary_path}")
    print("\n提示：将 error_summary_for_submission.md 的内容复制到申报材料的'实测结果'章节")

    return 0


def list_types():
    """列出所有错误类型"""
    print("\n可用的错误类型：\n")
    for key, info in ERROR_TYPES.items():
        print(f"  {key:25s} - {info['name']}")
    print()
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    command = sys.argv[1]

    if command == 'add':
        if len(sys.argv) != 6:
            print("用法: python error_classifier.py add <项目名> <事实编号> <错误类型> <原因>")
            print("\n查看可用错误类型:")
            print("  python error_classifier.py types")
            return 1
        return add_error(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])

    elif command == 'report':
        return generate_report()

    elif command == 'types':
        return list_types()

    else:
        print(f"未知命令: {command}")
        print("可用命令: add, report, types")
        return 1


if __name__ == '__main__':
    sys.exit(main())
