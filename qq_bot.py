#!/usr/bin/env python3
"""
QQ 机器人主程序

功能：
- 接收 QQ 消息并处理命令
- 接收 Webhook 通知并推送给用户
- 定时备份数据到 GitHub
"""

import json
import time
import threading
import websocket
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from typing import Optional

from config import (
    ENDPOINT, TOKEN, WEBHOOK_PORT, DATA_FILE,
    ONEBOT_WS_URL, ONEBOT_ACCESS_TOKEN_HTTP, ONEBOT_ACCESS_TOKEN_WS
)
from data_manager import DataManager
from qq_bot_api import QQBotAPI
from backup_scheduler import BackupScheduler


# ============== 消息处理器 ==============
class MessageHandler:
    """消息处理器"""
    
    def __init__(self, data_manager: DataManager, qq_api: QQBotAPI):
        self.data = data_manager
        self.qq = qq_api
    
    def handle_private_message(self, qq_number: str, message: str):
        """
        处理私聊消息
        
        Args:
            qq_number: 发送者 QQ 号
            message: 消息内容
        """
        message = message.strip()
        # /bind 命令
        if message.startswith("/bind "):
            username = message[6:].strip()
            self._handle_bind(qq_number, username)
            return
        
        # /verify 命令
        if message.startswith("/verify "):
            code = message[8:].strip()
            self._handle_verify(qq_number, code)
            return
        
        # 帮助信息
        if message in ["/help", "帮助", "?"]:
            help_msg = """QQ 机器人帮助：
/bind <用户名> - 绑定论坛账号
/verify <验证码> - 验证绑定
/noti - 设置通知方式（私聊中使用为私聊通知，群里使用为群通知）
/help - 显示帮助"""
            self.qq.send_private_message(qq_number, help_msg)
            return
        
        # /noti 命令 - 设置私聊通知
        if message == "/noti":
            self._handle_noti_private(qq_number)
            return
    
    def handle_group_message(self, group_id: str, qq_number: str, message: str):
        """
        处理群消息
        
        Args:
            group_id: 群号
            qq_number: 发送者 QQ 号
            message: 消息内容
        """
        message = message.strip()
        
        # /noti 命令 - 设置优先通知群
        if message == "/noti":
            self._handle_noti(group_id, qq_number)
            return
    
    def _handle_bind(self, qq_number: str, username: str):
        """处理绑定请求"""
        import requests
        
        # 检查冷却时间
        can_request, remaining = self.data.check_bind_cooldown(qq_number)
        if not can_request:
            self.qq.send_private_message(qq_number, f"请求过于频繁，请 {remaining} 秒后再试")
            return
        
        # 生成验证码
        code = self.data.create_pending_binding(qq_number, username)
        
        # 向服务器发送绑定请求
        try:
            url = f"{ENDPOINT}/api/hist/qqbot/bind"
            headers = {"Content-Type": "application/json"}
            payload = {
                "token": TOKEN,
                "username": username,
                "verification_code": code,
                "qq_number": qq_number
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            
            if response.status_code == 200:
                self.qq.send_private_message(
                    qq_number,
                    f"绑定请求已发送！\n"
                    f"请在 5 分钟内回复 /verify 验证码 完成验证\n"
                    f"（验证码发送到了您的论坛账号通知里）"
                )
            else:
                print(response.status_code)
                error_msg = response.json().get("message", "未知错误")
                self.qq.send_private_message(qq_number, f"绑定请求失败: {error_msg}")
                
        except requests.exceptions.RequestException as e:
            self.qq.send_private_message(qq_number, f"网络错误: {e}")
    
    def _handle_verify(self, qq_number: str, code: str):
        """处理验证请求"""
        success, message = self.data.verify_binding(qq_number, code)
        self.qq.send_private_message(qq_number, message)
    
    def _handle_noti(self, group_id: str, qq_number: str):
        """处理设置通知群请求"""
        # 检查是否已绑定
        username = self.data.get_binding(qq_number)
        if not username:
            self.qq.send_group_message(group_id, "你还没有绑定账号，请先私聊发送 /bind <用户名> 进行绑定")
            return
        
        self.data.set_notification_group(qq_number, group_id)
        self.qq.send_group_message(group_id, f"已设置本群为你的优先通知群")
    
    def _handle_noti_private(self, qq_number: str):
        """处理设置私聊通知请求"""
        # 检查是否已绑定
        username = self.data.get_binding(qq_number)
        if not username:
            self.qq.send_private_message(qq_number, "你还没有绑定账号，请先使用 /bind <用户名> 进行绑定")
            return
        
        self.data.set_notification_group(qq_number, "private")
        self.qq.send_private_message(qq_number, "已设置为私聊通知优先")


class WebhookHandler(BaseHTTPRequestHandler):
    
    data_manager: DataManager = None
    qq_api: QQBotAPI = None
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        
        print("=" * 50)
        print(f"[{datetime.now().isoformat()}] WEBHOOK RECEIVED!")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print("=" * 50)
        
        # 处理 webhook 事件
        self._process_webhook(data)
        
        # 返回成功响应
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"success":true}')
    
    def _process_webhook(self, data: dict):
        """处理 webhook 数据"""
        event = data.get("event")
        
        if event == "submission_approved":
            self._handle_submission_approved(data)
        if event == "submission_rejected":
            self._handle_submission_rejected(data)
    
    def _handle_submission_approved(self, data: dict):
        """处理提交审核通过事件"""
        user_id = data.get("user_id")
        username = data.get("username", "未知用户")
        map_name = data.get("map_name", "未知地图")
        map_stars = data.get("map_stars", 0)
        golden_berry = data.get("golden_berry", False)
        
        # 获取用户绑定的 QQ
        qq_number = self.data_manager.get_qq_by_username(username)
        if not qq_number:
            print(f"用户 {username}(ID:{user_id}) 未绑定 QQ，跳过通知")
            return
        
        # 构建通知消息
        action = "金了" if golden_berry else "通过了"
        message = f"恭喜 {username} {action} {map_stars} 星地图 {map_name}！"
        
        # 查找通知群
        target_group = self._find_notification_group(qq_number)
        
        if target_group:
            self.qq_api.send_group_at_message(target_group, qq_number, message)
            print(f"已在群 {target_group} 通知用户 {qq_number}")
        else:
            # 没有找到合适的群，发送私聊
            self.qq_api.send_private_message(qq_number, message)
            print(f"未找到合适的群，已私聊通知用户 {qq_number}")
    
    def _handle_submission_rejected(self, data: dict):
        """处理提交审核未通过事件"""
        user_id = data.get("user_id")
        username = data.get("username", "未知用户")
        map_name = data.get("map_name", "未知地图")
        map_stars = data.get("map_stars", 0)
        
        # 获取用户绑定的 QQ
        qq_number = self.data_manager.get_qq_by_username(username)
        if not qq_number:
            print(f"用户 {username}(ID:{user_id}) 未绑定 QQ，跳过通知")
            return
        
        # 构建通知消息
        message = f"很遗憾， {username} 通过 {map_stars} 星地图 {map_name} 的申请被拒绝！审核员：" + data.get("reviewer", "未知")
        
        # 查找通知群
        target_group = self._find_notification_group(qq_number)
        
        if target_group:
            self.qq_api.send_group_at_message(target_group, qq_number, message)
            print(f"已在群 {target_group} 通知用户 {qq_number}")
        else:
            # 没有找到合适的群，发送私聊
            self.qq_api.send_private_message(qq_number, message)
            print(f"未找到合适的群，已私聊通知用户 {qq_number}")
    
    def _find_notification_group(self, qq_number: str) -> Optional[str]:
        """
        查找通知群
        1. 如果设置为 "private"，返回 None（表示私聊）
        2. 优先使用用户设置的通知群（如果用户在群里）
        3. 否则查找任意一个用户在的群
        """
        # 检查优先通知设置
        preferred = self.data_manager.get_notification_group(qq_number)
        
        # 如果设置为私聊优先
        if preferred == "private":
            return None
        
        # 检查优先通知群
        if preferred and self.qq_api.is_user_in_group(preferred, qq_number):
            return preferred
        
        # 查找其他群
        for group_id in self.data_manager.get_groups():
            if self.qq_api.is_user_in_group(group_id, qq_number):
                return group_id
        
        return None
    
    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {args[0]}")


