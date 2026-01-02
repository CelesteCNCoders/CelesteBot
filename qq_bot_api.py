#!/usr/bin/env python3
"""QQ 机器人 API 模块 - OneBot v11 协议实现"""

import requests

from config import ONEBOT_HTTP_URL, ONEBOT_ACCESS_TOKEN_HTTP


class QQBotAPI:
    """
    QQ 机器人 API 接口 - OneBot v11 协议实现
    支持 go-cqhttp、NapCat、Lagrange 等 OneBot 实现
    """
    
    @staticmethod
    def _call_api(endpoint: str, data: dict) -> dict:
        """
        调用 OneBot HTTP API
        
        Args:
            endpoint: API 端点，如 "send_private_msg"
            data: 请求数据
            
        Returns:
            API 响应
        """
        url = f"{ONEBOT_HTTP_URL}/{endpoint}"
        headers = {"Content-Type": "application/json"}
        
        if ONEBOT_ACCESS_TOKEN_HTTP:
            headers["Authorization"] = f"Bearer {ONEBOT_ACCESS_TOKEN_HTTP}"
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            print('success ' + response.text + ' ' + str(response.status_code))
            print('url: ' + url)
            result = response.json()
            
            if result.get("status") == "failed":
                print(f"[OneBot API 错误] {endpoint}: {result.get('message', '未知错误')}")
            
            return result
        except requests.exceptions.RequestException as e:
            print(f"[OneBot API 网络错误] {endpoint}: {e}")
            return {"status": "failed", "message": str(e)}
    
    @staticmethod
    def send_private_message(qq_number: str, message: str) -> bool:
        """
        发送私聊消息
        
        Args:
            qq_number: QQ 号
            message: 消息内容
            
        Returns:
            是否发送成功
        """
        result = QQBotAPI._call_api("send_private_msg", {
            "user_id": int(qq_number),
            "message": message
        })
        
        success = result.get("status") == "ok"
        if success:
            print(f"[私聊] -> {qq_number}: {message}")
        return success
    
    @staticmethod
    def send_group_message(group_id: str, message: str) -> bool:
        """
        发送群消息
        
        Args:
            group_id: 群号
            message: 消息内容
            
        Returns:
            是否发送成功
        """
        result = QQBotAPI._call_api("send_group_msg", {
            "group_id": int(group_id),
            "message": message
        })
        
        success = result.get("status") == "ok"
        if success:
            print(f"[群聊] -> 群{group_id}: {message}")
        return success
    
    @staticmethod
    def send_group_at_message(group_id: str, qq_number: str, message: str) -> bool:
        """
        发送群消息并 @ 某人
        
        Args:
            group_id: 群号
            qq_number: 要 @ 的 QQ 号
            message: 消息内容
            
        Returns:
            是否发送成功
        """
        # 使用 CQ 码格式 @ 用户
        at_message = f"[CQ:at,qq={qq_number}] {message}"
        
        result = QQBotAPI._call_api("send_group_msg", {
            "group_id": int(group_id),
            "message": at_message
        })
        
        success = result.get("status") == "ok"
        if success:
            print(f"[群聊] -> 群{group_id} @{qq_number}: {message}")
        return success
    
    @staticmethod
    def is_user_in_group(group_id: str, qq_number: str) -> bool:
        """
        检查用户是否在群里
        
        Args:
            group_id: 群号
            qq_number: QQ 号
            
        Returns:
            是否在群里
        """
        result = QQBotAPI._call_api("get_group_member_info", {
            "group_id": int(group_id),
            "user_id": int(qq_number),
            "no_cache": False
        })
        
        return result.get("status") == "ok" and result.get("data") is not None
    
    @staticmethod
    def get_group_list() -> list:
        """
        获取机器人加入的群列表
        
        Returns:
            群列表 [{"group_id": 123, "group_name": "xxx"}, ...]
        """
        result = QQBotAPI._call_api("get_group_list", {})
        
        if result.get("status") == "ok":
            return result.get("data", [])
        return []
    
    @staticmethod
    def get_login_info() -> dict:
        """
        获取登录号信息
        
        Returns:
            {"user_id": 123456, "nickname": "xxx"}
        """
        result = QQBotAPI._call_api("get_login_info", {})
        
        if result.get("status") == "ok":
            return result.get("data", {})
        return {}
