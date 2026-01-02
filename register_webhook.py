#!/usr/bin/env python3
"""注册 webhook 到服务器"""

import requests
import json

from config import ENDPOINT, TOKEN, WEBHOOK_PORT

# Webhook 回调地址（服务器会向这个地址发送通知）
WEBHOOK_URL = f"http://127.0.0.1:{WEBHOOK_PORT}"


def register_webhook():
    """注册 webhook"""
    url = f"{ENDPOINT}/api/hist/qqbot/webhook"
    headers = {"Content-Type": "application/json"}
    data = {
        "token": TOKEN,
        "action": "register",
        "webhook_url": WEBHOOK_URL
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        print("注册成功！")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return True
    except requests.exceptions.RequestException as e:
        print(f"注册失败: {e}")
        return False


def check_status():
    """检查 webhook 状态"""
    url = f"{ENDPOINT}/api/hist/qqbot/webhook"
    headers = {"Content-Type": "application/json"}
    data = {
        "token": TOKEN,
        "action": "status"
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        print("当前状态：")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result
    except requests.exceptions.RequestException as e:
        print(f"查询失败: {e}")
        return None


def unregister_webhook():
    """取消注册 webhook"""
    url = f"{ENDPOINT}/api/hist/qqbot/webhook"
    headers = {"Content-Type": "application/json"}
    data = {
        "token": TOKEN,
        "action": "unregister"
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        print("取消注册成功！")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return True
    except requests.exceptions.RequestException as e:
        print(f"取消注册失败: {e}")
        return False


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python register_webhook.py [register|status|unregister]")
        print("  register   - 注册 webhook")
        print("  status     - 查看状态")
        print("  unregister - 取消注册")
        sys.exit(1)
    
    action = sys.argv[1].lower()
    
    if action == "register":
        register_webhook()
    elif action == "status":
        check_status()
    elif action == "unregister":
        unregister_webhook()
    else:
        print(f"未知操作: {action}")
        sys.exit(1)
