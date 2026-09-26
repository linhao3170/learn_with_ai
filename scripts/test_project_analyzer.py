"""
测试项目级分析引擎

⚠️ **这个脚本不许写学生快照**（`WO-04` 一轮根治的顺序陷阱，`docs/08` §19.1 第 22 条）
----------------------------------------------------------------------------
它以前把分析结果写回 `frontend/public/demo/project_analysis.json` —— 那正是
`scripts/build_demo_snapshots.py` 的学生快照。于是"先跑冒烟还是先跑产物脚本"
会改变学生在页面上看到的内容，只能靠人记得"跑完冒烟要重跑产物脚本"。

现在它只写 `validation/results/` 下的调试产物，并且**在同一次运行内**
跑前跑后各取一次学生快照的内容 sha256 与 mtime、断言逐个相同
（守卫本身也是验收的一部分）。
"""

import sys
import os
import json

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from engine.project_analyzer import ProjectAnalyzer
from scripts.build_demo_snapshots import (
    assert_student_snapshots_unchanged,
    student_snapshot_state,
)

#: 本脚本的调试产物（**不是**学生快照）：放到 gitignore 的 `validation/results/`，
#: 与 `test_deep_analyzer.py` 的 P0-15/P0-16 处理方式一致。
DEBUG_OUTPUT = os.path.join(REPO_ROOT, "validation", "results", "legacy_project_analysis.json")


def main():
    # 顺序陷阱守卫：跑之前先给全部学生快照取一次 sha256 + mtime
    snapshots_before = student_snapshot_state()

    project_path = os.path.join("sample_projects", "lab_safety_assistant")

    print("=" * 70)
    print("项目级业务逻辑分析引擎 - 测试")
    print("=" * 70)
    print(f"\n分析项目: {project_path}")

    analyzer = ProjectAnalyzer()
    result = analyzer.analyze(project_path)

    data = result.to_dict()
    # P0-11：答案不再随契约下发，判题答案只在后端（这里从结果对象里单独取，
    # 用来确认题目是可判定的）。
    answer_key = result.training_answer_key

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
    print("训练题（第 1~4 关；第 2 关每个够格的业务模块各一道，因此题数不固定）")
    print("=" * 70)
    tr = data["training"]
    print(f"\n  训练项目: {tr['project_name']}")
    print(f"  题目数: {len(tr['questions'])}")

    for index, q in enumerate(tr["questions"]):
        print(f"\n  【关卡 {q['level']}】{q['title']}")
        print(f"    类型: {q['question_type']}")
        print(f"    难度: {q['difficulty']}/5")
        print(f"    来源: {q.get('source', 'n/a')}")
        print(f"    题干: {q['description'][:80]}...")
        print(f"    选项数: {len(q['options'])}")
        key = answer_key.get(str(index), {})
        print(f"    正确答案（仅后端可见）: {', '.join(key.get('answers', []))}")
        print(f"    知识点: {', '.join(q['knowledge_points'])}")

    # 契约自检
    if result.training.get("questions") and any(
        "correct_answers" in q for q in result.training["questions"]
    ):
        print("\n  ⚠️ 契约里出现了 correct_answers —— 违反 P0-11！")

    # === 保存 JSON（调试产物，**不是学生快照**）===
    print("\n" + "=" * 70)
    os.makedirs(os.path.dirname(DEBUG_OUTPUT), exist_ok=True)
    with open(DEBUG_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n已保存到: {DEBUG_OUTPUT}")
    print(f"JSON 大小: {os.path.getsize(DEBUG_OUTPUT)} 字节")
    print("（学生快照 frontend/public/demo/ 下的产物不归本脚本写：")
    print("  它的唯一写出方是 scripts/build_demo_snapshots.py）")

    # === 顺序陷阱守卫：学生快照必须一个都没被写过 ===
    print("\n" + "=" * 70)
    assert_student_snapshots_unchanged(snapshots_before, context="scripts/test_project_analyzer.py")

    print("\n" + "=" * 70)
    print("  测试通过！项目级分析引擎工作正常")
    print("=" * 70)


if __name__ == "__main__":
    main()
