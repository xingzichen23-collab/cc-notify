#!/usr/bin/env python3
"""
Claude Code 通知脚本 — cc-notify v3
通过飞书/企业微信 Webhook 发送通知，支持四种事件类型：

  --event userpromptsubmit  用户提交提示词 → 保存任务名
  --event pretooluse        工具即将执行   → 写入状态文件
  --event stop              Claude 停止     → 判断并发送通知（待处理 / 处理完毕）
  --event posttooluse       工具执行完毕   → 清理状态文件

纯标准库实现，无需 pip install 任何依赖。
"""

import sys
import json
import os
import urllib.request
import urllib.error
import time
from datetime import datetime

# ── 配置 ──────────────────────────────────────────────

STATE_FILE = os.path.expanduser("~/.claude/cc-notify-state.json")
STATE_TTL = 60  # 状态文件有效期（秒），超过视为过期
PROMPT_FILE = os.path.expanduser("~/.claude/cc-notify-prompt.json")


# ── 工具函数 ──────────────────────────────────────────

def load_config():
    """加载配置文件 ~/.claude/cc-notify-config.json"""
    config_path = os.path.expanduser("~/.claude/cc-notify-config.json")
    if not os.path.exists(config_path):
        return None
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(data: dict):
    """将待处理状态写入文件"""
    data["timestamp"] = time.time()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def load_state() -> dict | None:
    """读取状态文件，如果过期则返回 None 并清理"""
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        age = time.time() - data.get("timestamp", 0)
        if age > STATE_TTL:
            os.remove(STATE_FILE)
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def clear_state():
    """删除状态文件"""
    try:
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
    except OSError:
        pass


