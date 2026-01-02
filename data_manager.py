#!/usr/bin/env python3
"""数据管理模块"""

import json
import random
import time
import threading
from pathlib import Path
from typing import Optional

from config import VERIFICATION_TIMEOUT, BIND_COOLDOWN


class DataManager:
    """JSON 数据管理器"""
    
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.lock = threading.Lock()
        self._ensure_file()
    
    def _ensure_file(self):
        """确保数据文件存在"""
        if not self.filepath.exists():
            self._save({
                "bindings": {},
                "user_qq_map": {},
                "notifications": {},
                "groups": [],
                "pending_bindings": {}
            })
    
    def _load(self) -> dict:
        """加载数据"""
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    def _save(self, data: dict):
        """保存数据"""
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def get_binding(self, qq_number: str) -> Optional[str]:
        """获取 QQ 号绑定的用户名"""
        with self.lock:
            data = self._load()
            return data.get("bindings", {}).get(qq_number)
    
    def get_qq_by_username(self, username: str) -> Optional[str]:
        """根据用户名获取绑定的 QQ 号"""
        with self.lock:
            data = self._load()
            return data.get("user_qq_map", {}).get(username)
    
    def set_binding(self, qq_number: str, username: str):
        """设置绑定"""
        with self.lock:
            data = self._load()
            if "bindings" not in data:
                data["bindings"] = {}
            if "user_qq_map" not in data:
                data["user_qq_map"] = {}
            
            # 移除旧绑定（如果存在）
            old_username = data["bindings"].get(qq_number)
            if old_username:
                data["user_qq_map"].pop(old_username, None)
            
            old_qq = data["user_qq_map"].get(username)
            if old_qq:
                data["bindings"].pop(old_qq, None)
            
            data["bindings"][qq_number] = username
            data["user_qq_map"][username] = qq_number
            self._save(data)
    
    def check_bind_cooldown(self, qq_number: str) -> tuple[bool, int]:
        """检查是否在冷却时间内，返回 (是否可以请求, 剩余秒数)"""
        with self.lock:
            data = self._load()
            pending = data.get("pending_bindings", {}).get(qq_number)
            
            if pending:
                request_time = pending.get("request_time", 0)
                elapsed = time.time() - request_time
                if elapsed < BIND_COOLDOWN:
                    return False, int(BIND_COOLDOWN - elapsed)
            
            return True, 0
    
    def create_pending_binding(self, qq_number: str, username: str) -> str:
        """创建待验证的绑定，返回验证码"""
        code = str(random.randint(100000, 999999))
        expire_time = time.time() + VERIFICATION_TIMEOUT
        request_time = time.time()
        
        with self.lock:
            data = self._load()
            if "pending_bindings" not in data:
                data["pending_bindings"] = {}
            
            data["pending_bindings"][qq_number] = {
                "username": username,
                "code": code,
                "expire_time": expire_time,
                "request_time": request_time
            }
            self._save(data)
        
        return code
    
    def verify_binding(self, qq_number: str, code: str) -> tuple[bool, str]:
        """验证绑定，返回 (成功, 消息)"""
        with self.lock:
            data = self._load()
            pending = data.get("pending_bindings", {}).get(qq_number)
            
            if not pending:
                return False, "没有待验证的绑定请求，请先使用 /bind 命令"
            
            if time.time() > pending["expire_time"]:
                # 清理过期的绑定请求
                data["pending_bindings"].pop(qq_number, None)
                self._save(data)
                return False, "验证码已过期，请重新使用 /bind 命令"
            
            if pending["code"] != code:
                return False, "验证码错误，请重新输入"
            
            # 验证成功，创建绑定
            username = pending["username"]
            data["pending_bindings"].pop(qq_number, None)
            self._save(data)
        
        # 使用外部方法设置绑定（避免死锁）
        self.set_binding(qq_number, username)
        return True, f"绑定成功！已将 QQ 绑定到用户: {username}"
    
    def set_notification_group(self, qq_number: str, group_id: str):
        """设置优先通知群"""
        with self.lock:
            data = self._load()
            if "notifications" not in data:
                data["notifications"] = {}
            data["notifications"][qq_number] = group_id
            self._save(data)
    
    def get_notification_group(self, qq_number: str) -> Optional[str]:
        """获取优先通知群"""
        with self.lock:
            data = self._load()
            return data.get("notifications", {}).get(qq_number)
    
    def add_group(self, group_id: str):
        """添加群"""
        with self.lock:
            data = self._load()
            if "groups" not in data:
                data["groups"] = []
            if group_id not in data["groups"]:
                data["groups"].append(group_id)
                self._save(data)
    
    def remove_group(self, group_id: str):
        """移除群"""
        with self.lock:
            data = self._load()
            if "groups" not in data:
                data["groups"] = []
            if group_id in data["groups"]:
                data["groups"].remove(group_id)
                self._save(data)
    
    def get_groups(self) -> list:
        """获取所有群"""
        with self.lock:
            data = self._load()
            return data.get("groups", [])
