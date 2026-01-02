#!/usr/bin/env python3
"""
定时备份模块

每天定时从 API 获取数据并备份到 GitHub 仓库。
"""

import json
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from config import (
    ENDPOINT,
    BACKUP_REPO_PATH, BACKUP_REMOTE_URL,
    BACKUP_HOUR, BACKUP_MINUTE
)

# 备份 API 地址（基于 ENDPOINT 构建）
BACKUP_API_URL = f"{ENDPOINT}/api/hist/export"


# ============== 备份调度器 ==============
class BackupScheduler:
    """定时备份调度器"""
    
    def __init__(
        self,
        api_url: str = BACKUP_API_URL,
        repo_path: Path = BACKUP_REPO_PATH,
        remote_url: str = BACKUP_REMOTE_URL,
        hour: int = BACKUP_HOUR,
        minute: int = BACKUP_MINUTE
    ):
        """
        初始化备份调度器
        
        Args:
            api_url: 备份数据的 API 地址
            repo_path: 本地 Git 仓库路径
            remote_url: GitHub 远程仓库 URL
            hour: 每天备份的小时（0-23）
            minute: 每天备份的分钟（0-59）
        """
        self.api_url = api_url
        self.repo_path = repo_path
        self.remote_url = remote_url
        self.hour = hour
        self.minute = minute
        self._thread: Optional[threading.Thread] = None
    
    def start(self) -> threading.Thread:
        """启动备份调度器（后台线程）"""
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._thread.start()
        return self._thread
    
    def _scheduler_loop(self):
        """调度器主循环"""
        print(f"[Backup] 定时备份已启动，每天 {self.hour:02d}:{self.minute:02d} 执行")
        last_backup_date = None
        
        while True:
            now = datetime.now()
            today = now.date()
            
            # 检查是否到达备份时间且今天还没备份
            if (now.hour == self.hour and 
                now.minute == self.minute and 
                last_backup_date != today):
                
                print(f"[Backup] 开始执行定时备份...")
                try:
                    self.run_backup()
                    last_backup_date = today
                    print(f"[Backup] 定时备份完成")
                except Exception as e:
                    print(f"[Backup] 备份失败: {e}")
            
            # 每 30 秒检查一次
            time.sleep(30)
    
    def run_backup(self):
        """执行一次备份任务"""
        print(f"[Backup] === HIST Leaderboard Backup ===")
        print(f"[Backup] Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Step 1: 从 API 获取数据
        print(f"[Backup] [1/4] Fetching data from API...")
        data = self._fetch_export_data()
        
        # Step 2: 确保仓库存在
        repo_path = self.repo_path.expanduser().resolve()
        print(f"[Backup] [2/4] Preparing repo: {repo_path}")
        self._ensure_repo(repo_path)
        
        # Step 3: 保存文件
        print(f"[Backup] [3/4] Saving export files...")
        self._save_export_files(data, repo_path)
        
        # Step 4: 提交并推送
        print(f"[Backup] [4/4] Committing and pushing...")
        self._git_commit_push(repo_path)
        
        print(f"[Backup] === Backup Complete ===")
    
    def _fetch_export_data(self) -> dict:
        """从 API 获取导出数据"""
        print(f"[Backup]   Fetching from: {self.api_url}")
        
        request = Request(
            self.api_url,
            headers={
                "Accept": "application/json",
                "User-Agent": "HIST-Backup-Script/1.0",
            }
        )
        
        try:
            with urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data
        except HTTPError as e:
            raise RuntimeError(f"HTTP Error {e.code}: {e.reason}")
        except URLError as e:
            raise RuntimeError(f"URL Error: {e.reason}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"JSON decode error: {e}")
    
    def _ensure_repo(self, repo_path: Path):
        """确保 Git 仓库存在"""
        if repo_path.exists() and (repo_path / ".git").exists():
            print("[Backup]   Repository exists, pulling latest...")
            self._run_cmd(["git", "pull", "--ff-only"], cwd=repo_path, check=False)
            return
        
        if repo_path.exists() and not (repo_path / ".git").exists():
            raise RuntimeError(f"RepoPath exists but is not a git repo: {repo_path}")
        
        if not self.remote_url:
            raise RuntimeError(
                f"RepoPath does not exist: {repo_path}\n"
                f"Please set BACKUP_REMOTE_URL to clone the repo on first run."
            )
        
        repo_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"[Backup]   Cloning from: {self.remote_url}")
        self._run_cmd(["git", "clone", self.remote_url, str(repo_path)])
    
    def _save_export_files(self, data: dict, repo_path: Path):
        """保存导出数据到文件"""
        data_dir = repo_path / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        
        meta = data.get("meta", {})
        summary = data.get("summary", {})
        maps = data.get("maps", [])
        players = data.get("players", [])
        runs = data.get("runs", [])
        
        # 保存各个 JSON 文件
        self._save_json(data_dir / "maps.json", {
            "meta": meta, "count": len(maps), "maps": maps
        })
        print(f"[Backup]   -> maps.json ({len(maps)} maps)")
        
        self._save_json(data_dir / "players.json", {
            "meta": meta, "count": len(players), "players": players
        })
        print(f"[Backup]   -> players.json ({len(players)} players)")
        
        self._save_json(data_dir / "runs.json", {
            "meta": meta, "count": len(runs), "runs": runs
        })
        print(f"[Backup]   -> runs.json ({len(runs)} runs)")
        
        self._save_json(data_dir / "summary.json", {
            "meta": meta, "statistics": summary.get("statistics", {})
        })
        print(f"[Backup]   -> summary.json")
        
        # 生成 README
        self._save_readme(repo_path, meta, summary)
        print("[Backup]   -> README.md")
    
    def _save_json(self, filepath: Path, data: dict):
        """保存 JSON 文件"""
        filepath.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    
    def _save_readme(self, repo_path: Path, meta: dict, summary: dict):
        """生成 README 文件"""
        stats = summary.get("statistics", {})
        exported_at = meta.get("exported_at", "")
        
        readme = f"""# HIST Leaderboard Backup

Auto-generated backup of HIST game leaderboard data.

## Statistics

| Metric | Value |
|--------|-------|
| Total Maps | {stats.get("total_maps", 0)} |
| Total Players | {stats.get("total_players", 0)} |
| Total Runs | {stats.get("total_runs", 0)} |

## Last Updated

{exported_at}

## Files

- data/maps.json - Map list with recommendation stats
- data/players.json - Player rankings
- data/runs.json - All completion records
- data/summary.json - Summary statistics
"""
        (repo_path / "README.md").write_text(readme, encoding="utf-8")
    
    def _git_commit_push(self, repo_path: Path):
        """提交并推送更改"""
        self._run_cmd(["git", "status"], cwd=repo_path)
        
        # 检查是否有变更
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_path),
            text=True,
            capture_output=True
        )
        
        if not result.stdout.strip():
            print("[Backup] No changes to commit.")
            return
        
        # 添加所有文件
        self._run_cmd(["git", "add", "-A"], cwd=repo_path)
        
        # 生成提交信息
        commit_msg = "Backup " + datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # 获取当前分支
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(repo_path),
            text=True,
            capture_output=True
        )
        branch = result.stdout.strip()
        
        if not branch:
            self._run_cmd(["git", "checkout", "-B", "main"], cwd=repo_path)
            branch = "main"
        
        # 提交并推送
        self._run_cmd(["git", "commit", "-m", commit_msg], cwd=repo_path)
        self._run_cmd(["git", "push", "-u", "origin", branch], cwd=repo_path)
    
    def _run_cmd(self, cmd: list, cwd: Path = None, check: bool = True) -> int:
        """运行命令并显示输出"""
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True
        )
        
        # 打印输出
        output = result.stdout + result.stderr
        for line in output.strip().split('\n'):
            if line:
                print(f"[Backup]   {line}")
        
        if check and result.returncode != 0:
            raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}")
        
        return result.returncode


# ============== 测试入口 ==============
if __name__ == "__main__":
    # 可以单独运行此文件来测试备份功能
    print("测试备份功能...")
    scheduler = BackupScheduler()
    
    # 手动执行一次备份
    try:
        scheduler.run_backup()
    except Exception as e:
        print(f"备份失败: {e}")
