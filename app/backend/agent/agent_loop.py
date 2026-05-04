"""Agent 循环 — ReAct Loop 核心逻辑

实现 Thought → Action → Observation 循环：
1. LLM 决定是否调用工具
2. 如果调用工具 → 执行工具 → 观察结果 → 继续循环
3. 如果不调用工具 → 返回最终回复

支持：
- 最大步数限制（防止无限循环）
- 循环检测（防止重复调用）
- 流式输出最终回复
- 工具调用失败处理
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from app.backend.agent.llm_router import TaskType, chat_stream
from app.backend.agent.tools import ToolRegistry, tool_registry

logger = logging.getLogger(__name__)

MAX_STEPS = 5
MAX_RECENT_CALLS = 3


@dataclass
class AgentStep:
    step_number: int
    step_type: str  # "llm_call" | "tool_call" | "tool_result"
    content: str
    tool_name: str | None = None
    tool_args: dict | None = None
    duration_ms: int = 0
    success: bool = True
    error: str | None = None


@dataclass
class AgentResult:
    final_response: str
    steps: list[AgentStep] = field(default_factory=list)
    total_duration_ms: int = 0
    tool_calls_count: int = 0


async def agent_loop(
    user_input: str,
    system_prompt: str,
    history_messages: list[dict],
    task_type: TaskType = "general_chat",
    max_steps: int = MAX_STEPS,
    db: Any = None,
    user_id: str | None = None,
    registry: ToolRegistry | None = None,
) -> AsyncIterator[str | AgentResult]:
    """ReAct Loop 核心循环（流式）

    参数：
        user_input: 用户输入
        system_prompt: 系统提示词（由 orchestrator 组装）
        history_messages: 历史消息列表
        task_type: 任务类型（决定用哪个模型）
        max_steps: 最大循环步数
        db: 数据库 session（工具需要）
        user_id: 用户 ID（工具需要）
        registry: 工具注册表（默认使用全局注册表）

    Yields：
        str: 流式 token（最终回复的一部分）
        AgentResult: 最终结果（最后 yield）

    使用方式：
        async for item in agent_loop(...):
            if isinstance(item, str):
                # 流式 token
                print(item, end="")
            else:
                # AgentResult
                result = item
    """
    reg = registry or tool_registry
    tools_schema = reg.get_schemas()
    steps: list[AgentStep] = []
    start_time = time.time()
    tool_calls_count = 0

    # 构建初始消息
    messages = [
        {"role": "system", "content": system_prompt},
        *history_messages,
        {"role": "user", "content": user_input},
    ]

    # 循环检测：记录最近的工具调用签名
    recent_calls: list[str] = []

    for step_num in range(1, max_steps + 1):
        step_start = time.time()

        # 1. 流式调用 LLM
        content_buffer = ""
        tool_calls_buffer: list[dict] = []

        try:
            async for token in chat_stream(
                task_type=task_type,
                messages=messages,
                tools=tools_schema if tools_schema else None,
                max_tokens=4096,  # 增加 token 限制，避免长回复被截断
            ):
                if isinstance(token, str):
                    # 普通文本 token
                    content_buffer += token
                    yield token  # 流式输出给调用方
                elif isinstance(token, dict) and "tool_calls" in token:
                    # tool_calls chunk，需要累积
                    for tc_delta in token["tool_calls"]:
                        # 找到或创建对应的 tool_call
                        tc_index = tc_delta.index if hasattr(tc_delta, "index") else 0
                        while len(tool_calls_buffer) <= tc_index:
                            tool_calls_buffer.append(
                                {
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            )
                        tc = tool_calls_buffer[tc_index]
                        if hasattr(tc_delta, "id") and tc_delta.id:
                            tc["id"] = tc_delta.id
                        if hasattr(tc_delta, "function") and tc_delta.function:
                            if hasattr(tc_delta.function, "name") and tc_delta.function.name:
                                tc["function"]["name"] = tc_delta.function.name
                            if hasattr(tc_delta.function, "arguments") and tc_delta.function.arguments:
                                tc["function"]["arguments"] += tc_delta.function.arguments
        except Exception as e:
            logger.error("LLM 调用失败 (step %d): %s", step_num, e)
            steps.append(
                AgentStep(
                    step_number=step_num,
                    step_type="llm_call",
                    content="",
                    duration_ms=int((time.time() - step_start) * 1000),
                    success=False,
                    error=str(e),
                )
            )
            break

        # 2. 检查是否有 tool_calls
        if tool_calls_buffer and any(tc["id"] for tc in tool_calls_buffer):
            # LLM 返回了 tool_calls
            steps.append(
                AgentStep(
                    step_number=step_num,
                    step_type="llm_call",
                    content=content_buffer or f"[决定调用 {len(tool_calls_buffer)} 个工具]",
                    duration_ms=int((time.time() - step_start) * 1000),
                )
            )

            # 3. 执行工具调用
            tool_messages = []  # 收集所有 tool 消息
            for tc in tool_calls_buffer:
                if not tc["id"]:
                    continue

                tool_name = tc["function"]["name"]
                tool_args_str = tc["function"]["arguments"]
                tool_call_id = tc["id"]

                try:
                    tool_args = json.loads(tool_args_str) if isinstance(tool_args_str, str) else tool_args_str
                except json.JSONDecodeError:
                    tool_args = {}

                # 循环检测
                call_signature = f"{tool_name}:{json.dumps(tool_args, sort_keys=True)}"
                tool_start = time.time()
                if call_signature in recent_calls[-MAX_RECENT_CALLS:]:
                    logger.warning("检测到重复工具调用: %s", call_signature)
                    tool_result = f"检测到重复调用 {tool_name}，跳过执行。"
                    tool_success = False
                else:
                    recent_calls.append(call_signature)

                    try:
                        tool_result = await reg.execute(
                            name=tool_name,
                            arguments=tool_args,
                            db=db,
                            user_id=user_id,
                        )
                        tool_success = True
                    except Exception as e:
                        tool_result = f"工具执行失败：{e}"
                        tool_success = False
                        logger.error("工具执行失败: %s - %s", tool_name, e)

                steps.append(
                    AgentStep(
                        step_number=step_num,
                        step_type="tool_call",
                        content=tool_result,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        duration_ms=int((time.time() - tool_start) * 1000),
                        success=tool_success,
                    )
                )
                tool_calls_count += 1

                # 收集 tool 消息（不立即 append）
                tool_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": tool_result,
                    }
                )

            # 4. 一条 assistant 消息包含所有 tool_calls + 多条 tool 消息
            messages.append(
                {
                    "role": "assistant",
                    "content": content_buffer,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["function"]["name"],
                                "arguments": tc["function"]["arguments"],
                            },
                        }
                        for tc in tool_calls_buffer
                        if tc["id"]
                    ],
                }
            )
            messages.extend(tool_messages)

            # 继续循环，让 LLM 处理工具结果
            continue

        else:
            # LLM 返回了最终回复（已流式输出）
            final_response = content_buffer

            steps.append(
                AgentStep(
                    step_number=step_num,
                    step_type="llm_call",
                    content=final_response,
                    duration_ms=int((time.time() - step_start) * 1000),
                )
            )

            # yield 最终结果
            yield AgentResult(
                final_response=final_response,
                steps=steps,
                total_duration_ms=int((time.time() - start_time) * 1000),
                tool_calls_count=tool_calls_count,
            )
            return

    # 超过最大步数
    logger.warning("Agent 循环超过最大步数: %d", max_steps)
    yield AgentResult(
        final_response="抱歉，处理过程中遇到了问题，请稍后重试。",
        steps=steps,
        total_duration_ms=int((time.time() - start_time) * 1000),
        tool_calls_count=tool_calls_count,
    )
