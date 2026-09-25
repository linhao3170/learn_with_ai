"""设备台账模块，集中维护实验室设备及其可借状态。"""

STATUS_AVAILABLE = "available"
STATUS_BORROWED = "borrowed"
STATUS_REPAIRING = "repairing"
STATUS_RETIRED = "retired"


class EquipmentRecord:
    """设备记录：描述一台设备的编号、名称、状态和位置"""


class EquipmentManager:
    """设备管理器：维护设备台账和设备状态流转"""

    def setup_config(self) -> bool:
        """配置设备管理器：建立设备字典和状态常量映射"""
        self.equipment: dict[str, dict[str, str]] = {}
        self.locations: dict[str, str] = {}
        self.status_labels: dict[str, str] = {
            STATUS_AVAILABLE: "可借用",
            STATUS_BORROWED: "借出中",
            STATUS_REPAIRING: "维修中",
            STATUS_RETIRED: "已报废",
        }
        return True

    def add_equipment(
        self,
        equipment_id: str,
        name: str,
        category: str,
        location: str,
    ) -> bool:
        """添加设备：登记设备基础资料并设置为可用"""
        # 设备编号唯一，保证借用记录能定位到唯一资产
        if equipment_id in self.equipment:
            raise ValueError(f"设备已存在: {equipment_id}")
        if not equipment_id or not name or not category:
            raise ValueError("设备编号、名称和分类不能为空")
        self.equipment[equipment_id] = {
            "equipment_id": equipment_id,
            "name": name,
            "category": category,
            "location": location,
            "status": STATUS_AVAILABLE,
        }
        self.locations[equipment_id] = location
        return True

    def get_equipment(self, equipment_id: str) -> dict[str, str] | bool:
        """获取设备：返回设备资料或不存在标记"""
        if equipment_id not in self.equipment:
            return False
        return dict(self.equipment[equipment_id])

    def validate_equipment(self, equipment_id: str) -> bool:
        """校验设备：确认设备存在且没有被报废"""
        if equipment_id not in self.equipment:
            return False
        if self.equipment[equipment_id]["status"] == STATUS_RETIRED:
            return False
        return True

    def mark_equipment_status(self, equipment_id: str, status: str) -> bool:
        """标记设备状态：按业务流转更新设备当前状态"""
        if equipment_id not in self.equipment:
            raise ValueError(f"设备不存在: {equipment_id}")
        if status not in self.status_labels:
            raise ValueError(f"未知设备状态: {status}")
        if self.equipment[equipment_id]["status"] == STATUS_RETIRED:
            raise ValueError(f"报废设备不能改变状态: {equipment_id}")
        self.equipment[equipment_id]["status"] = status
        return True

    def update_equipment(
        self,
        equipment_id: str,
        name: str,
        category: str,
        location: str,
    ) -> bool:
        """更新设备：修改设备名称、分类和存放位置"""
        if equipment_id not in self.equipment:
            raise ValueError(f"设备不存在: {equipment_id}")
        if not name or not category or not location:
            raise ValueError("设备资料不能为空")
        record = self.equipment[equipment_id]
        record["name"] = name
        record["category"] = category
        record["location"] = location
        self.locations[equipment_id] = location
        return True

    def list_equipment(self) -> list[dict[str, str]]:
        """列出设备：按编号返回完整设备台账"""
        result: list[dict[str, str]] = []
        for equipment_id in sorted(self.equipment):
            result.append(dict(self.equipment[equipment_id]))
        return result
