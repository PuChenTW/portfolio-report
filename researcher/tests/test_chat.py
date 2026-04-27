from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from researcher.handlers.chat import (
    _sessions,
    handle_chat,
    reset_chat_session,
    save_chat_to_memory,
)


@pytest.fixture(autouse=True)
def clear_sessions():
    _sessions.clear()
    yield
    _sessions.clear()


def test_reset_clears_existing_history():
    _sessions[1] = [MagicMock()]
    result = reset_chat_session(1)
    assert 1 not in _sessions
    assert "重置" in result


def test_reset_with_no_session_does_not_raise():
    result = reset_chat_session(999)
    assert "重置" in result


async def test_handle_chat_stores_history_after_reply():
    mock_result = MagicMock()
    mock_result.output = "Hello back"
    mock_result.all_messages.return_value = [MagicMock()]

    with patch("researcher.handlers.chat._get_agent") as mock_get_agent:
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

    with patch("researcher.handlers.chat._get_agent") as mock_get_agent:
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_result)
        mock_get_agent.return_value = mock_agent

        await handle_chat("Follow-up", user_id=42)
        call_kwargs = mock_agent.run.call_args.kwargs
        assert call_kwargs["message_history"] == [existing_msg]


async def test_handle_chat_error_returns_fallback():
    with patch("researcher.handlers.chat._get_agent") as mock_get_agent:
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=Exception("API error"))
        mock_get_agent.return_value = mock_agent

        reply = await handle_chat("Hello", user_id=1)

    assert "抱歉" in reply
    assert 1 not in _sessions


async def test_handle_chat_different_users_have_separate_history():
    msgs_10 = [MagicMock()]
    msgs_20 = [MagicMock(), MagicMock()]

    call_count = {"n": 0}

    async def fake_run(prompt, *, deps, message_history):
        call_count["n"] += 1
        if call_count["n"] == 1:
            result = MagicMock()
            result.output = "A"
            result.all_messages.return_value = msgs_10
            return result
        result = MagicMock()
        result.output = "B"
        result.all_messages.return_value = msgs_20
        return result

    with patch("researcher.handlers.chat._get_agent") as mock_get_agent:
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=fake_run)
        mock_get_agent.return_value = mock_agent

        await handle_chat("msg", user_id=10)
        await handle_chat("msg", user_id=20)

    assert _sessions[10] is msgs_10
    assert _sessions[20] is msgs_20
    assert _sessions[10] is not _sessions[20]


async def test_save_chat_no_history_returns_message():
    reply = await save_chat_to_memory(user_id=99)
    assert "沒有" in reply


async def test_save_chat_with_history_calls_agent_and_returns_summary():
    _sessions[5] = [MagicMock()]

    mock_result = MagicMock()
    mock_result.output = "摘要：討論了 TSLA 前景"

    with patch("researcher.handlers.chat._get_agent") as mock_get_agent:
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_result)
        mock_get_agent.return_value = mock_agent

        reply = await save_chat_to_memory(user_id=5)

        # agent.run should be called with the existing history as message_history
        call_kwargs = mock_agent.run.call_args.kwargs
        assert call_kwargs["message_history"] == _sessions[5]

    assert "已儲存" in reply
    assert "TSLA" in reply


async def test_save_chat_error_returns_failure_message():
    _sessions[7] = [MagicMock()]

    with patch("researcher.handlers.chat._get_agent") as mock_get_agent:
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=Exception("timeout"))
        mock_get_agent.return_value = mock_agent

        reply = await save_chat_to_memory(user_id=7)

    assert "失敗" in reply
