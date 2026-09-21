"""
安全检查模块

负责安全检查项管理、检查记录、隐患整改跟踪。
"""

from datetime import datetime


class SafetyChecker:
    """安全检查核心类"""

    LEVEL_LOW = "low"        # 一般隐患
    LEVEL_MEDIUM = "medium"  # 较大隐患
    LEVEL_HIGH = "high"      # 重大隐患

    STATUS_OPEN = "open"            # 待整改
    STATUS_IN_PROGRESS = "fixing"   # 整改中
    STATUS_CLOSED = "closed"        # 已完成

    def __init__(self):
        self.check_items = {}  # id -> 检查项
        self._next_item_id = 1
        self.check_records = []  # 检查记录
        self._next_record_id = 1
        self.hazards = []  # 隐患台账
        self._next_hazard_id = 1

    def add_check_item(self, content: str, category: str,
                       standard: str = "", risk_level: str = "low") -> int:
        """
        添加安全检查项

        Args:
            content: 检查内容
            category: 检查类别（消防/用电/化学品/设备等）
            standard: 检查标准
            risk_level: 风险等级 low/medium/high
        """
        if not content:
            raise ValueError("检查内容不能为空")

        valid_levels = {self.LEVEL_LOW, self.LEVEL_MEDIUM, self.LEVEL_HIGH}
        if risk_level not in valid_levels:
            raise ValueError(f"非法风险等级: {risk_level}")

        item_id = self._next_item_id
        self.check_items[item_id] = {
            "id": item_id,
            "content": content,
            "category": category,
            "standard": standard,
            "risk_level": risk_level,
            "active": True,
        }
        self._next_item_id += 1
        return item_id

    def perform_check(self, lab_id: str, inspector: str,
                      results: dict[int, bool]) -> int:
        """
        执行一次安全检查

        Args:
            lab_id: 被检查的实验室
            inspector: 检查人员
            results: {检查项ID: 是否合格}

        Returns:
            检查记录 ID
        """
        if not results:
            raise ValueError("检查结果不能为空")

        total = len(results)
        passed = sum(1 for v in results.values() if v)
        failed = total - passed

        record_id = self._next_record_id
        record = {
            "id": record_id,
            "lab_id": lab_id,
            "inspector": inspector,
            "check_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total_items": total,
            "passed_count": passed,
            "failed_count": failed,
            "results": results,
            "score": int(passed / total * 100) if total > 0 else 0,
        }
        self.check_records.append(record)
        self._next_record_id += 1

        # 不合格项自动生成隐患
        for item_id, is_ok in results.items():
            if not is_ok and item_id in self.check_items:
                item = self.check_items[item_id]
                self._create_hazard(
                    lab_id=lab_id,
                    description=item["content"],
                    risk_level=item["risk_level"],
                    source_record=record_id,
                )

        return record_id

    def _create_hazard(self, lab_id: str, description: str,
                       risk_level: str, source_record: int = 0) -> int:
        """创建一条隐患记录"""
        hazard_id = self._next_hazard_id
        self.hazards.append({
            "id": hazard_id,
            "lab_id": lab_id,
            "description": description,
            "risk_level": risk_level,
            "status": self.STATUS_OPEN,
            "source_record": source_record,
            "created_at": datetime.now().strftime("%Y-%m-%d"),
            "responsible": "",
            "deadline": "",
            "fix_description": "",
            "closed_at": None,
        })
        self._next_hazard_id += 1
        return hazard_id

    def assign_hazard(self, hazard_id: int, responsible: str,
                      deadline: str) -> bool:
        """指派隐患整改责任人及期限"""
        hazard = self._find_hazard(hazard_id)
        if not hazard:
            raise KeyError(f"隐患 {hazard_id} 不存在")

        if hazard["status"] == self.STATUS_CLOSED:
            raise ValueError("已完成的隐患不能重新指派")

        hazard["responsible"] = responsible
        hazard["deadline"] = deadline
        hazard["status"] = self.STATUS_IN_PROGRESS
        return True

    def close_hazard(self, hazard_id: int, fix_description: str) -> bool:
        """完成隐患整改并关闭"""
        hazard = self._find_hazard(hazard_id)
        if not hazard:
            raise KeyError(f"隐患 {hazard_id} 不存在")

        if hazard["status"] == self.STATUS_CLOSED:
            raise ValueError("该隐患已关闭")

        hazard["fix_description"] = fix_description
        hazard["status"] = self.STATUS_CLOSED
        hazard["closed_at"] = datetime.now().strftime("%Y-%m-%d")
        return True

    def _find_hazard(self, hazard_id: int) -> dict | None:
        """查找隐患"""
        for h in self.hazards:
            if h["id"] == hazard_id:
                return h
        return None

    def get_hazards(self, lab_id: str | None = None,
                    status: str | None = None,
                    risk_level: str | None = None) -> list[dict]:
        """获取隐患列表，支持多条件筛选"""
        result = []
        for h in self.hazards:
            if lab_id and h["lab_id"] != lab_id:
                continue
            if status and h["status"] != status:
                continue
            if risk_level and h["risk_level"] != risk_level:
                continue
            result.append(h)
        return result

    def get_check_records(self, lab_id: str | None = None) -> list[dict]:
        """获取检查记录"""
        if lab_id:
            return [r for r in self.check_records if r["lab_id"] == lab_id]
        return list(self.check_records)

    def list_check_items(self, category: str | None = None) -> list[dict]:
        """列出检查项"""
        result = []
        for item in self.check_items.values():
            if not item["active"]:
                continue
            if category and item["category"] != category:
                continue
            result.append(item)
        return result
