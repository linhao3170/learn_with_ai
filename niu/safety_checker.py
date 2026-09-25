"""安全检查模块，判断设备是否满足借用前的安全准入条件。"""

from datetime import datetime, timedelta

from equipment_manager import (
    STATUS_AVAILABLE,
    STATUS_BORROWED,
    STATUS_REPAIRING,
    EquipmentManager,
)


class SafetyChecker:
    """安全检查器：维护检查记录并执行周期性借用准入判断"""

    def setup_config(self, equipment_manager: EquipmentManager) -> bool:
        """配置安全检查器：关联设备台账并建立检查记录"""
        self.equipment_manager = equipment_manager
        self.checks: dict[str, dict[str, str]] = {}
        self.interval_days = 30
        self.pass_result = "pass"
        self.fail_result = "fail"
        return True

    def add_check_record(
        self,
        equipment_id: str,
        inspector: str,
        result: str,
        checked_time: str,
        note: str,
    ) -> bool:
        """添加检查记录：登记检查人、时间、结果和处置说明"""
        if equipment_id not in self.equipment_manager.equipment:
            raise ValueError(f"设备不存在: {equipment_id}")
        if result not in (self.pass_result, self.fail_result):
            raise ValueError("检查结果只能是 pass 或 fail")
        if not inspector or not checked_time:
            raise ValueError("检查人和检查时间不能为空")
        try:
            checked_at = datetime.fromisoformat(checked_time)
        except ValueError:
            raise ValueError(f"检查时间格式错误: {checked_time}")
        self.checks[equipment_id] = {
            "equipment_id": equipment_id,
            "inspector": inspector,
            "result": result,
            "checked_time": checked_at.isoformat(timespec="minutes"),
            "note": note,
        }
        # 检查不合格立即进入维修状态，阻断后续借用
        if result == self.fail_result:
            self.equipment_manager.mark_equipment_status(
                equipment_id, STATUS_REPAIRING
            )
        elif self.equipment_manager.equipment[equipment_id]["status"] == STATUS_REPAIRING:
            self.equipment_manager.mark_equipment_status(
                equipment_id, STATUS_AVAILABLE
            )
        return True

    def get_check_record(self, equipment_id: str) -> dict[str, str] | bool:
        """获取检查记录：返回设备最近一次安全检查"""
        if equipment_id not in self.checks:
            return False
        return dict(self.checks[equipment_id])

    def check_equipment_safety(self, equipment_id: str) -> bool:
        """检查设备安全：判断检查结果和有效期是否允许借用"""
        if equipment_id not in self.equipment_manager.equipment:
            return False
        record = self.checks.get(equipment_id)
        if record is None:
            return False
        if record["result"] != self.pass_result:
            return False
        try:
            checked_at = datetime.fromisoformat(record["checked_time"])
        except ValueError:
            # 历史数据损坏时按不安全处理，避免放行未经核验的设备
            return False
        deadline = checked_at + timedelta(days=self.interval_days)
        if datetime.now() > deadline:
            return False
        if self.equipment_manager.equipment[equipment_id]["status"] == STATUS_REPAIRING:
            return False
        return True

    def ensure_equipment_safety(self, equipment_id: str) -> bool:
        """确保设备安全：安全检查失败时直接返回拒绝结果"""
        if not self.check_equipment_safety(equipment_id):
            return False
        if self.equipment_manager.equipment[equipment_id]["status"] == STATUS_BORROWED:
            return False
        return True

    def list_check_record(self) -> list[dict[str, str]]:
        """列出检查记录：返回全部设备的最近检查资料"""
        result: list[dict[str, str]] = []
        for equipment_id in sorted(self.checks):
            result.append(dict(self.checks[equipment_id]))
        return result
