---
name: cc-notify
description: >
  Set up Claude Code hook notifications via Feishu/WeCom webhook bots.
  Sends distinct messages when Claude needs permission approval (⏳ pending)
  vs when a task is complete (✅ done). Never miss a prompt again.
triggers:
  - setup notification
  - set up notification
  - configure feishu notification
  - configure wechat notification
  - 设置通知
  - 配置飞书提醒
  - 配置微信通知
  - cc-notify
---

# cc-notify — Claude Code 通知提醒 v2

当 Claude Code 需要人工介入或任务完成时，通过飞书/企业微信机器人发送**不同类型**的消息提醒。

---

## 通知类型

| 场景 | 消息 | 内容 |
|------|------|------|
| 需要用户确权 | ⏳ **待处理操作** | 工具名、操作摘要、时间 |
| 任务处理完毕 | ✅ **任务处理完毕** | 时间 |

### 示例

**待确权时：**
> ⏳ Claude Code — 待处理操作
>
> 操作：Bash: npm install react
> 时间：2026-06-06 14:30:00
>
> ---
> 请回到终端确认此操作

**任务完成时：**
> ✅ Claude Code — 任务处理完毕
>
> 时间：2026-06-06 14:32:00
>
> ---
> 可以查看结果或继续下一步

---

## 工作原理

```
PreToolUse 触发 → 写入状态文件（记录工具信息）
       │
       ├─ 工具需确权 → Stop 触发 → 读到状态 → 发 ⏳ "待处理" → 清除状态
       │
       └─ 工具已授权 → PostToolUse 触发 → 清除状态（不通知）
       │
（处理...）
       │
Stop 触发 → 无状态文件 → 发 ✅ "任务处理完毕"
```

---

## 前置条件

1. **Python 3** 可用（命令行可运行 `python`）
2. **飞书自定义机器人** 已创建，拥有 Webhook URL

---

## 安装与配置

### Step 1：获取 Webhook URL（如已有可跳过）

**飞书**：
1. 目标飞书群 → 设置 → 群机器人 → 添加机器人 → 自定义机器人
2. 复制 Webhook 地址（格式：`https://open.feishu.cn/open-apis/bot/v2/hook/xxx`）

### Step 2：创建配置文件

`~/.claude/cc-notify-config.json`：

```json
{
  "platform": "feishu",
  "webhook_url": "你的 Webhook URL",
  "enabled": true
}
```

### Step 3：配置 Hooks

在 `~/.claude/settings.json` 中添加：

```json
{
  "hooks": {
    "PreToolUse": [{
      "hooks": [{
        "type": "command",
        "command": "python ~/.claude/scripts/cc-notify.py --event pretooluse",
        "timeout": 5
      }]
    }],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "python ~/.claude/scripts/cc-notify.py --event stop",
        "timeout": 10
      }]
    }],
    "PostToolUse": [{
      "hooks": [{
        "type": "command",
        "command": "python ~/.claude/scripts/cc-notify.py --event posttooluse",
        "timeout": 5
      }]
    }]
  }
}
```

### Step 4：测试

```bash
# 模拟待确权流程
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"npm test"}}' | python ~/.claude/scripts/cc-notify.py --event pretooluse
echo '{"hook_event_name":"Stop","reason":""}' | python ~/.claude/scripts/cc-notify.py --event stop
# → 应该收到 ⏳ "待处理操作" 消息

# 模拟任务完成
echo '{"hook_event_name":"Stop","reason":""}' | python ~/.claude/scripts/cc-notify.py --event stop
# → 应该收到 ✅ "任务处理完毕" 消息
```

---

## 常见问题

### Q: 会影响 Claude Code 正常运行吗？
不会。脚本设计为"静默失败"——任何错误都不会阻塞 Claude Code。

### Q: 如何关闭通知？
将 `cc-notify-config.json` 中 `enabled` 设为 `false`。

### Q: 如何卸载？
删除以下内容：
- `~/.claude/scripts/cc-notify.py`
- `~/.claude/cc-notify-config.json`
- `~/.claude/cc-notify-state.json`
- 从 `~/.claude/settings.json` 中移除 `hooks.PreToolUse`、`hooks.Stop`、`hooks.PostToolUse` 三个配置
