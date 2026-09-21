"""
用户管理模块

负责用户注册、登录认证、角色权限管理。
用户角色分为：学生、教师、实验员、管理员。
"""


class UserManager:
    """用户管理核心类"""

    def __init__(self):
        self.users = {}  # username -> user_info
        self._next_id = 1
        self._current_user = None

    def register(self, username: str, password: str, role: str = "student",
                 real_name: str = "", department: str = "") -> int:
        """
        注册新用户

        Args:
            username: 用户名
            password: 密码（明文仅为演示，实际应加密）
            role: 角色：student/teacher/lab_admin/admin
            real_name: 真实姓名
            department: 所属院系

        Returns:
            用户 ID

        Raises:
            ValueError: 用户已存在或角色不合法
        """
        if not username or len(username) < 3:
            raise ValueError("用户名长度不能少于3位")

        if username in self.users:
            raise ValueError(f"用户 {username} 已存在")

        valid_roles = {"student", "teacher", "lab_admin", "admin"}
        if role not in valid_roles:
            raise ValueError(f"非法角色: {role}")

        if not password or len(password) < 6:
            raise ValueError("密码长度不能少于6位")

        user_id = self._next_id
        self.users[username] = {
            "id": user_id,
            "username": username,
            "password": password,
            "role": role,
            "real_name": real_name,
            "department": department,
            "active": True,
        }
        self._next_id += 1
        return user_id

    def login(self, username: str, password: str) -> bool:
        """
        用户登录

        Args:
            username: 用户名
            password: 密码

        Returns:
            登录成功返回 True
        """
        if username not in self.users:
            raise ValueError(f"用户 {username} 不存在")

        user = self.users[username]
        if not user["active"]:
            raise ValueError("该账户已被停用")

        if user["password"] != password:
            raise ValueError("密码错误")

        self._current_user = username
        return True

    def logout(self) -> None:
        """用户登出"""
        self._current_user = None

    def get_current_user(self) -> dict | None:
        """获取当前登录用户"""
        if not self._current_user:
            return None
        return self.users[self._current_user]

    def has_permission(self, permission: str) -> bool:
        """
        检查当前用户是否有指定权限

        权限规则：
        - admin: 所有权限
        - lab_admin: 设备/检查管理权限
        - teacher: 预约审批权限
        - student: 基础预约权限
        """
        user = self.get_current_user()
        if not user:
            return False

        role = user["role"]
        role_permissions = {
            "admin": {"all"},
            "lab_admin": {"equipment", "safety_check", "view_reservations"},
            "teacher": {"approve_reservation", "view_reservations", "create_reservation"},
            "student": {"create_reservation", "view_own_reservations"},
        }

        perms = role_permissions.get(role, set())
        return "all" in perms or permission in perms

    def list_users(self, role: str | None = None) -> list[dict]:
        """列出用户，可按角色筛选"""
        result = []
        for user in self.users.values():
            if role and user["role"] != role:
                continue
            # 不返回密码
            result.append({k: v for k, v in user.items() if k != "password"})
        return result

    def deactivate_user(self, username: str) -> bool:
        """停用用户账户"""
        if username not in self.users:
            raise KeyError(f"用户 {username} 不存在")
        self.users[username]["active"] = False
        return True
