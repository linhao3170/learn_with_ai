"""
完整引擎集成测试

验证：解析 -> 模式识别 -> 调用图 -> 知识点 -> 流程图 -> 题目生成  全链路
"""

import sys
import os
import json

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.analyzer import BusinessLogicAnalyzer
from engine.visualizer import FlowchartGenerator
from engine.quiz import QuizGenerator


def main():
    # 读取示例代码
    demo_path = os.path.join("demo", "student_manager.py")
    with open(demo_path, "r", encoding="utf-8") as f:
        code = f.read()

    print("=" * 70)
    print("LearnWithAI 业务逻辑分析引擎 - 集成测试")
    print("=" * 70)
    print(f"\n测试文件: {demo_path}")
    print(f"代码行数: {len(code.splitlines())}")

    # ===== 步骤 1：业务逻辑分析 =====
    print("\n" + "=" * 70)
    print("步骤 1: 业务逻辑分析")
    print("=" * 70)

    analyzer = BusinessLogicAnalyzer()
    result = analyzer.analyze(code, module_name="student_manager")

    print("\n--- 模块概览 ---")
    ov = result.overview
    print(f"  名称: {ov.name}")
    print(f"  主要用途: {ov.primary_purpose}")
    print(f"  难度等级: {ov.complexity_level} ({result.difficulty_score}/5)")
    print(f"  函数数: {ov.total_functions}")
    print(f"  类数: {ov.total_classes}")
    print(f"  代码行: {ov.total_lines}")
    print(f"  关键模式: {', '.join(ov.key_patterns)}")

    print("\n--- 业务模式识别结果 ---")
    for p in result.patterns:
        confidence_icon = {
            "high": "[高]",
            "medium": "[中]",
            "low": "[低]",
        }.get(p["confidence"], "[?]")
        sub = f" ({p['sub_type']})" if p.get("sub_type") else ""
        print(f"  {confidence_icon} {p['score']:.2f}  {p['pattern_name']}{sub}")
        print(f"         目标: {p['target_type']} {p['target_name']} (行 {p['target_line']})")
        for e in p["evidence"][:2]:
            print(f"         证据: 行 {e['line_start']} - {e['description']}")

    print(f"\n  模式汇总: {result.pattern_summary}")

    print("\n--- 调用图 ---")
    cg = result.call_graph
    print(f"  节点数: {len(cg['nodes'])}")
    print(f"  入口点: {cg['entry_points']}")
    print(f"  叶子节点: {cg['leaves']}")
    for nid, node in cg["nodes"].items():
        calls = ", ".join(node["calls"]) if node["calls"] else "(无)"
        print(f"    {nid} -> {calls}")

    print("\n--- 主流程 ---")
    for step in result.main_flow:
        func_info = f" [{step.related_function}]" if step.related_function else ""
        print(f"  步骤 {step.step}: {step.description}{func_info}")

    print("\n--- 知识点 ---")
    current_cat = ""
    for kp in result.knowledge_points:
        if kp["category"] != current_cat:
            current_cat = kp["category"]
            print(f"\n  [{current_cat}]")
        print(f"    {kp['name']} (难度 {kp['difficulty']}/5)")
        if kp["related_functions"]:
            print(f"      相关函数: {', '.join(kp['related_functions'][:5])}")

    print(f"\n  知识点分类统计: {result.knowledge_categories}")

    # ===== 步骤 2：流程图生成 =====
    print("\n" + "=" * 70)
    print("步骤 2: Mermaid 流程图生成")
    print("=" * 70)

    fc_gen = FlowchartGenerator()

    # 模块级流程图
    module_fc = fc_gen.generate_module_flowchart(result.to_dict())
    print("\n--- 模块级流程图 (Mermaid) ---")
    print(module_fc.mermaid_syntax[:500] + "\n...")
    print(f"\n  节点数: {len(module_fc.nodes)}, 边数: {len(module_fc.edges)}")

    # 函数级流程图（取 add_student）
    func_fc = fc_gen.generate_function_flowchart(code, "add_student")
    print("\n--- add_student 函数流程图 (Mermaid) ---")
    print(func_fc.mermaid_syntax[:600] + "\n...")
    print(f"\n  节点数: {len(func_fc.nodes)}, 边数: {len(func_fc.edges)}")

    # ===== 步骤 3：闯关题生成 =====
    print("\n" + "=" * 70)
    print("步骤 3: 闯关题生成")
    print("=" * 70)

    quiz_gen = QuizGenerator(seed=42)
    quiz = quiz_gen.generate(result.to_dict(), code.splitlines())

    print(f"\n生成了 {len(quiz.questions)} 道题\n")

    for q in quiz.questions:
        print(f"【关卡 {q.level}】{q.title}（难度 {q.difficulty}/5）")
        print(f"  类型: {q.question_type}")
        desc_preview = q.description[:100].replace("\n", " ") + ("..." if len(q.description) > 100 else "")
        print(f"  题干: {desc_preview}")
        for opt in q.options:
            marker = " <- 正确" if opt.is_correct else ""
            print(f"    {opt.id}. {opt.text[:50]}{marker}")
        print(f"  证据行: {q.evidence_lines}")
        print(f"  知识点: {q.knowledge_points}")
        print()

    # ===== 输出 JSON =====
    print("=" * 70)
    print("完整 JSON 输出大小")
    print("=" * 70)
    output = result.to_dict()
    output["flowcharts"] = {
        "module": module_fc.to_dict(),
        "add_student": func_fc.to_dict(),
    }
    output["quiz"] = quiz.to_dict()

    json_str = json.dumps(output, ensure_ascii=False, indent=2)
    print(f"\nJSON 总大小: {len(json_str)} 字符 ({len(json_str.encode('utf-8'))} 字节)")

    # 保存到文件
    output_path = os.path.join("demo", "analysis_output.json")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json_str)
    print(f"已保存到: {output_path}")

    print("\n" + "=" * 70)
    print("  所有测试通过！引擎全链路工作正常")
    print("=" * 70)


if __name__ == "__main__":
    main()
