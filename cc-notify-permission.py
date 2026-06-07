"""Claude Code Notification hook — permission_prompt → Feishu/WeCom"""
import sys, json, os, urllib.request


def load_config():
    config_path = os.path.expanduser("~/.claude/cc-notify-config.json")
    if not os.path.exists(config_path):
        return None
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    raw = sys.stdin.buffer.read()
    data = json.loads(raw.decode("utf-8"))
    if data.get("notification_type") != "permission_prompt":
        return

    config = load_config()
    if config is None or not config.get("enabled", True):
        return

    webhook_url = config.get("webhook_url", "").strip()
    if not webhook_url:
        return

    msg = data.get("message", "")
    title = data.get("title", "")
    text = f"{title}: {msg}" if title else msg
    body_text = f"⏳ 待处理 — {text}\n\n---\n请回到终端处理"

    body = json.dumps({
        "msg_type": "text",
        "content": {"text": body_text}
    }).encode()

    req = urllib.request.Request(webhook_url, data=body,
        headers={"Content-Type": "application/json; charset=utf-8"})
    urllib.request.urlopen(req, timeout=5)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
