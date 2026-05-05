from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from researcher.handlers.chat import (
    _sessions,
    handle_chat,
    reset_chat_session,
)


@pytest.fixture(autouse=True)
def clear_sessions():
    _sessions.clear()
    yield
    _sessions.clear()


def test_reset_clears_existing_history():
    _sessions[1] = [MagicMock()]
    reply = reset_chat_session(1)
    assert 1 not in _sessions
    assert "重置" in reply


def test_reset_with_no_session_does_not_raise():
    reply = reset_chat_session(999)
    assert "重置" in reply


async def test_handle_chat_stores_history_after_reply():
    mock_result = MagicMock()
    mock_result.output = "Hello back"
    mock_result.all_messages.return_value = [MagicMock()]

    with patch("researcher.handlers.chat._get_agent") as mock_get_agent, patch("researcher.handlers.chat._append_chat_log"):
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_result)
        mock_get_agent.return_value = mock_agent

        reply = await handle_chat("Hello", user_id=42)

    assert reply == "Hello back"
    assert 42 in _sessions
    assert len(_sessions[42]) == 1


async def test_handle_chat_passes_existing_history():
    existing_msg = MagicMock()
    _sessions[42] = [existing_msg]

    mock_result = MagicMock()
    mock_result.output = "Follow-up response"
    mock_result.all_messages.return_value = [existing_msg, MagicMock()]

    with patch("researcher.handlers.chat._get_agent") as mock_get_agent, patch("researcher.handlers.chat._append_chat_log"):
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_result)
        mock_get_agent.return_value = mock_agent

        await handle_chat("Follow-up", user_id=42)
        call_kwargs = mock_agent.run.call_args.kwargs
        assert call_kwargs["message_history"] == [existing_msg]


async def test_handle_chat_appends_to_chat_log_each_turn():
    mock_result = MagicMock()
    mock_result.output = "Answer"
    mock_result.all_messages.return_value = [MagicMock()]

    with patch("researcher.handlers.chat._get_agent") as mock_get_agent, patch("researcher.handlers.chat._append_chat_log") as mock_log:
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_result)
        mock_get_agent.return_value = mock_agent

        await handle_chat("Question", user_id=1)

        mock_log.assert_called_once_with("Question", "Answer")


async def test_handle_chat_error_returns_fallback_and_skips_log():
    with patch("researcher.handlers.chat._get_agent") as mock_get_agent, patch("researcher.handlers.chat._append_chat_log") as mock_log:
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=Exception("API error"))
        mock_get_agent.return_value = mock_agent

        reply = await handle_chat("Hello", user_id=1)

    assert "抱歉" in reply
    assert 1 not in _sessions
    mock_log.assert_not_called()


async def test_handle_chat_different_users_have_separate_history():
    msgs_10 = [MagicMock()]
    msgs_20 = [MagicMock(), MagicMock()]
    call_count = {"n": 0}

    async def fake_run(prompt, *, deps, message_history):
        call_count["n"] += 1
        result = MagicMock()
        result.output = "A" if call_count["n"] == 1 else "B"
        result.all_messages.return_value = msgs_10 if call_count["n"] == 1 else msgs_20
        return result

    with patch("researcher.handlers.chat._get_agent") as mock_get_agent, patch("researcher.handlers.chat._append_chat_log"):
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=fake_run)
        mock_get_agent.return_value = mock_agent

        await handle_chat("msg", user_id=10)
        await handle_chat("msg", user_id=20)

    assert _sessions[10] is msgs_10
    assert _sessions[20] is msgs_20
    assert _sessions[10] is not _sessions[20]


def test_append_chat_log_writes_exchange(tmp_path, monkeypatch):
    from researcher.config import settings
    from researcher.handlers.chat import _append_chat_log

    monkeypatch.setattr(settings, "researcher_memory_path", str(tmp_path))

    _append_chat_log("TSLA 怎麼樣?", "TSLA 近期表現...")

    log_path = tmp_path / "CHAT-LOG.md"
    assert log_path.exists()
    content = log_path.read_text()
    assert "TSLA 怎麼樣?" in content
    assert "TSLA 近期表現..." in content
    assert "**User**:" in content
    assert "**Bot**:" in content


