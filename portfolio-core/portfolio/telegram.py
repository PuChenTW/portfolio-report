import os
import tempfile
import urllib.request
import urllib.error

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendDocument"


def send_telegram_file(
    html_content: str,
    filename: str = "daily_report.html",
) -> str:
    """Upload an HTML string as a file to a Telegram chat via Bot API sendDocument."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return "Error: TELEGRAM_BOT_TOKEN not set"
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not chat_id:
        return "Error: TELEGRAM_CHAT_ID not set"

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        ) as f:
            f.write(html_content)
            tmp_path = f.name

        boundary = "----FormBoundary7MA4YWxkTrZu0gW"
        with open(tmp_path, "rb") as f:
            file_data = f.read()

        body = (
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
                f"{chat_id}\r\n"
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'
                f"Content-Type: text/html\r\n\r\n"
            ).encode()
            + file_data
            + f"\r\n--{boundary}--\r\n".encode()
        )

        url = _TELEGRAM_API.format(token=token)
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 200:
                return f"✅ 已傳送至 Telegram（chat_id: {chat_id}）"
            return f"Error {resp.status}"
    except urllib.error.HTTPError as e:
        return f"Error {e.code}: {e.read().decode()}"
    except Exception as e:
        return f"Error: {e}"
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