# ============== OneBot WebSocket 客户端 ==============
class OneBotWebSocket:
    """OneBot WebSocket 客户端，用于接收消息事件"""
    
    def __init__(self, bot: 'QQBot'):
        self.bot = bot
        self.ws: websocket.WebSocketApp = None
        self.connected = False
        self.reconnect_interval = 5  # 重连间隔（秒）
    
    def _on_open(self, ws):
        """WebSocket 连接打开"""
        self.connected = True
        print(f"[OneBot WS] 已连接到 {ONEBOT_WS_URL}")
        
        # 同步群列表
        self._sync_group_list()
    
    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket 连接关闭"""
        self.connected = False
        print(f"[OneBot WS] 连接已关闭: {close_status_code} {close_msg}")
    
    def _on_error(self, ws, error):
        """WebSocket 错误"""
        print(f"[OneBot WS] 错误: {error}")
    
    def _on_message(self, ws, message: str):
        """处理 WebSocket 消息"""
        try:
            data = json.loads(message)
            self._process_event(data)
        except json.JSONDecodeError as e:
            print(f"[OneBot WS] JSON 解析错误: {e}")
    
    def _process_event(self, data: dict):
        """处理 OneBot 事件"""
        post_type = data.get("post_type")
        
        if post_type == "message":
            self._handle_message_event(data)
        elif post_type == "notice":
            self._handle_notice_event(data)
        elif post_type == "meta_event":
            self._handle_meta_event(data)
    
    def _handle_message_event(self, data: dict):
        """处理消息事件"""
        message_type = data.get("message_type")
        user_id = str(data.get("user_id", ""))
        raw_message = data.get("raw_message", "") or self._extract_text(data.get("message", []))
        
        if message_type == "private":
            # 私聊消息
            print(f"[私聊] <- {user_id}: {raw_message}")
            self.bot.on_private_message(user_id, raw_message)
            
        elif message_type == "group":
            # 群消息
            group_id = str(data.get("group_id", ""))
            print(f"[群聊] <- 群{group_id} {user_id}: {raw_message}")
            self.bot.on_group_message(group_id, user_id, raw_message)
    
    def _handle_notice_event(self, data: dict):
        """处理通知事件"""
        notice_type = data.get("notice_type")
        
        if notice_type == "group_increase":
            # 群成员增加
            user_id = str(data.get("user_id", ""))
            group_id = str(data.get("group_id", ""))
            self_id = str(data.get("self_id", ""))
            
            if user_id == self_id:
                self.bot.on_group_join(group_id)
                
        elif notice_type == "group_decrease":
            # 群成员减少
            user_id = str(data.get("user_id", ""))
            group_id = str(data.get("group_id", ""))
            self_id = str(data.get("self_id", ""))
            
            if user_id == self_id:
                self.bot.on_group_leave(group_id)
    
    def _handle_meta_event(self, data: dict):
        """处理元事件"""
        meta_event_type = data.get("meta_event_type")
        
        if meta_event_type == "lifecycle":
            sub_type = data.get("sub_type")
            if sub_type == "connect":
                print("[OneBot WS] 生命周期: 连接成功")
        elif meta_event_type == "heartbeat":
            # 心跳事件，可以忽略
            pass
    
    def _extract_text(self, message) -> str:
        """从消息段中提取纯文本"""
        if isinstance(message, str):
            return message
        
        if isinstance(message, list):
            texts = []
            for seg in message:
                if isinstance(seg, dict) and seg.get("type") == "text":
                    texts.append(seg.get("data", {}).get("text", ""))
            return "".join(texts)
        
        return ""
    
    def _sync_group_list(self):
        """同步群列表"""
        try:
            groups = QQBotAPI.get_group_list()
            for group in groups:
                group_id = str(group.get("group_id", ""))
                if group_id:
                    self.bot.data.add_group(group_id)
            print(f"[OneBot WS] 已同步 {len(groups)} 个群")
        except Exception as e:
            print(f"[OneBot WS] 同步群列表失败: {e}")
    
    def connect(self):
        """连接 WebSocket"""
        headers = {}
        if ONEBOT_ACCESS_TOKEN_HTTP:
            headers["Authorization"] = f"Bearer {ONEBOT_ACCESS_TOKEN_HTTP}"
        
        self.ws = websocket.WebSocketApp(
            ONEBOT_WS_URL + '/?access_token=' + ONEBOT_ACCESS_TOKEN_WS,
            header=headers,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )

        print(ONEBOT_WS_URL + '/?access_token=' + ONEBOT_ACCESS_TOKEN_WS)
        
        # 运行 WebSocket（带自动重连）
        while True:
            try:
                print(f"[OneBot WS] 正在连接 {ONEBOT_WS_URL}...")
                self.ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception as e:
                print(f"[OneBot WS] 连接异常: {e}")
            
            if not self.connected:
                print(f"[OneBot WS] {self.reconnect_interval} 秒后重连...")
                time.sleep(self.reconnect_interval)
    
    def start(self):
        """在后台线程启动 WebSocket"""
        thread = threading.Thread(target=self.connect, daemon=True)
        thread.start()
        return thread


# ============== 机器人管理器 ==============
class QQBot:
    """QQ 机器人管理器"""
    
    def __init__(self):
        self.data = DataManager(DATA_FILE)
        self.qq_api = QQBotAPI()
        self.message_handler = MessageHandler(self.data, self.qq_api)
        self.onebot_ws: OneBotWebSocket = None
        
        # 设置 webhook handler 的依赖
        WebhookHandler.data_manager = self.data
        WebhookHandler.qq_api = self.qq_api
    
    def start_webhook_server(self):
        """启动 webhook 服务器"""
        server = HTTPServer(('0.0.0.0', WEBHOOK_PORT), WebhookHandler)
        print(f"[Webhook] 服务器已启动: http://0.0.0.0:{WEBHOOK_PORT}")
        server.serve_forever()
    
    def start_onebot_ws(self):
        """启动 OneBot WebSocket 客户端"""
        self.onebot_ws = OneBotWebSocket(self)
        return self.onebot_ws.start()
    
    def on_private_message(self, qq_number: str, message: str):
        """
        处理私聊消息的入口点
        """
        self.message_handler.handle_private_message(qq_number, message)
    
    def on_group_message(self, group_id: str, qq_number: str, message: str):
        """
        处理群消息的入口点
        """
        self.message_handler.handle_group_message(group_id, qq_number, message)
    
    def on_group_join(self, group_id: str):
        """
        机器人加入群时调用
        """
        self.data.add_group(group_id)
        print(f"[Bot] 已加入群: {group_id}")
    
    def on_group_leave(self, group_id: str):
        """机器人离开群时调用"""
        self.data.remove_group(group_id)
        print(f"[Bot] 已离开群: {group_id}")


# ============== 主程序 ==============
def main():
    """主函数"""
    print("=" * 50)
    print("QQ 机器人启动中...")
    print("=" * 50)
    
    bot = QQBot()
    
    # 启动 webhook 服务器（在后台线程）
    webhook_thread = threading.Thread(target=bot.start_webhook_server, daemon=True)
    webhook_thread.start()
    
    # 启动 OneBot WebSocket 客户端（在后台线程）
    onebot_thread = bot.start_onebot_ws()
    
    # 启动定时备份调度器（在后台线程）
    backup_scheduler = BackupScheduler()
    backup_thread = backup_scheduler.start()
    
    # 获取登录信息
    time.sleep(2)  # 等待连接建立
    login_info = QQBotAPI.get_login_info()
    if login_info:
        print(f"\n[Bot] 登录账号: {login_info.get('nickname')} ({login_info.get('user_id')})")
    
    print("\n机器人已就绪！")
    print("\n可用命令：")
    print("  私聊: /bind <用户ID> - 绑定账号")
    print("  私聊: /verify <验证码> - 验证绑定")
    print("  群聊: /noti - 设置本群为优先通知群")
    print("\n按 Ctrl+C 退出")
    
    # 保持主线程运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n机器人已停止")


if __name__ == "__main__":
    main()
