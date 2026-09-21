"""
预约管理模块

负责实验室预约申请、审批、取消、冲突检测等核心业务流程。
是整个系统的核心业务模块。
"""

from datetime import datetime, timedelta


class ReservationManager:
    """预约管理核心类"""

    STATUS_PENDING = "pending"      # 待审批
    STATUS_APPROVED = "approved"    # 已批准
    STATUS_REJECTED = "rejected"    # 已拒绝
    STATUS_CANCELLED = "cancelled"  # 已取消
    STATUS_COMPLETED = "completed"  # 已完成

    def __init__(self):
        self.reservations = {}  # id -> reservation
        self._next_id = 1
        self.labs = {}  # lab_id -> lab_info

    def add_lab(self, lab_id: str, name: str, capacity: int,
                location: str, safety_level: str = "normal") -> bool:
        """
        添加实验室

        Args:
            lab_id: 实验室编号
            name: 实验室名称
            capacity: 容纳人数
            location: 位置
            safety_level: 安全等级（normal/medium/high）
        """
        if lab_id in self.labs:
            raise ValueError(f"实验室 {lab_id} 已存在")

        if capacity <= 0:
            raise ValueError("容纳人数必须大于0")

        valid_levels = {"normal", "medium", "high"}
        if safety_level not in valid_levels:
            raise ValueError(f"非法安全等级: {safety_level}")

        self.labs[lab_id] = {
            "name": name,
            "capacity": capacity,
            "location": location,
            "safety_level": safety_level,
            "equipment": [],
        }
        return True

    def create_reservation(self, username: str, lab_id: str,
                           start_time: str, end_time: str,
                           purpose: str = "", num_people: int = 1) -> int:
        """
        创建预约申请

        Args:
            username: 申请人
            lab_id: 实验室编号
            start_time: 开始时间 'YYYY-MM-DD HH:MM'
            end_time: 结束时间 'YYYY-MM-DD HH:MM'
            purpose: 实验用途
            num_people: 参与人数

        Returns:
            预约 ID
        """
        if lab_id not in self.labs:
            raise ValueError(f"实验室 {lab_id} 不存在")

        start = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
        end = datetime.strptime(end_time, "%Y-%m-%d %H:%M")

        if start >= end:
            raise ValueError("结束时间必须晚于开始时间")

        if num_people > self.labs[lab_id]["capacity"]:
            raise ValueError(f"人数超过实验室容量（最大 {self.labs[lab_id]['capacity']} 人）")

        # 冲突检测
        if self._check_conflict(lab_id, start, end):
            raise ValueError("该时间段已被预约")

        res_id = self._next_id
        self.reservations[res_id] = {
            "id": res_id,
            "username": username,
            "lab_id": lab_id,
            "start_time": start_time,
            "end_time": end_time,
            "purpose": purpose,
            "num_people": num_people,
            "status": self.STATUS_PENDING,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "approved_by": None,
            "reject_reason": "",
        }
        self._next_id += 1
        return res_id

    def _check_conflict(self, lab_id: str, start: datetime, end: datetime) -> bool:
        """
        检查预约冲突

        同一实验室同一时间段只能有一个有效预约（已批准的）。
        """
        for res in self.reservations.values():
            if res["lab_id"] != lab_id:
                continue
            if res["status"] not in (self.STATUS_PENDING, self.STATUS_APPROVED):
                continue

            res_start = datetime.strptime(res["start_time"], "%Y-%m-%d %H:%M")
            res_end = datetime.strptime(res["end_time"], "%Y-%m-%d %H:%M")

            # 时间段重叠判断
            if start < res_end and end > res_start:
                return True
        return False

    def approve_reservation(self, res_id: int, approver: str) -> bool:
        """审批通过预约"""
        if res_id not in self.reservations:
            raise KeyError(f"预约 {res_id} 不存在")

        res = self.reservations[res_id]
        if res["status"] != self.STATUS_PENDING:
            raise ValueError("只有待审批的预约可以批准")

        res["status"] = self.STATUS_APPROVED
        res["approved_by"] = approver
        return True

    def reject_reservation(self, res_id: int, reason: str, rejector: str) -> bool:
        """拒绝预约"""
        if res_id not in self.reservations:
            raise KeyError(f"预约 {res_id} 不存在")

        res = self.reservations[res_id]
        if res["status"] != self.STATUS_PENDING:
            raise ValueError("只有待审批的预约可以拒绝")

        res["status"] = self.STATUS_REJECTED
        res["reject_reason"] = reason
        res["approved_by"] = rejector
        return True

    def cancel_reservation(self, res_id: int, username: str) -> bool:
        """用户取消自己的预约"""
        if res_id not in self.reservations:
            raise KeyError(f"预约 {res_id} 不存在")

        res = self.reservations[res_id]
        if res["username"] != username:
            raise PermissionError("只能取消自己的预约")

        if res["status"] not in (self.STATUS_PENDING, self.STATUS_APPROVED):
            raise ValueError("该状态无法取消")

        res["status"] = self.STATUS_CANCELLED
        return True

    def get_user_reservations(self, username: str) -> list[dict]:
        """获取指定用户的所有预约"""
        return [r for r in self.reservations.values() if r["username"] == username]

    def get_lab_reservations(self, lab_id: str, status: str | None = None) -> list[dict]:
        """获取指定实验室的预约，可按状态筛选"""
        result = []
        for res in self.reservations.values():
            if res["lab_id"] != lab_id:
                continue
            if status and res["status"] != status:
                continue
            result.append(res)
        return result

    def list_labs(self, safety_level: str | None = None) -> list[dict]:
        """列出实验室列表"""
        result = []
        for lid, lab in self.labs.items():
            if safety_level and lab["safety_level"] != safety_level:
                continue
            result.append({"id": lid, **lab})
        return result
