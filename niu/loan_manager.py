"""借还管理模块，执行设备借出、归还、撤销和逾期统计。"""

from datetime import datetime, timedelta

from equipment_manager import (
    STATUS_AVAILABLE,
    STATUS_BORROWED,
    EquipmentManager,
)
from safety_checker import SafetyChecker
from user_manager import UserManager


LOAN_BORROWED = "borrowed"
LOAN_RETURNED = "returned"
LOAN_CANCELLED = "cancelled"
LOAN_PENDING = "pending"
LOAN_REJECTED = "rejected"


class LoanManager:
    """借还管理器：维护借用记录并协调用户、设备和安全检查"""

    def setup_config(
        self,
        user_manager: UserManager,
        equipment_manager: EquipmentManager,
        safety_checker: SafetyChecker,
    ) -> bool:
        """配置借还管理器：关联三类基础管理器并初始化借用状态"""
        self.user_manager = user_manager
        self.equipment_manager = equipment_manager
        self.safety_checker = safety_checker
        self.loans: dict[str, dict[str, str]] = {}
        self.sequence = 1
        self.loan_days = 7
        return True

    def borrow_equipment(
        self,
        equipment_id: str,
        user_id: str,
        borrow_time: str,
    ) -> dict[str, str] | bool:
        """借出设备：登记借用记录并锁定设备"""
        # 设备必须存在，否则不能建立借用关系
        if equipment_id not in self.equipment_manager.equipment:
            raise ValueError(f"设备不存在: {equipment_id}")
        # 借用人必须有效，避免出现无法追责的借用记录
        if not self.user_manager.validate_user(user_id):
            raise ValueError(f"用户无效: {user_id}")
        # 设备必须处于可用状态，否则不允许借出
        if self.equipment_manager.equipment[equipment_id]["status"] != STATUS_AVAILABLE:
            raise ValueError(f"设备当前不可借用: {equipment_id}")
        if not self.safety_checker.ensure_equipment_safety(equipment_id):
            return False
        if not borrow_time:
            raise ValueError("借用时间不能为空")
        try:
            start_at = datetime.fromisoformat(borrow_time)
        except ValueError:
            raise ValueError(f"借用时间格式错误: {borrow_time}")
        # 再次扫描活动记录，保证同一设备不会出现双重借出
        for loan in self.loans.values():
            if loan["equipment_id"] == equipment_id and loan["status"] == LOAN_BORROWED:
                return False
        loan_id = f"L{self.sequence:04d}"
        self.sequence += 1
        due_at = start_at + timedelta(days=self.loan_days)
        record = {
            "loan_id": loan_id,
            "equipment_id": equipment_id,
            "user_id": user_id,
            "borrow_time": start_at.isoformat(timespec="minutes"),
            "due_time": due_at.isoformat(timespec="minutes"),
            "return_time": "",
            "status": LOAN_BORROWED,
            "approval": "approved",
        }
        self.loans[loan_id] = record
        self.equipment_manager.mark_equipment_status(
            equipment_id, STATUS_BORROWED
        )
        return dict(record)

    def return_equipment(
        self,
        loan_id: str,
        user_id: str,
        return_time: str,
    ) -> bool:
        """归还设备：关闭借用记录并释放设备状态"""
        if loan_id not in self.loans:
            raise ValueError(f"借用记录不存在: {loan_id}")
        record = self.loans[loan_id]
        if record["status"] != LOAN_BORROWED:
            raise ValueError(f"借用记录当前不可归还: {loan_id}")
        if record["user_id"] != user_id:
            raise ValueError("只能由原借用人归还设备")
        if not return_time:
            raise ValueError("归还时间不能为空")
        try:
            returned_at = datetime.fromisoformat(return_time)
        except ValueError:
            raise ValueError(f"归还时间格式错误: {return_time}")
        record["return_time"] = returned_at.isoformat(timespec="minutes")
        record["status"] = LOAN_RETURNED
        self.equipment_manager.mark_equipment_status(
            record["equipment_id"], STATUS_AVAILABLE
        )
        return True

    def cancel_loan(self, loan_id: str, reason: str) -> bool:
        """撤销借用：标记记录为撤销并在必要时释放设备"""
        if loan_id not in self.loans:
            raise ValueError(f"借用记录不存在: {loan_id}")
        if not reason:
            raise ValueError("撤销原因不能为空")
        record = self.loans[loan_id]
        if record["status"] in (LOAN_RETURNED, LOAN_CANCELLED):
            return False
        record["status"] = LOAN_CANCELLED
        record["cancel_reason"] = reason
        if record["equipment_id"] in self.equipment_manager.equipment:
            self.equipment_manager.mark_equipment_status(
                record["equipment_id"], STATUS_AVAILABLE
            )
        return True

    def approve_loan(self, loan_id: str) -> bool:
        """批准借用：将待审批记录转为已借出并锁定设备"""
        if loan_id not in self.loans:
            raise ValueError(f"借用记录不存在: {loan_id}")
        record = self.loans[loan_id]
        if record["status"] != LOAN_PENDING:
            return False
        if not self.safety_checker.ensure_equipment_safety(record["equipment_id"]):
            return False
        record["status"] = LOAN_BORROWED
        record["approval"] = "approved"
        self.equipment_manager.mark_equipment_status(
            record["equipment_id"], STATUS_BORROWED
        )
        return True

    def reject_loan(self, loan_id: str, reason: str) -> bool:
        """拒绝借用：记录拒绝原因并释放审批中的申请"""
        if loan_id not in self.loans:
            raise ValueError(f"借用记录不存在: {loan_id}")
        if not reason:
            raise ValueError("拒绝原因不能为空")
        record = self.loans[loan_id]
        if record["status"] != LOAN_PENDING:
            return False
        record["status"] = LOAN_REJECTED
        record["approval"] = reason
        return True

    def get_loan(self, loan_id: str) -> dict[str, str] | bool:
        """获取借用：返回单条借用记录或失败标记"""
        if loan_id not in self.loans:
            return False
        return dict(self.loans[loan_id])

    def list_overdue_loans(self, current_time: str) -> list[dict[str, str]]:
        """列出逾期借用：筛选已超过应还时间的活动记录"""
        result: list[dict[str, str]] = []
        try:
            now = datetime.fromisoformat(current_time)
        except ValueError:
            # 当前时间无法解析时返回空列表，避免统计命令让整个程序退出
            return result
        for record in self.loans.values():
            if record["status"] != LOAN_BORROWED:
                continue
            try:
                due_at = datetime.fromisoformat(record["due_time"])
            except ValueError:
                continue
            if now > due_at:
                result.append(dict(record))
        return result

    def calculate_borrow_count(self, user_id: str) -> int:
        """计算借用次数：统计用户全部有效借用记录"""
        count = 0
        for record in self.loans.values():
            if record["user_id"] == user_id and record["status"] != LOAN_CANCELLED:
                count += 1
        return count