def save_prompt(user_prompt: str):
    """保存用户原始提问作为任务名"""
    if not user_prompt.strip():
        return
    # 取第一行或前 80 字符作为任务名
    task_name = user_prompt.strip().split("\n")[0].strip()
    if len(task_name) > 80:
        task_name = task_name[:80] + "..."
    # 清理可能的编码问题字符
    task_name = task_name.encode("utf-8", errors="surrogateescape").decode("utf-8", errors="replace")
    data = {"task_name": task_name, "timestamp": time.time()}
    try:
        with open(PROMPT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except (OSError, UnicodeEncodeError):
        pass


def load_prompt() -> str | None:
    """读取任务名，如果文件不存在返回 None"""
    if not os.path.exists(PROMPT_FILE):
        return None
    try:
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("task_name")
    except (json.JSONDecodeError, OSError):
        return None


def summarize_tool(tool_name: str, tool_input: dict) -> str:
    """将工具调用信息总结为一行简短描述"""
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        desc = tool_input.get("description", "")
        if desc:
            return f"Bash: {desc}"
        # 截断过长命令
        if len(cmd) > 150:
            cmd = cmd[:150] + "..."
        return f"Bash: {cmd}"
    elif tool_name in ("Write", "Edit"):
        fp = tool_input.get("file_path", "unknown")
        return f"写入文件: {fp}"
    elif tool_name == "MultiEdit":
        fp = tool_input.get("file_path", "unknown")
        edits = tool_input.get("edits", [])
        return f"批量编辑 ({len(edits)}处): {fp}"
    elif tool_name == "Read":
        fp = tool_input.get("file_path", "unknown")
        return f"读取文件: {fp}"
    elif tool_name == "Glob":
        pattern = tool_input.get("pattern", "")
        return f"搜索文件: {pattern}"
    elif tool_name == "Grep":
        pattern = tool_input.get("pattern", "")
        return f"搜索内容: {pattern}"
    elif tool_name == "WebFetch":
        url = tool_input.get("url", "")
        return f"获取网页: {url[:100]}"
    elif tool_name == "WebSearch":
        query = tool_input.get("query", "")
        return f"搜索网络: {query[:100]}"
    else:
        return f"{tool_name}"


def send_feishu_post(webhook_url: str, title: str, lines: list[str]):
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


def send_wecom_markdown(webhook_url: str, title: str, lines: list[str]):
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


def send_notification(config: dict, title: str, lines: list[str]):
    """统一发送入口，根据平台选择发送方式"""
    platform = config.get("platform", "feishu")
    webhook_url = config.get("webhook_url", "").strip()
    if not webhook_url:
        return
    if platform == "wecom":
        send_wecom_markdown(webhook_url, title, lines)
    else:
        send_feishu_post(webhook_url, title, lines)


# ── 事件处理器 ────────────────────────────────────────

def handle_userpromptsubmit(input_data: dict):
    """UserPromptSubmit: 保存用户原始提问作为任务名"""
    # Claude Code hook 实际字段名是 "prompt"，不是 "user_prompt"
    user_prompt = input_data.get("prompt", "").strip()
    if user_prompt:
        save_prompt(user_prompt)


# 永远安全的工具——纯读取，不通知
ALWAYS_SILENT = {"Read", "Glob", "Grep", "Task", "TaskList", "TaskGet",
                 "TaskCreate", "TaskUpdate", "TaskOutput", "TaskStop",
                 "EnterPlanMode", "ExitPlanMode", "CronList",
                 "Skill", "AskUserQuestion"}

# acceptEdits 模式下自动放行的编辑工具，不通知
ACCEPT_EDIT_SILENT = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def should_notify(input_data: dict) -> bool:
    """判断当前工具是否需要通知用户"""
    tool_name = input_data.get("tool_name", "")
    if not tool_name:
        return False
    # 纯读取/查询类工具永远不通知
    if tool_name in ALWAYS_SILENT:
        return False
    # acceptEdits 模式下，编辑工具自动放行
    permission_mode = input_data.get("permission_mode", "")
    if permission_mode == "acceptEdits" and tool_name in ACCEPT_EDIT_SILENT:
        return False
    return True


def handle_pretooluse(input_data: dict):
    """PreToolUse: 有风险的操作立即通知，安全操作只写状态"""
    config = load_config()
    if config is None or not config.get("enabled", True):
        return

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    if not tool_name:
        return

    tool_summary = summarize_tool(tool_name, tool_input)
    save_state({
        "tool_name": tool_name,
        "tool_summary": tool_summary,
    })

    if not should_notify(input_data):
        return  # 安全工具，不发通知

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    task_name = load_prompt()
    if task_name:
        title = f"⏳ 待处理 — {task_name}"
    else:
        title = "⏳ Claude Code — 待处理操作"
    lines = [
        f"**操作**：{tool_summary}",
        f"**时间**：{now}",
        "",
        "---",
        "请回到终端确认此操作",
    ]
    send_notification(config, title, lines)


def handle_stop(input_data: dict):
    """Stop: 任务处理完毕，发送完成通知"""
    config = load_config()
    if config is None or not config.get("enabled", True):
        clear_state()
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    task_name = load_prompt()
    state = load_state()

    if state is not None:
        # 工具被阻止（用户拒绝），通知已在 PreToolUse 时发过
        clear_state()
        return

    # 无待处理工具 → 任务处理完毕
    if task_name:
        title = f"✅ 处理完毕 — {task_name}"
    else:
        title = "✅ Claude Code — 任务处理完毕"
    lines = [
        f"**时间**：{now}",
        "",
        "---",
        "可以查看结果或继续下一步",
    ]
    send_notification(config, title, lines)


def handle_posttooluse(input_data: dict):
    """PostToolUse: 清理状态文件（工具自动放行/已执行完毕）"""
    clear_state()


# ── 入口 ──────────────────────────────────────────────

def main():
    event = "stop"  # 默认
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--event" and i + 1 < len(args):
            event = args[i + 1]
        elif arg.startswith("--event="):
            event = arg.split("=", 1)[1]

    try:
        # 从 stdin 读取原始字节并解码为 UTF-8（Windows 管道默认非 UTF-8）
        raw = sys.stdin.buffer.read()
        input_data = json.loads(raw.decode("utf-8"))

        if event == "userpromptsubmit":
            handle_userpromptsubmit(input_data)
        elif event == "pretooluse":
            handle_pretooluse(input_data)
        elif event == "stop":
            handle_stop(input_data)
        elif event == "posttooluse":
            handle_posttooluse(input_data)
        else:
            # 兼容旧版（无 --event 参数）
            handle_stop(input_data)

    except Exception:
        # 静默处理所有异常 — 绝不阻塞 Claude Code
        pass
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
