"""
实验室安全助手系统 - 主入口

串联四大模块，提供统一的系统接口。
"""

from .user_manager import UserManager
from .reservation_manager import ReservationManager
from .equipment_manager import EquipmentManager
from .safety_checker import SafetyChecker


class LabSafetyApp:
    """
    实验室安全助手主应用

    整合用户管理、预约管理、设备管理、安全检查四大模块，
    提供统一的系统操作入口。
    """

    def __init__(self):
        self.user_manager = UserManager()
        self.reservation_manager = ReservationManager()
        self.equipment_manager = EquipmentManager()
        self.safety_checker = SafetyChecker()

    def initialize_sample_data(self) -> None:
        """初始化示例数据"""
        # 创建管理员
        self.user_manager.register(
            username="admin",
            password="admin123",
            role="admin",
            real_name="系统管理员",
        )

        # 创建实验室
        self.reservation_manager.add_lab(
            lab_id="LAB-101",
            name="化学基础实验室",
            capacity=30,
            location="A栋1楼101",
            safety_level="medium",
        )
        self.reservation_manager.add_lab(
            lab_id="LAB-201",
            name="生物安全实验室",
            capacity=20,
            location="B栋2楼201",
            safety_level="high",
        )

        # 添加一些设备
        self.equipment_manager.add_equipment(
            name="分析天平", model="FA2004", lab_id="LAB-101"
        )
        self.equipment_manager.add_equipment(
            name="显微镜", model="CX23", lab_id="LAB-101"
        )

        # 添加安全检查项
        self.safety_checker.add_check_item(
            content="消防通道是否畅通",
            category="消防",
            risk_level="high",
        )
        self.safety_checker.add_check_item(
            content="灭火器是否在有效期内",
            category="消防",
            risk_level="medium",
        )
        self.safety_checker.add_check_item(
            content="电器设备是否完好",
            category="用电",
            risk_level="medium",
        )

    def get_system_stats(self) -> dict:
        """获取系统概览统计"""
        return {
            "total_users": len(self.user_manager.users),
            "total_labs": len(self.reservation_manager.labs),
            "total_reservations": len(self.reservation_manager.reservations),
            "total_equipments": len(self.equipment_manager.equipments),
            "total_hazards": len(self.safety_checker.hazards),
            "pending_reservations": len([
                r for r in self.reservation_manager.reservations.values()
                if r["status"] == ReservationManager.STATUS_PENDING
            ]),
            "open_hazards": len([
                h for h in self.safety_checker.hazards
                if h["status"] != SafetyChecker.STATUS_CLOSED
            ]),
        }
