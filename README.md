# cc-notify

Claude Code 通知提醒工具 — 当 Claude Code 需要人工介入或任务完成时，通过飞书/企业微信机器人发送消息提醒。

## 功能

| 场景 | 通知 | 示例 |
|------|------|------|
| 需要用户确权 | ⏳ 待处理 + 操作详情 | `⏳ 待处理 — 帮我重构认证模块` |
| 任务处理完毕 | ✅ 处理完毕 | `✅ 处理完毕 — 帮我重构认证模块` |

## 工作原理

```
UserPromptSubmit → 保存任务名
PreToolUse       → 记录待确权工具
Stop → 有状态? → ⏳ 待处理通知
     → 无状态? → ✅ 处理完毕通知
PostToolUse      → 清理状态
```

## 快速开始

### 方式一：让 Claude Code 帮你安装（推荐）

直接对 Claude Code 说：

> 帮我安装 cc-knock 通知工具，仓库地址是 https://github.com/xingzichen23-colla/cc-knock ，我的飞书 Webhook 是 https://open.feishu.cn/open-apis/bot/v2/hook/你的key

Claude Code 会自动完成以下所有步骤：
1. 克隆仓库到本地
2. 复制脚本到 `~/.claude/scripts/`
3. 创建配置文件并填入你的 Webhook URL
4. 在 `~/.claude/settings.json` 中配置四个 Hook
5. 发送测试消息验证

你只需要提前准备好飞书机器人的 Webhook URL 即可。

### 方式二：手动安装

#### 1. 创建飞书机器人

飞书群 → 设置 → 群机器人 → 添加机器人 → 自定义机器人 → 复制 Webhook URL

#### 2. 安装

```bash
# 克隆仓库
git clone https://github.com/xingzichen23-colla/cc-knock.git ~/projects/cc-knock

# 复制脚本到 Claude Code 目录
mkdir -p ~/.claude/scripts
cp ~/projects/cc-knock/cc-notify.py ~/.claude/scripts/cc-notify.py

# 创建配置文件，填入你的 Webhook URL
cp ~/projects/cc-knock/cc-notify-config.example.json ~/.claude/cc-notify-config.json
# 编辑 ~/.claude/cc-notify-config.json，填入真实的 webhook_url
```

#### 3. 配置 Claude Code Hooks

在 `~/.claude/settings.json` 中添加：

```json
{
  "hooks": {
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "python ~/.claude/scripts/cc-notify.py --event userpromptsubmit", "timeout": 5}]}],
    "PreToolUse": [{"hooks": [{"type": "command", "command": "python ~/.claude/scripts/cc-notify.py --event pretooluse", "timeout": 5}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "python ~/.claude/scripts/cc-notify.py --event stop", "timeout": 10}]}],
    "PostToolUse": [{"hooks": [{"type": "command", "command": "python ~/.claude/scripts/cc-notify.py --event posttooluse", "timeout": 5}]}]
  }
}
```

#### 4. 测试

```bash
# 模拟完整流程
echo '{"hook_event_name":"UserPromptSubmit","user_prompt":"测试任务"}' | python ~/.claude/scripts/cc-notify.py --event userpromptsubmit
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"echo test"}}' | python ~/.claude/scripts/cc-notify.py --event pretooluse
echo '{"hook_event_name":"Stop","reason":""}' | python ~/.claude/scripts/cc-notify.py --event stop
echo '{"hook_event_name":"Stop","reason":""}' | python ~/.claude/scripts/cc-notify.py --event stop
```

成功的话，飞书会收到两条消息（⏳ 待处理 + ✅ 处理完毕）。

## 配置说明

`~/.claude/cc-notify-config.json`：

```json
{
  "platform": "feishu",
  "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
  "enabled": true
}
```

| 字段 | 说明 |
|------|------|
| `platform` | `"feishu"` 或 `"wecom"` |
| `webhook_url` | 飞书/企微机器人 Webhook 地址 |
| `enabled` | `true` 开启，`false` 关闭 |

## 文件说明

```
cc-knock/
├── README.md                        # 本文件
├── cc-notify.py                     # 核心脚本（纯标准库，零依赖）
├── cc-notify-config.example.json    # 配置文件模板
├── .gitignore                       # Git 忽略规则
└── SKILL.md                         # Claude Code Skill 定义（可选）
```

## 卸载

```bash
rm ~/.claude/scripts/cc-notify.py
rm ~/.claude/cc-notify-config.json
rm ~/.claude/cc-notify-state.json
rm ~/.claude/cc-notify-prompt.json
# 从 ~/.claude/settings.json 移除 hooks 中的四个配置
```

## 常见问题

**Q: 会影响 Claude Code 正常运行吗？**  
不会。脚本所有异常静默处理，始终 exit 0，绝不阻塞 Claude Code。

**Q: 如何关闭通知？**  
将 `cc-notify-config.json` 中 `enabled` 设为 `false`。

**Q: 支持哪些平台？**  
飞书自定义机器人（`feishu`）和企业微信群机器人（`wecom`）。
