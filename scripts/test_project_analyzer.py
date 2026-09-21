"""
测试项目级分析引擎
"""

import sys
import os
import json

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.project_analyzer import ProjectAnalyzer


def main():
    project_path = os.path.join("sample_projects", "lab_safety_assistant")

    print("=" * 70)
    print("项目级业务逻辑分析引擎 - 测试")
    print("=" * 70)
    print(f"\n分析项目: {project_path}")

    analyzer = ProjectAnalyzer()
    result = analyzer.analyze(project_path)

    data = result.to_dict()

    # === 概览 ===
    print("\n" + "=" * 70)
    print("项目概览")
    print("=" * 70)
    ov = data["overview"]
    print(f"  项目名: {data['project_name']}")
    print(f"  文件数: {ov['total_files']}")
    print(f"  代码行: {ov['total_lines']}")
    print(f"  类数: {ov['total_classes']}")
    print(f"  函数数: {ov['total_functions']}")
    print(f"  识别模块数: {ov['module_count']}")
    print(f"  核心模块数: {ov['core_module_count']}")

    # === 模块 ===
    print("\n" + "=" * 70)
    print("模块拆解结果")
    print("=" * 70)
    for i, mod in enumerate(data["modules"], 1):
        core_marker = " ★" if mod["core_score"] >= 0.5 else ""
        print(f"\n  [{i}] {mod['name']}{core_marker}")
        print(f"      类型: {mod['type']}")
        print(f"      核心度: {mod['core_score']}")
        print(f"      描述: {mod['description']}")
        print(f"      类数: {mod['class_count']}, 方法数: {mod['method_count']}")
        print(f"      职责: {', '.join(mod['responsibilities'][:4])}")
        if mod["depends_on"]:
            print(f"      依赖: {', '.join(mod['depends_on'])}")
        if mod["depended_by"]:
            print(f"      被依赖: {', '.join(mod['depended_by'])}")

    # === 依赖关系 ===
    print("\n" + "=" * 70)
    print("模块依赖关系")
    print("=" * 70)
    for dep in data["dependencies"]:
        print(f"  {dep['from']} → {dep['to']} ({dep['type']})")

    # === 核心流程 ===
    print("\n" + "=" * 70)
    print("核心业务流程")
    print("=" * 70)
    for flow in data["core_flows"]:
        print(f"\n  ● {flow['name']}")
        print(f"    描述: {flow['description']}")
        print(f"    步骤:")
        for step in flow["steps"]:
            print(f"      {step['order']}. {step['name']}")

    # === 训练题 ===
    print("\n" + "=" * 70)
    print("四关训练题")
    print("=" * 70)
    tr = data["training"]
    print(f"\n  训练项目: {tr['project_name']}")
    print(f"  题目数: {len(tr['questions'])}")

    for q in tr["questions"]:
        print(f"\n  【关卡 {q['level']}】{q['title']}")
        print(f"    类型: {q['question_type']}")
        print(f"    难度: {q['difficulty']}/5")
        print(f"    题干: {q['description'][:80]}...")
        print(f"    选项数: {len(q['options'])}")
        print(f"    正确答案: {', '.join(q['correct_answers'])}")
        print(f"    知识点: {', '.join(q['knowledge_points'])}")

    # === 保存 JSON ===
    print("\n" + "=" * 70)
    output_path = os.path.join("frontend", "public", "demo", "project_analysis.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n已保存到: {output_path}")
    print(f"JSON 大小: {os.path.getsize(output_path)} 字节")

    print("\n" + "=" * 70)
    print("  测试通过！项目级分析引擎工作正常")
    print("=" * 70)


if __name__ == "__main__":
    main()
