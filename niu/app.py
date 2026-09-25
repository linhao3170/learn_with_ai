"""命令行入口：串联用户、设备、安全检查和借还模块。"""

from datetime import datetime

from equipment_manager import EquipmentManager
from loan_manager import LoanManager
from safety_checker import SafetyChecker
from user_manager import UserManager


def format_report(title: str, rows: list[dict[str, str]]) -> str:
    """格式化报表：把字典记录转换为命令行可读文本"""
    lines = [f"=== {title} ==="]
    if not rows:
        lines.append("暂无记录")
        return "\n".join(lines)
    for row in rows:
        parts: list[str] = []
        for key in sorted(row):
            parts.append(f"{key}={row[key]}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def borrow_equipment(
    loan_manager: LoanManager,
    equipment_id: str,
    user_id: str,
) -> bool:
    """借出设备：提供命令行场景的借用流程包装"""
    borrow_time = datetime.now().isoformat(timespec="minutes")
    try:
        record = loan_manager.borrow_equipment(
            equipment_id, user_id, borrow_time
        )
    except ValueError as error:
        print(f"借用失败: {error}")
        return False
    if not record:
        print("借用被拒绝：设备未通过安全检查或已有活动借用")
        return False
    print(f"借用成功: {record['loan_id']}")
    return True


def return_equipment(
    loan_manager: LoanManager,
    loan_id: str,
    user_id: str,
) -> bool:
    """归还设备：提供命令行场景的归还流程包装"""
    return_time = datetime.now().isoformat(timespec="minutes")
    try:
        success = loan_manager.return_equipment(
            loan_id, user_id, return_time
        )
    except ValueError as error:
        print(f"归还失败: {error}")
        return False
    if not success:
        print("归还失败：借用记录状态不允许归还")
        return False
    print("归还成功，设备已重新进入可用状态")
    return True


def list_report(
    user_manager: UserManager,
    equipment_manager: EquipmentManager,
    safety_checker: SafetyChecker,
    loan_manager: LoanManager,
) -> str:
    """列出报表：汇总用户、设备、检查和借用数据"""
    sections = [
        format_report("用户", user_manager.list_user()),
        format_report("设备", equipment_manager.list_equipment()),
        format_report("安全检查", safety_checker.list_check_record()),
        format_report("逾期借用", loan_manager.list_overdue_loans(
            datetime.now().isoformat(timespec="minutes")
        )),
    ]
    return "\n\n".join(sections)


def setup_config() -> bool:
    """配置命令行应用：创建模块对象、演示业务流程并启动菜单"""
    user_manager = UserManager()
    equipment_manager = EquipmentManager()
    safety_checker = SafetyChecker()
    loan_manager = LoanManager()
    user_manager.setup_config()
    equipment_manager.setup_config()
    safety_checker.setup_config(equipment_manager)
    loan_manager.setup_config(user_manager, equipment_manager, safety_checker)
    user_manager.add_user("U001", "张敏", "researcher")
    user_manager.add_user("U002", "李工", "manager")
    equipment_manager.add_equipment("E001", "离心机", "分析设备", "A-101")
    equipment_manager.add_equipment("E002", "高温炉", "热处理设备", "B-202")
    now = datetime.now().isoformat(timespec="minutes")
    safety_checker.add_check_record("E001", "李工", "pass", now, "防护罩正常")
    safety_checker.add_check_record("E002", "李工", "fail", now, "温控异常")
    print("实验室设备借还与安全检查管理系统")
    print("示例：E001 可正常借用，E002 会因安全检查不合格被拒绝。")
    while True:
        print("1 借用  2 归还  3 查看报表  0 退出")
        choice = input("请选择: ").strip()
        if choice == "0":
            return True
        if choice == "1":
            equipment_id = input("设备编号: ").strip()
            user_id = input("用户编号: ").strip()
            borrow_equipment(loan_manager, equipment_id, user_id)
            continue
        if choice == "2":
            loan_id = input("借用编号: ").strip()
            user_id = input("用户编号: ").strip()
            return_equipment(loan_manager, loan_id, user_id)
            continue
        if choice == "3":
            print(list_report(
                user_manager, equipment_manager, safety_checker, loan_manager
            ))
            continue
        print("无效选项，请重新输入")


if __name__ == "__main__":
    setup_config()
