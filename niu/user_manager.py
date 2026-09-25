"""用户与角色管理模块，提供实验室借还系统的身份基础数据。"""


class UserManager:
    """用户管理器：维护用户、角色和登录状态"""

    def setup_config(self) -> bool:
        """配置用户管理器：建立用户、角色和会话字典"""
        self.users: dict[str, dict[str, str]] = {}
        self.sessions: dict[str, bool] = {}
        self.roles: dict[str, str] = {
            "admin": "系统管理员",
            "manager": "设备管理员",
            "researcher": "实验人员",
        }
        self.default_role = "researcher"
        return True

    def add_user(self, user_id: str, name: str, role: str) -> bool:
        """添加用户：登记姓名并分配实验室角色"""
        # 用户编号必须唯一，避免借用记录无法追踪到具体人员
        if user_id in self.users:
            raise ValueError(f"用户已存在: {user_id}")
        if not user_id or not name:
            raise ValueError("用户编号和姓名不能为空")
        if role not in self.roles:
            raise ValueError(f"角色不存在: {role}")
        self.users[user_id] = {
            "user_id": user_id,
            "name": name,
            "role": role,
            "active": "yes",
        }
        self.sessions[user_id] = False
        return True

    def validate_user(self, user_id: str) -> bool:
        """校验用户：确认用户存在且仍处于有效状态"""
        if user_id not in self.users:
            return False
        user = self.users[user_id]
        if user["active"] != "yes":
            return False
        return True

    def get_user(self, user_id: str) -> dict[str, str] | bool:
        """获取用户：返回用户资料或失败标记"""
        if not self.validate_user(user_id):
            return False
        return dict(self.users[user_id])

    def assign_role(self, user_id: str, role: str) -> bool:
        """分配角色：更新有效用户的实验室权限角色"""
        if user_id not in self.users:
            raise ValueError(f"用户不存在: {user_id}")
        if role not in self.roles:
            raise ValueError(f"角色不存在: {role}")
        self.users[user_id]["role"] = role
        return True

    def list_user(self) -> list[dict[str, str]]:
        """列出用户：返回所有用户的可读资料副本"""
        result: list[dict[str, str]] = []
        for user_id in sorted(self.users):
            result.append(dict(self.users[user_id]))
        return result

    def login_user(self, user_id: str) -> bool:
        """登录用户：建立当前会话并返回登录结果"""
        if not self.validate_user(user_id):
            return False
        self.sessions[user_id] = True
        return True

    def logout_user(self, user_id: str) -> bool:
        """退出用户：清除当前会话并返回退出结果"""
        if user_id not in self.sessions:
            return False
        self.sessions[user_id] = False
        return True
