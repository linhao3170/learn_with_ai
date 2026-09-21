"""
生成前端所需的完整分析数据 JSON

运行方式：
    python scripts/generate_web_data.py

会读取 demo/student_manager.py，生成完整分析结果（包括流程图），
然后保存到 frontend/public/demo/analysis_output.json
"""

import sys
import os
import json

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.analyzer import BusinessLogicAnalyzer
from engine.visualizer import FlowchartGenerator
from engine.quiz import QuizGenerator


def main():
    # 路径
    demo_code_path = os.path.join("demo", "student_manager.py")
    output_dir = os.path.join("frontend", "public", "demo")
    output_code_path = os.path.join(output_dir, "student_manager.py")
    output_json_path = os.path.join(output_dir, "analysis_output.json")

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 读取源码
    with open(demo_code_path, "r", encoding="utf-8") as f:
        code = f.read()

    print(f"源码: {demo_code_path} ({len(code.splitlines())} 行)")

    # 步骤 1：业务逻辑分析
    print("正在分析业务逻辑...")
    analyzer = BusinessLogicAnalyzer()
    result = analyzer.analyze(code, module_name="student_manager")
    output = result.to_dict()

    # 步骤 2：生成流程图
    print("正在生成流程图...")
    fc_gen = FlowchartGenerator()

    # 模块级流程图
    module_fc = fc_gen.generate_module_flowchart(output)
    output["flowcharts"] = {
        "module": module_fc.to_dict(),
        "functions": {},
    }

    # 每个函数的流程图
    for cls in output.get("classes", []):
        for method in cls.get("methods", []):
            try:
                func_fc = fc_gen.generate_function_flowchart(code, method["name"])
                key = cls["name"] + "." + method["name"]
                output["flowcharts"]["functions"][key] = func_fc.to_dict()
            except Exception as e:
                print(f"  警告: {cls['name']}.{method['name']} 流程图生成失败: {e}")

    for func in output.get("functions", []):
        try:
            func_fc = fc_gen.generate_function_flowchart(code, func["name"])
            output["flowcharts"]["functions"][func["name"]] = func_fc.to_dict()
        except Exception as e:
            print(f"  警告: {func['name']} 流程图生成失败: {e}")

    # 步骤 3：生成闯关题
    print("正在生成闯关题...")
    quiz_gen = QuizGenerator(seed=42)
    quiz = quiz_gen.generate(output, code.splitlines())
    output["quiz"] = quiz.to_dict()

    # 保存
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 复制源码文件到 public
    with open(output_code_path, "w", encoding="utf-8") as f:
        f.write(code)

    print(f"\n完成！输出已保存到:")
    print(f"  源码: {output_code_path}")
    print(f"  JSON: {output_json_path}")
    print(f"  JSON 大小: {os.path.getsize(output_json_path)} 字节")
    print(f"  模块级节点: {len(module_fc.nodes)}")
    print(f"  函数级流程图: {len(output['flowcharts']['functions'])} 个")
    print(f"  闯关题: {len(output['quiz'])} 道")


if __name__ == "__main__":
    main()
