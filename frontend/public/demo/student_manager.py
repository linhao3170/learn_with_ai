"""
学生管理系统 - 示例代码

用于测试业务逻辑分析引擎的演示样本。
典型的 CRUD + 数据验证 + 异常处理模式。
"""


class StudentManager:
    """学生信息管理器，支持增删改查和批量操作"""

    def __init__(self):
        self.students = {}
        self._next_id = 1

    def add_student(self, name: str, age: int, major: str = "未分配") -> int:
        """
        添加一个新学生

        Args:
            name: 学生姓名
            age: 年龄（必须在 0-150 之间）
            major: 专业

        Returns:
            新学生的 ID

        Raises:
            ValueError: 参数不合法时抛出
        """
        if not name or not isinstance(name, str):
            raise ValueError("姓名不能为空且必须为字符串")

        if not isinstance(age, int) or age < 0 or age > 150:
            raise ValueError(f"年龄不合法: {age}")

        student_id = self._next_id
        self.students[student_id] = {
            "name": name,
            "age": age,
            "major": major,
            "scores": {},
        }
        self._next_id += 1
        return student_id

    def delete_student(self, student_id: int) -> bool:
        """
        删除指定学生

        Args:
            student_id: 学生 ID

        Returns:
            删除成功返回 True

        Raises:
            KeyError: 学生不存在时抛出
        """
        if student_id not in self.students:
            raise KeyError(f"学生 {student_id} 不存在")
        del self.students[student_id]
        return True

    def update_student(self, student_id: int, **kwargs) -> bool:
        """
        更新学生信息

        Args:
            student_id: 学生 ID
            **kwargs: 要更新的字段（name, age, major）

        Returns:
            更新成功返回 True
        """
        if student_id not in self.students:
            raise KeyError(f"学生 {student_id} 不存在")

        student = self.students[student_id]
        for key, value in kwargs.items():
            if key == "age":
                if not isinstance(value, int) or value < 0 or value > 150:
                    raise ValueError(f"年龄不合法: {value}")
            if key in ("name", "age", "major"):
                student[key] = value
        return True

    def get_student(self, student_id: int) -> dict | None:
        """查询学生信息，不存在返回 None"""
        return self.students.get(student_id)

    def list_students(self, major: str | None = None) -> list[dict]:
        """
        列出所有学生，可按专业筛选

        Args:
            major: 专业筛选条件，None 表示全部

        Returns:
            学生信息列表
        """
        result = []
        for sid, info in self.students.items():
            if major and info["major"] != major:
                continue
            result.append({"id": sid, **info})
        return result

    def add_score(self, student_id: int, course: str, score: float) -> bool:
        """
        录入学生课程成绩

        Args:
            student_id: 学生 ID
            course: 课程名
            score: 分数（0-100）
        """
        if student_id not in self.students:
            raise KeyError(f"学生 {student_id} 不存在")

        if score < 0 or score > 100:
            raise ValueError(f"分数不合法: {score}")

        self.students[student_id]["scores"][course] = score
        return True

    def get_average_score(self, student_id: int) -> float:
        """
        计算学生的平均分

        Args:
            student_id: 学生 ID

        Returns:
            平均分（0 表示没有成绩）
        """
        student = self.get_student(student_id)
        if not student:
            raise KeyError(f"学生 {student_id} 不存在")

        scores = student["scores"]
        if not scores:
            return 0.0

        total = sum(scores.values())
        return total / len(scores)

    def count(self) -> int:
        """返回学生总数"""
        return len(self.students)

    def clear(self) -> None:
        """清空所有学生数据"""
        self.students.clear()
        self._next_id = 1


def load_from_file(filepath: str) -> StudentManager:
    """
    从 JSON 文件加载学生数据

    Args:
        filepath: JSON 文件路径

    Returns:
        加载了数据的 StudentManager 实例
    """
    import json

    manager = StudentManager()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        for item in data.get("students", []):
            sid = item["id"]
            manager.students[sid] = {
                "name": item["name"],
                "age": item["age"],
                "major": item.get("major", "未分配"),
                "scores": item.get("scores", {}),
            }
            if sid >= manager._next_id:
                manager._next_id = sid + 1
    except FileNotFoundError:
        # 文件不存在就返回空管理器
        pass
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 文件解析失败: {e}")

    return manager


def save_to_file(manager: StudentManager, filepath: str) -> None:
    """
    保存学生数据到 JSON 文件

    Args:
        manager: StudentManager 实例
        filepath: 保存路径
    """
    import json

    data = {"students": []}
    for sid, info in manager.students.items():
        data["students"].append({"id": sid, **info})

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
