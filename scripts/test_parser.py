"""测试解析层是否工作正常"""

import sys, os

# 修复 Windows 终端编码问题
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.parser import parse_python


def main():
    with open(os.path.join("demo", "student_manager.py"), "r", encoding="utf-8") as f:
        code = f.read()

    print("=" * 60)
    print("解析测试: student_manager.py")
    print("=" * 60)

    result = parse_python(code)

    print(f"\n模块文档: {result.module_docstring[:60] if result.module_docstring else '无'}...")
    print(f"顶层函数: {len(result.functions)} 个")
    for f in result.functions:
        print(f"  - {f.name} (行 {f.start_line}-{f.end_line})")
        if f.docstring:
            print(f"    文档: {f.docstring[:50]}...")

    print(f"\n类: {len(result.classes)} 个")
    for c in result.classes:
        print(f"\n  类: {c.name} (行 {c.start_line}-{c.end_line})")
        print(f"    文档: {c.docstring[:50] if c.docstring else '无'}...")
        print(f"    方法数: {len(c.methods)}")
        for m in c.methods:
            flags = []
            if m.if_count > 0:
                flags.append(f"if={m.if_count}")
            if m.loop_count > 0:
                flags.append(f"loop={m.loop_count}")
            if m.try_count > 0:
                flags.append(f"try={m.try_count}")
            if m.raise_count > 0:
                flags.append(f"raise={m.raise_count}")
            flag_str = f" [{', '.join(flags)}]" if flags else ""
            print(f"      - {m.name} (行 {m.start_line}){flag_str}")

    print(f"\n导入: {len(result.imports)} 个")
    for imp in result.imports:
        print(f"  - {imp.module}: {imp.names} (行 {imp.line})")

    all_funcs = result.get_all_functions()
    print(f"\n所有函数总数: {len(all_funcs)}")

    # 测试代码片段获取
    print("\n--- 代码片段测试 (第 30-40 行) ---")
    snippet = result.get_code_snippet(30, 40)
    for i, line in enumerate(snippet.split("\n"), start=30):
        print(f"  {i:3d}: {line}")

    print("\n✅ 解析层测试通过！")


if __name__ == "__main__":
    main()
