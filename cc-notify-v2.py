#!/usr/bin/env python3
"""
Claude Code 通知脚本 — cc-notify v2
基于官方 Notification Hook + Stop Hook，通过飞书/企业微信 Webhook 发送通知。

  --event notification   权限请求 → ⏳ 待处理
  --event stop           任务完成 → ✅ 处理完毕

纯标准库实现，无需 pip install 任何依赖。
"""

import sys
import json
import os
import urllib.request
from datetime import datetime


# ── 配置加载 ──────────────────────────────────────────

def load_config():
    config_path = os.path.expanduser("~/.claude/cc-notify-config.json")
    if not os.path.exists(config_path):
        return None
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_prompt():
    """从 prompt 文件读取当前任务名（由旧版或 UserPromptSubmit hook 写入）"""
    prompt_file = os.path.expanduser("~/.claude/cc-notify-prompt.json")
    if not os.path.exists(prompt_file):
        return None
    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("task_name")
    except (json.JSONDecodeError, OSError):
        return None


# ── 飞书 / 企微发送 ───────────────────────────────────

def send_feishu(webhook_url: str, title: str, lines: list[str]):
    """通过飞书自定义机器人发送富文本消息"""
    content_blocks = [[{"tag": "text", "text": line}] for line in lines]
    data = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": title,
                    "content": content_blocks,
                }
            }
        },
    }
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.read()


def send_wecom(webhook_url: str, title: str, lines: list[str]):
    """通过企业微信群机器人发送 Markdown 消息"""
    content = f"## {title}\n" + "\n".join(lines)
    data = {"msgtype": "markdown", "markdown": {"content": content}}
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.read()


def notify(config: dict, title: str, lines: list[str]):
    """统一发送入口"""
    platform = config.get("platform", "feishu")
    webhook_url = config.get("webhook_url", "").strip()
    if not webhook_url:
        return
    if platform == "wecom":
        send_wecom(webhook_url, title, lines)
    else:
        send_feishu(webhook_url, title, lines)


# ── 通知生成 ──────────────────────────────────────────

def format_permission_notification(msg: str, title: str | None) -> tuple[str, list[str]]:
    """生成"待处理"通知的标题和内容"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    task_name = load_prompt()

    if task_name:
        notify_title = f"⏳ 待处理 — {task_name}"
    elif title:
        notify_title = f"⏳ 待处理 — {title}"
    else:
        notify_title = "⏳ Claude Code — 待处理操作"

    lines = [
        f"**内容**：{msg}",
        f"**时间**：{now}",
        "",
        "---",
        "请回到终端处理",
    ]
    return notify_title, lines


def format_done_notification() -> tuple[str, list[str]]:
    """生成"处理完毕"通知的标题和内容"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    task_name = load_prompt()

    if task_name:
        notify_title = f"✅ 处理完毕 — {task_name}"
    else:
        notify_title = "✅ Claude Code — 任务处理完毕"

    lines = [
        f"**时间**：{now}",
        "",
        "---",
        "可以查看结果或继续下一步",
    ]
    return notify_title, lines


# ── 事件处理 ──────────────────────────────────────────

def handle_notification(input_data: dict):
    """处理 Notification hook 事件"""
    config = load_config()
    if config is None or not config.get("enabled", True):
        return

    notification_type = input_data.get("notification_type", "")
    if notification_type != "permission_prompt":
        return  # 只关注权限请求，忽略 auth_success、idle_prompt 等

    message = input_data.get("message", "需要你的操作")
    title = input_data.get("title", "")
    notify_title, lines = format_permission_notification(message, title)
    notify(config, notify_title, lines)


def handle_stop(input_data: dict):
    """处理 Stop hook 事件 — 任务完成通知"""
    config = load_config()
    if config is None or not config.get("enabled", True):
        return

    notify_title, lines = format_done_notification()
    notify(config, notify_title, lines)


# ── 入口 ──────────────────────────────────────────────

def main():
    event = "notification"
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--event" and i + 1 < len(args):
            event = args[i + 1]
        elif arg.startswith("--event="):
            event = arg.split("=", 1)[1]

    # 诊断日志：每次被调用都写时间戳
    log_path = os.path.expanduser("~/.claude/cc-notify-debug.log")
    try:
        raw = sys.stdin.buffer.read()
        input_data = json.loads(raw.decode("utf-8"))
        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(f"[{datetime.now().isoformat()}] event={event} input_keys={list(input_data.keys())}\n")

        if event == "notification":
            handle_notification(input_data)
        elif event == "stop":
            handle_stop(input_data)
    except Exception as e:
        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(f"[{datetime.now().isoformat()}] ERROR: {e}\n")
        pass
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