def test_append_chat_log_accumulates_multiple_turns(tmp_path, monkeypatch):
    from researcher.config import settings
    from researcher.handlers.chat import _append_chat_log

    monkeypatch.setattr(settings, "researcher_memory_path", str(tmp_path))

    _append_chat_log("第一問", "第一答")
    _append_chat_log("第二問", "第二答")

    content = (tmp_path / "CHAT-LOG.md").read_text()
    assert "第一問" in content
    assert "第二問" in content


def _make_ctx(deps):
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


def _make_test_agent():
    from researcher.config import settings
    with patch.object(settings, "chat_model", "test"):
        from researcher.handlers.chat import _make_agent
        return _make_agent()


def _make_chat_deps(tmp_path):
    from researcher.handlers.chat import _ChatDeps
    from researcher.services.transaction_log import MarkdownTransactionLog

    return _ChatDeps(
        memory_path=str(tmp_path),
        watchlist_path=str(tmp_path / "w.csv"),
        portfolio_path=str(tmp_path / "p.csv"),
        transaction_log=MarkdownTransactionLog(str(tmp_path / "TRANSACTION-LOG.md")),
    )


def test_update_holding_tool_delegates_to_handler(tmp_path):
    deps = _make_chat_deps(tmp_path)

    with patch("researcher.handlers.chat.handle_update_holding", return_value="Updated TSLA: 10.0 shares @ 250.0.") as mock_update:
        agent = _make_test_agent()
        tool_fn = agent._function_toolset.tools["update_holding"].function
        result = tool_fn(_make_ctx(deps), ticker="TSLA", shares=10.0, cost_price=250.0, reason="調整")

    mock_update.assert_called_once_with(["TSLA", "10.0", "250.0"], deps.portfolio_path, "調整", deps.transaction_log)
    assert "Updated" in result


def test_add_holding_tool_delegates_to_handler(tmp_path):
    deps = _make_chat_deps(tmp_path)

    with patch("researcher.handlers.chat.handle_add_holding", return_value="Added NVDA (Nvidia): 5.0 shares @ 800.0 [USD / 美股].") as mock_add:
        agent = _make_test_agent()
        tool_fn = agent._function_toolset.tools["add_holding"].function
        result = tool_fn(_make_ctx(deps), ticker="NVDA", name="Nvidia", shares=5.0, cost_price=800.0, currency="USD", category="美股", reason="長期持有")

    mock_add.assert_called_once_with(["NVDA", "Nvidia", "5.0", "800.0", "USD", "美股"], deps.portfolio_path, "長期持有", deps.transaction_log)
    assert "Added" in result


def test_remove_holding_tool_delegates_to_handler(tmp_path):
    deps = _make_chat_deps(tmp_path)

    with patch("researcher.handlers.chat.handle_remove_holding", return_value="Removed TSLA from portfolio.") as mock_remove:
        agent = _make_test_agent()
        tool_fn = agent._function_toolset.tools["remove_holding"].function
        result = tool_fn(_make_ctx(deps), ticker="TSLA", reason="止損")

    mock_remove.assert_called_once_with(["TSLA"], deps.portfolio_path, "止損", deps.transaction_log)
    assert "Removed" in result


def test_read_transaction_log_tool_returns_entries(tmp_path):
    log = tmp_path / "TRANSACTION-LOG.md"
    # Write a recent entry (today's date so entries_since picks it up)
    from datetime import date
    today = date.today().isoformat()
    log.write_text(f"## {today} 14:32 UPDATE TSLA\nshares=10.0 cost=250.0\n")
    deps = _make_chat_deps(tmp_path)

    agent = _make_test_agent()
    tool_fn = agent._function_toolset.tools["read_transaction_log"].function
    result = tool_fn(_make_ctx(deps), since_days=1)

    assert "UPDATE TSLA" in result


def test_read_transaction_log_tool_empty(tmp_path):
    deps = _make_chat_deps(tmp_path)

    agent = _make_test_agent()
    tool_fn = agent._function_toolset.tools["read_transaction_log"].function
    result = tool_fn(_make_ctx(deps))

    assert "無持倉異動紀錄" in result
