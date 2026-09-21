"""
设备管理模块

负责实验室设备台账管理、设备借用、维护记录。
"""

from datetime import datetime


class EquipmentManager:
    """设备管理核心类"""

    STATUS_AVAILABLE = "available"    # 可用
    STATUS_BORROWED = "borrowed"      # 借出
    STATUS_MAINTENANCE = "maintenance"  # 维护中
    STATUS_SCRAPPED = "scrapped"      # 报废

    def __init__(self):
        self.equipments = {}  # id -> equipment
        self._next_id = 1
        self.borrow_records = []  # 借用记录
        self.maintenance_logs = []  # 维护记录

    def add_equipment(self, name: str, model: str, lab_id: str,
                      manufacturer: str = "", purchase_date: str = "") -> int:
        """
        添加设备

        Args:
            name: 设备名称
            model: 型号
            lab_id: 所属实验室
            manufacturer: 生产厂商
            purchase_date: 购置日期
        """
        if not name:
            raise ValueError("设备名称不能为空")

        equip_id = self._next_id
        self.equipments[equip_id] = {
            "id": equip_id,
            "name": name,
            "model": model,
            "lab_id": lab_id,
            "manufacturer": manufacturer,
            "purchase_date": purchase_date,
            "status": self.STATUS_AVAILABLE,
            "last_maintenance": None,
        }
        self._next_id += 1
        return equip_id

    def borrow_equipment(self, equip_id: int, username: str,
                         expected_return: str) -> int:
        """
        借出设备

        Args:
            equip_id: 设备 ID
            username: 借用人
            expected_return: 预计归还日期

        Returns:
            借用记录 ID
        """
        if equip_id not in self.equipments:
            raise KeyError(f"设备 {equip_id} 不存在")

        equip = self.equipments[equip_id]
        if equip["status"] != self.STATUS_AVAILABLE:
            raise ValueError(f"设备当前状态为 {equip['status']}，无法借出")

        record_id = len(self.borrow_records) + 1
        self.borrow_records.append({
            "id": record_id,
            "equip_id": equip_id,
            "username": username,
            "borrow_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "expected_return": expected_return,
            "return_time": None,
            "status": "borrowed",
        })

        equip["status"] = self.STATUS_BORROWED
        return record_id

    def return_equipment(self, record_id: int) -> bool:
        """归还设备"""
        for record in self.borrow_records:
            if record["id"] == record_id:
                if record["status"] != "borrowed":
                    raise ValueError("该借用记录已归还")

                record["status"] = "returned"
                record["return_time"] = datetime.now().strftime("%Y-%m-%d %H:%M")

                equip_id = record["equip_id"]
                self.equipments[equip_id]["status"] = self.STATUS_AVAILABLE
                return True

        raise KeyError(f"借用记录 {record_id} 不存在")

    def add_maintenance(self, equip_id: int, content: str,
                        operator: str, cost: float = 0.0) -> int:
        """
        添加设备维护记录

        Args:
            equip_id: 设备 ID
            content: 维护内容
            operator: 维护人员
            cost: 维护费用
        """
        if equip_id not in self.equipments:
            raise KeyError(f"设备 {equip_id} 不存在")

        log_id = len(self.maintenance_logs) + 1
        self.maintenance_logs.append({
            "id": log_id,
            "equip_id": equip_id,
            "content": content,
            "operator": operator,
            "cost": cost,
            "date": datetime.now().strftime("%Y-%m-%d"),
        })

        self.equipments[equip_id]["last_maintenance"] = datetime.now().strftime("%Y-%m-%d")
        return log_id

    def set_equipment_status(self, equip_id: int, status: str) -> bool:
        """设置设备状态（可用/维护中/报废）"""
        if equip_id not in self.equipments:
            raise KeyError(f"设备 {equip_id} 不存在")

        valid_statuses = {
            self.STATUS_AVAILABLE,
            self.STATUS_MAINTENANCE,
            self.STATUS_SCRAPPED,
        }
        if status not in valid_statuses:
            raise ValueError(f"非法状态: {status}")

        self.equipments[equip_id]["status"] = status
        return True

    def list_equipments(self, lab_id: str | None = None,
                        status: str | None = None) -> list[dict]:
        """列出设备，可按实验室/状态筛选"""
        result = []
        for equip in self.equipments.values():
            if lab_id and equip["lab_id"] != lab_id:
                continue
            if status and equip["status"] != status:
                continue
            result.append(equip)
        return result

    def get_maintenance_history(self, equip_id: int) -> list[dict]:
        """获取设备的维护历史"""
        if equip_id not in self.equipments:
            raise KeyError(f"设备 {equip_id} 不存在")
        return [log for log in self.maintenance_logs if log["equip_id"] == equip_id]
