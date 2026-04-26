from portfolio.telegram import send_telegram_file, send_telegram_messages


class TelegramNotifier:
    def send_messages(self, messages: list[str]) -> None:
        send_telegram_messages(messages)

    def send_file(self, html_content: str, filename: str = "report.html") -> None:
        send_telegram_file(html_content, filename=filename)
