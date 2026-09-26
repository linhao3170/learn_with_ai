"""
完整引擎集成测试

验证：解析 -> 模式识别 -> 调用图 -> 知识点 -> 流程图 -> 题目生成  全链路

⚠️ 输出路径（`WO-04` 一轮根治的顺序陷阱，`docs/08` §19.1 第 22 条）
------------------------------------------------------------------
它以前把结果写到 **cwd 相对的** `demo/analysis_output.json`。从仓库根跑就落在根目录
那份过期副本上，从 `frontend/public` 跑就会**覆盖学生快照**
`frontend/public/demo/analysis_output.json`（App 的旧分析页真的在读它）——
同一个命令改不同的 cwd 就改不同的文件，这是典型的顺序陷阱。
现在输出固定写到 gitignore 的 `validation/results/` 下（与 `test_deep_analyzer.py`
的 P0-15/P0-16 一致），并在同一次运行内用 sha256 断言学生快照一个都没变。

注意：**输入**仍是 cwd 相对的 `demo/student_manager.py`（根目录与 `frontend/public`
下各有一份同样的文件）——它只读不写，所以不参与这个陷阱；改成绝对路径是另一件事，
本工单不动它（见交付说明的「仍未做」）。
"""

import sys
import os
import json

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from engine.analyzer import BusinessLogicAnalyzer
from engine.visualizer import FlowchartGenerator
from engine.quiz import QuizGenerator
from scripts.build_demo_snapshots import (
    assert_student_snapshots_unchanged,
    student_snapshot_state,
)

#: 调试产物路径（**绝对路径**，不随 cwd 变；**不是**学生快照）
DEBUG_OUTPUT = os.path.join(REPO_ROOT, "validation", "results", "legacy_full_engine_output.json")


def main():
    # 顺序陷阱守卫：跑之前先给全部学生快照取一次 sha256 + mtime
    snapshots_before = student_snapshot_state()

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

    # 保存到文件（绝对路径；不写学生快照）
    os.makedirs(os.path.dirname(DEBUG_OUTPUT), exist_ok=True)
    with open(DEBUG_OUTPUT, "w", encoding="utf-8") as f:
        f.write(json_str)
    print(f"已保存到: {DEBUG_OUTPUT}")
    print(f"（学生快照 frontend/public/demo/ 下的产物不归本脚本写：")
    print(f"  它的唯一写出方是 scripts/build_demo_snapshots.py）")

    # 顺序陷阱守卫：学生快照必须一个都没变
    assert_student_snapshots_unchanged(snapshots_before, context="scripts/test_full_engine.py")

    print("\n" + "=" * 70)
    print("  所有测试通过！引擎全链路工作正常")
    print("=" * 70)


if __name__ == "__main__":
    main()
