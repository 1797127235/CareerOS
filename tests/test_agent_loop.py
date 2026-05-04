"""Agent Loop 测试 — 验证 ReAct Loop 核心逻辑

测试场景：
- 简单对话（无工具调用）
- 单工具调用
- 多工具调用
- 重复工具调用检测
- 工具调用错误处理
- 最大步数限制
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.backend.agent.agent_loop import AgentResult, AgentStep, agent_loop
from app.backend.agent.tools import Tool, ToolRegistry


async def collect_agent_result(gen):
    """收集 agent_loop 生成器的所有输出"""
    tokens = []
    result = None
    async for item in gen:
        if isinstance(item, str):
            tokens.append(item)
        elif isinstance(item, AgentResult):
            result = item
    return tokens, result


@pytest.fixture
def mock_registry():
    """创建包含 mock 工具的注册表"""
    registry = ToolRegistry()

    async def mock_get_profile(user_id: str = None, db=None) -> str:
        return json.dumps({
            "name": "测试用户",
            "school": "测试大学",
            "major": "计算机科学",
        }, ensure_ascii=False)

    async def mock_update_profile(fields: dict, user_id: str = None, db=None) -> str:
        return json.dumps({"updated": list(fields.keys())}, ensure_ascii=False)

    registry.register(Tool(
        name="get_profile",
        description="读取用户画像",
        parameters={"type": "object", "properties": {}},
        handler=mock_get_profile,
        requires_db=True,
    ))

    registry.register(Tool(
        name="update_profile",
        description="更新用户画像",
        parameters={
            "type": "object",
            "properties": {
                "fields": {"type": "object", "description": "要更新的字段"},
            },
            "required": ["fields"],
        },
        handler=mock_update_profile,
        requires_db=True,
    ))

    return registry


def make_tool_call_delta(tc_id: str, name: str, arguments: str, index: int = 0):
    """创建 tool_call delta 对象，模拟 LiteLLM 流式响应格式"""
    func_mock = MagicMock()
    func_mock.name = name
    func_mock.arguments = arguments

    tc_mock = MagicMock()
    tc_mock.id = tc_id
    tc_mock.function = func_mock
    tc_mock.index = index

    return tc_mock


@pytest.mark.asyncio
async def test_simple_chat_no_tools(mock_registry):
    """简单对话：LLM 直接回复，不调用工具"""
    with patch("app.backend.agent.agent_loop.chat_stream", new_callable=MagicMock) as mock_stream:
        async def mock_stream_gen(*args, **kwargs):
            yield "你好！"
            yield "有什么可以帮助你的吗？"

        mock_stream.side_effect = lambda *args, **kwargs: mock_stream_gen()

        tokens, result = await collect_agent_result(agent_loop(
            user_input="你好",
            system_prompt="你是 CareerOS 助手",
            history_messages=[],
            task_type="general_chat",
            registry=mock_registry,
        ))

        assert isinstance(result, AgentResult)
        assert result.final_response == "你好！有什么可以帮助你的吗？"
        assert len(result.steps) == 1
        assert result.steps[0].step_type == "llm_call"
        assert result.tool_calls_count == 0
        assert len(tokens) == 2  # 两个 token


@pytest.mark.asyncio
async def test_single_tool_call(mock_registry):
    """单工具调用：LLM 调用 get_profile，然后回复"""
    call_count = 0

    with patch("app.backend.agent.agent_loop.chat_stream", new_callable=MagicMock) as mock_stream:
        async def mock_stream_gen(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # 第一次调用：返回 tool_calls
                yield {"tool_calls": [
                    make_tool_call_delta("call_1", "get_profile", "{}", 0)
                ]}
            else:
                # 第二次调用：返回最终回复
                yield "你的学校是测试大学，专业是计算机科学。"

        mock_stream.side_effect = lambda *args, **kwargs: mock_stream_gen()

        tokens, result = await collect_agent_result(agent_loop(
            user_input="我是谁",
            system_prompt="你是 CareerOS 助手",
            history_messages=[],
            task_type="general_chat",
            db=MagicMock(),
            user_id="test_user",
            registry=mock_registry,
        ))

        assert "测试大学" in result.final_response
        assert result.tool_calls_count == 1
        assert len(result.steps) == 3  # llm_call + tool_call + llm_call


@pytest.mark.asyncio
async def test_multi_tool_calls(mock_registry):
    """多工具调用：LLM 同时调用多个工具"""
    call_count = 0

    with patch("app.backend.agent.agent_loop.chat_stream", new_callable=MagicMock) as mock_stream:
        async def mock_stream_gen(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # 第一次调用：返回多个 tool_calls
                yield {"tool_calls": [
                    make_tool_call_delta("call_1", "get_profile", "{}", 0),
                    make_tool_call_delta("call_2", "update_profile", json.dumps({"fields": {"city": "北京"}}), 1),
                ]}
            else:
                # 第二次调用：返回最终回复
                yield "已更新你的意向城市为北京。"

        mock_stream.side_effect = lambda *args, **kwargs: mock_stream_gen()

        tokens, result = await collect_agent_result(agent_loop(
            user_input="我想去北京工作",
            system_prompt="你是 CareerOS 助手",
            history_messages=[],
            task_type="general_chat",
            db=MagicMock(),
            user_id="test_user",
            registry=mock_registry,
        ))

        assert "北京" in result.final_response
        assert result.tool_calls_count == 2


@pytest.mark.asyncio
async def test_duplicate_tool_call_detection(mock_registry):
    """重复工具调用检测：相同参数的调用应该被跳过"""
    call_count = 0

    with patch("app.backend.agent.agent_loop.chat_stream", new_callable=MagicMock) as mock_stream:
        async def mock_stream_gen(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # 第一次调用：返回 tool_calls
                yield {"tool_calls": [
                    make_tool_call_delta("call_1", "get_profile", "{}", 0)
                ]}
            elif call_count == 2:
                # 第二次调用：返回相同的 tool_calls（重复）
                yield {"tool_calls": [
                    make_tool_call_delta("call_2", "get_profile", "{}", 0)
                ]}
            else:
                # 第三次调用：返回最终回复
                yield "我已经获取了你的画像信息。"

        mock_stream.side_effect = lambda *args, **kwargs: mock_stream_gen()

        tokens, result = await collect_agent_result(agent_loop(
            user_input="获取我的画像",
            system_prompt="你是 CareerOS 助手",
            history_messages=[],
            task_type="general_chat",
            db=MagicMock(),
            user_id="test_user",
            registry=mock_registry,
        ))

        # 第二次调用应该被跳过，但仍然记录为 tool_call
        assert result.tool_calls_count == 2


@pytest.mark.asyncio
async def test_tool_call_error_handling(mock_registry):
    """工具调用失败：应该优雅处理错误"""
    # 注册一个会抛出异常的工具
    async def failing_tool():
        raise ValueError("工具执行失败")

    mock_registry.register(Tool(
        name="failing_tool",
        description="会失败的工具",
        parameters={"type": "object", "properties": {}},
        handler=failing_tool,
    ))

    call_count = 0

    with patch("app.backend.agent.agent_loop.chat_stream", new_callable=MagicMock) as mock_stream:
        async def mock_stream_gen(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # 第一次调用：返回 tool_calls
                yield {"tool_calls": [
                    make_tool_call_delta("call_1", "failing_tool", "{}", 0)
                ]}
            else:
                # 第二次调用：返回最终回复
                yield "抱歉，工具执行失败了。"

        mock_stream.side_effect = lambda *args, **kwargs: mock_stream_gen()

        tokens, result = await collect_agent_result(agent_loop(
            user_input="调用失败的工具",
            system_prompt="你是 CareerOS 助手",
            history_messages=[],
            task_type="general_chat",
            registry=mock_registry,
        ))

        # 工具调用失败，但循环应该继续
        assert result.tool_calls_count == 1
        # 检查步骤中是否有失败记录
        tool_steps = [s for s in result.steps if s.step_type == "tool_call"]
        assert len(tool_steps) == 1
        # ToolRegistry.execute() 捕获异常并返回错误字符串
        # 所以从 agent_loop 视角看，工具调用"成功"了（返回了字符串）
        assert "工具执行失败" in tool_steps[0].content


@pytest.mark.asyncio
async def test_max_steps_limit(mock_registry):
    """最大步数限制：超过限制应该返回错误消息"""
    with patch("app.backend.agent.agent_loop.chat_stream", new_callable=MagicMock) as mock_stream:
        # 总是返回 tool_calls，模拟无限循环
        async def mock_stream_gen(*args, **kwargs):
            yield {"tool_calls": [
                make_tool_call_delta("call_1", "get_profile", "{}", 0)
            ]}

        mock_stream.side_effect = lambda *args, **kwargs: mock_stream_gen()

        tokens, result = await collect_agent_result(agent_loop(
            user_input="无限循环测试",
            system_prompt="你是 CareerOS 助手",
            history_messages=[],
            task_type="general_chat",
            max_steps=3,  # 设置较小的步数限制
            db=MagicMock(),
            user_id="test_user",
            registry=mock_registry,
        ))

        # 应该返回错误消息
        assert "遇到了问题" in result.final_response
        # 验证最后一步的 step_number 是 max_steps
        last_step = result.steps[-1]
        assert last_step.step_number == 3


@pytest.mark.asyncio
async def test_agent_result_structure(mock_registry):
    """验证 AgentResult 结构"""
    with patch("app.backend.agent.agent_loop.chat_stream", new_callable=MagicMock) as mock_stream:
        async def mock_stream_gen(*args, **kwargs):
            yield "测试回复"

        mock_stream.side_effect = lambda *args, **kwargs: mock_stream_gen()

        tokens, result = await collect_agent_result(agent_loop(
            user_input="测试",
            system_prompt="你是 CareerOS 助手",
            history_messages=[],
            task_type="general_chat",
            registry=mock_registry,
        ))

        assert isinstance(result, AgentResult)
        assert hasattr(result, "final_response")
        assert hasattr(result, "steps")
        assert hasattr(result, "total_duration_ms")
        assert hasattr(result, "tool_calls_count")
        assert isinstance(result.steps, list)
        assert result.total_duration_ms >= 0


@pytest.mark.asyncio
async def test_agent_step_structure(mock_registry):
    """验证 AgentStep 结构"""
    with patch("app.backend.agent.agent_loop.chat_stream", new_callable=MagicMock) as mock_stream:
        async def mock_stream_gen(*args, **kwargs):
            yield "测试回复"

        mock_stream.side_effect = lambda *args, **kwargs: mock_stream_gen()

        tokens, result = await collect_agent_result(agent_loop(
            user_input="测试",
            system_prompt="你是 CareerOS 助手",
            history_messages=[],
            task_type="general_chat",
            registry=mock_registry,
        ))

        step = result.steps[0]
        assert isinstance(step, AgentStep)
        assert hasattr(step, "step_number")
        assert hasattr(step, "step_type")
        assert hasattr(step, "content")
        assert hasattr(step, "tool_name")
        assert hasattr(step, "tool_args")
        assert hasattr(step, "duration_ms")
        assert hasattr(step, "success")
        assert hasattr(step, "error")


@pytest.mark.asyncio
async def test_history_messages_included(mock_registry):
    """验证历史消息被正确包含在 LLM 调用中"""
    with patch("app.backend.agent.agent_loop.chat_stream", new_callable=MagicMock) as mock_stream:
        async def mock_stream_gen(*args, **kwargs):
            yield "测试回复"

        mock_stream.side_effect = lambda *args, **kwargs: mock_stream_gen()

        history = [
            {"role": "user", "content": "历史消息1"},
            {"role": "assistant", "content": "历史回复1"},
        ]

        tokens, result = await collect_agent_result(agent_loop(
            user_input="新消息",
            system_prompt="系统提示",
            history_messages=history,
            task_type="general_chat",
            registry=mock_registry,
        ))

        # 验证传给 LLM 的消息包含历史
        call_args = mock_stream.call_args
        messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][1]

        # 消息应该包含：system + history + user
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "历史消息1"
        assert messages[2]["role"] == "assistant"
        assert messages[2]["content"] == "历史回复1"
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "新消息"
