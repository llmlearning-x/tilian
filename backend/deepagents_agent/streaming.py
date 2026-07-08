"""
把 deepagents / LangGraph 的 astream chunk 转换为前端可展示的 SSE 事件。
"""
import json
from typing import Any


def format_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    """
    将 LangGraph chunk 格式化为前端友好的事件。

    输出字段：
    - type: "thought" | "tool_call" | "tool_result" | "todo" | "final" | "raw"
    - content: 文本内容
    - tool_name: 工具名（tool_call/tool_result 时）
    - tool_args: 工具参数（tool_call 时）
    - tool_result: 工具返回结果（tool_result 时）
    - todos: TODO 列表（todo 时）
    """
    # 模型消息：AI 思考内容或工具调用
    if "model" in chunk:
        messages = chunk["model"].get("messages", [])
        if not messages:
            return {"type": "raw", "content": "", "raw": _safe_json(chunk)}

        msg = messages[-1]
        content = getattr(msg, "content", "") or ""
        tool_calls = getattr(msg, "tool_calls", None) or []

        if tool_calls:
            # 返回第一个工具调用信息（通常一次只有一个）
            call = tool_calls[0]
            return {
                "type": "tool_call",
                "content": content,
                "tool_name": call.get("name"),
                "tool_args": call.get("args"),
            }

        # 没有工具调用的纯思考内容
        return {"type": "thought", "content": content}

    # 工具执行结果
    if "tools" in chunk:
        # 可能是工具返回消息，也可能是 todo 列表更新
        if "todos" in chunk["tools"]:
            return {
                "type": "todo",
                "todos": chunk["tools"]["todos"],
            }

        messages = chunk["tools"].get("messages", [])
        if messages:
            msg = messages[-1]
            return {
                "type": "tool_result",
                "tool_name": getattr(msg, "name", None),
                "tool_result": getattr(msg, "content", ""),
            }

        return {"type": "raw", "content": "", "raw": _safe_json(chunk)}

    # TODO middleware
    if any(key.endswith("TodoListMiddleware.after_model") for key in chunk):
        return {"type": "heartbeat", "content": ""}

    # 其他 middleware 事件
    if any(key.endswith(".before_agent") for key in chunk):
        return {"type": "start", "content": "Agent 开始整理"}

    return {"type": "raw", "content": "", "raw": _safe_json(chunk)}


def _safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return str(obj)
