#!/usr/bin/env python3
"""
配置文件

存放所有需要统一管理的配置项。
修改此文件中的配置后，所有模块都会生效。
"""

from pathlib import Path

# ============== 服务器配置 ==============
# 后端 API 地址（正式环境请修改此处）
ENDPOINT = ""

# QQ 机器人 Token（用于 webhook 验证）
TOKEN = ""

# ============== OneBot 配置 ==============
# OneBot HTTP API 地址
ONEBOT_HTTP_URL = ""
# OneBot WebSocket 地址
ONEBOT_WS_URL = ""
# OneBot HTTP 认证 Token
ONEBOT_ACCESS_TOKEN_HTTP = ""
# OneBot WebSocket 认证 Token
ONEBOT_ACCESS_TOKEN_WS = ""

# ============== 本地文件配置 ==============
# 数据存储目录
DATA_DIR = Path(__file__).parent
# 绑定数据文件
DATA_FILE = DATA_DIR / "data.json"

# ============== Webhook 配置 ==============
# Webhook 服务器监听端口
WEBHOOK_PORT = 9999

# ============== 备份配置 ==============
# 备份仓库本地路径
BACKUP_REPO_PATH = DATA_DIR / "backup_repo"
# GitHub 仓库远程 URL（首次克隆时需要，SSH 格式推荐）
BACKUP_REMOTE_URL = "https://github.com/CelesteCNCoders/CNHistBackup"
# 每天备份时间（小时，24小时制）
BACKUP_HOUR = 4
# 每天备份时间（分钟）
BACKUP_MINUTE = 0

# ============== 绑定配置 ==============
# 验证码有效期（秒）
VERIFICATION_TIMEOUT = 300
# 绑定请求冷却时间（秒）
BIND_COOLDOWN = 60
