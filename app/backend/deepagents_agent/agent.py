"""
题库整理 Agent 工厂与执行器。

本模块提供基于 LLM 的题库整理能力。针对 deepagents 在长输入或
复杂上下文下容易出现空回复、不稳定的问题，当前实现采用直接的
LLM 调用 + 校验循环：模型生成 JSON 后用平台 schema 自我校验，
未通过则反馈错误并再次生成，最多重试两次。

同时保留 `get_bank_import_agent` 签名，避免调用方改动；流式接口
生成与 deepagents 兼容的事件类型，前端无需修改。
"""
import json
import re
from typing import Any, AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from deepagents_agent.config import get_kimi_model
from deepagents_agent.prompts import BANK_IMPORT_AGENT_PROMPT
from deepagents_agent.tools import execute_python, validate_bank_json


def _extract_json(text: str) -> Any:
    """从模型回复中提取 JSON 对象，支持 markdown 代码块。"""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[1:])
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    return json.loads(cleaned)


def _build_initial_prompt(raw_text: str) -> str:
    return (
        f"{BANK_IMPORT_AGENT_PROMPT}\n\n"
        f"文档内容：\n```\n{raw_text}\n```\n\n"
        f"请直接输出JSON对象："
    )


def _build_fix_prompt(raw_text: str, previous_content: str, validation: str) -> str:
    return (
        f"你之前输出的JSON存在以下问题，请修正后重新输出完整JSON。\n\n"
        f"校验错误：\n{validation}\n\n"
        f"你之前的输出：\n```\n{previous_content}\n```\n\n"
        f"原始文档内容：\n```\n{raw_text}\n```\n\n"
        f"请直接输出修正后的完整JSON对象："
    )


CODE_GENERATION_PROMPT = """你是题库解析专家。请根据提供的文档样本格式，编写一段 Python 代码来解析完整文档并整理成标准题库 JSON。

代码要求：
1. 变量 `_bank_agent_input_text_` 已经由运行环境注入为字符串（包含完整文档），直接使用 `_bank_agent_input_text_`，绝对不要重新定义、覆盖或初始化它。
2. 根据样本格式选择合适的解析方式：正则、按行/制表符/分号分割、表格解析等。
3. 识别题目、选项、答案，每题必须有且只有 4 个选项，label 固定为 A/B/C/D。
4. 如果原文选项超过 4 个，请删除最不相关或合并多余选项，确保最终只有 A/B/C/D，并相应调整 answer。
5. 如果原文选项少于 4 个，请补充合理选项。
6. 单选题 type="single" 且 answer 长度为 1；多选题 type="multiple" 且 answer 长度至少为 2；answer 中必须是选项 label。
7. 为每题补充 explanation（如果原文没有解析，请依据题目材料写简要说明，不能留空）。
8. difficulty 取 1/2/3。
9. 输出必须是合法 JSON，使用 `print(json.dumps(result, ensure_ascii=False, indent=2))` 输出。
10. `name` 和 `description` 请根据文档主题（如天翼云、云计算、数据库等）自动生成，不要使用"题库名称"、"题库描述"等占位符。
11. 只输出 Python 代码，不要输出 ```python 等 markdown 标记，不要写 `if __name__ == '__main__':`，也不要附加任何说明文字。

请按以下解析框架编写代码（这是该文档最可靠的解析方式，请优先使用 split('\t') 而不是正则表达式）：
```python
lines = _bank_agent_input_text_.strip().split('\n')
questions = []
for line in lines:
    parts = [p.strip() for p in line.split('\t') if p.strip()]
    if len(parts) < 4 or parts[0] == '序号' or not parts[0].isdigit():
        continue
    idx, stem, options_str, answer = parts[0], parts[1], parts[2], parts[-1].strip().upper()
    raw_options = [o.strip() for o in re.split(r'\\s*;\\s*', options_str) if o.strip()]
    options = []
    for opt in raw_options:
        if ':' in opt:
            label, content = opt.split(':', 1)
            label = label.strip().upper()
            content = content.strip().strip('";)')
            if label in 'ABCDEF':
                options.append({'label': label, 'content': content})
    # 强制整理为 A/B/C/D 四个选项
    target_labels = ['A', 'B', 'C', 'D']
    # 如果原始答案在 E/F 等被删除的选项中，优先把这些选项中的第一个放入前4个
    answer_labels = [a for a in answer if a in 'ABCDEF']
    extra_correct = [opt for opt in options if opt['label'] in answer_labels and opt['label'] not in target_labels]
    options = [opt for opt in options if opt['label'] in target_labels]
    if extra_correct and len(options) < 4:
        # 用正确答案替换最后一个补充选项
        options.append({'label': target_labels[len(options)], 'content': extra_correct[0]['content']})
    while len(options) < 4:
        options.append({'label': target_labels[len(options)], 'content': '补充选项'})
    options = options[:4]
    # 确保 answer 只包含整理后 A/B/C/D 选项的 label
    final_labels = [opt['label'] for opt in options]
    answer = [a for a in answer_labels if a in final_labels]
    if not answer:
        answer = [final_labels[0]]
    question_type = 'single' if len(answer) == 1 else 'multiple'
    explanation = '正确答案是 ' + ', '.join(answer) + '。'
    questions.append({...})
```

标准输出格式：
{
  "name": "题库名称",
  "description": "题库描述",
  "questions": [
    {
      "type": "single" | "multiple",
      "stem": "题干",
      "options": [
        {"label": "A", "content": "..."},
        {"label": "B", "content": "..."},
        {"label": "C", "content": "..."},
        {"label": "D", "content": "..."}
      ],
      "answer": ["C"],
      "explanation": "...",
      "difficulty": 2
    }
  ]
}
"""


def _build_code_prompt(sample_text: str, full_length: int) -> str:
    sample_lines = sample_text.strip().split("\n")
    display_sample = "\n".join(sample_lines[:8])
    return (
        f"{CODE_GENERATION_PROMPT}\n\n"
        f"格式说明：\n"
        f"- 文档是制表符或连续空白分隔的表格/文本，每行对应一道题。\n"
        f"- 每行通常包含：序号、题干、选项文本、答案，字段之间用制表符或至少两个空格分隔。\n"
        f"- 选项文本中多个选项用分号 ; 分隔，每个选项形如 'A:内容'、'B:内容' 等。\n"
        f"- 答案通常是行的最后一个非空字段，可能是单个字母（如 A）或多个字母（如 ABC）。\n"
        f"- 如果某行选项数量不是 4 个，请通过删除/合并多余选项或补充合理选项，强制整理为 A/B/C/D 四个选项。\n\n"
        f"下面给出的是文档前 {len(sample_text)} 个字符中的前 8 行作为样本，"
        f"完整文档共约 {full_length} 个字符。请根据样本格式编写能够处理完整文档的 Python 代码。\n\n"
        f"文档样本：\n```\n{display_sample}\n```\n\n"
        f"请输出 Python 代码："
    )


def _build_code_fix_prompt(sample_text: str, full_length: int, previous_code: str, execution_result: str) -> str:
    sample_lines = sample_text.strip().split("\n")
    display_sample = "\n".join(sample_lines[:8])
    return (
        f"你之前编写的 Python 代码执行或校验失败，请修正后重新输出完整代码。\n\n"
        f"执行/校验结果：\n{execution_result}\n\n"
        f"你之前的代码：\n```\n{previous_code}\n```\n\n"
        f"格式提醒：每行通常包含：序号、题干、选项文本（用 ; 分隔，选项形如 A:内容）、答案。"
        f"文档样本（前 {len(sample_text)} 个字符中的前 8 行，完整文档约 {full_length} 个字符）：\n"
        f"```\n{display_sample}\n```\n\n"
        f"请输出修正后的完整 Python 代码（只输出代码，不要 markdown 标记）："
    )


def _extract_code(text: str) -> str:
    """从模型回复中提取 Python 代码，支持 markdown 代码块。"""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _sanitize_code(code: str) -> str:
    """
    清理 LLM 生成的代码：删除对输入变量的重复赋值，
    防止模型覆盖运行环境注入的 _bank_agent_input_text_。
    """
    lines = code.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # 删除形如 input_text = ... 或 _bank_agent_input_text_ = ... 的赋值
        if re.match(r"^(input_text|_bank_agent_input_text_)\s*=", stripped):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


async def _organize_by_code(raw_text: str) -> dict[str, Any] | None:
    """
    让 Agent 先编写 Python 代码解析文档，执行后验证。
    适合表格、规整文本等可通过代码快速处理的格式。
    为避免长文档超 token，只把前 5000 字符作为样本给模型，代码执行时使用完整文本。
    返回结果字典；若失败返回 None，调用方应 fallback 到其他策略。
    """
    sample_length = 5000
    sample_text = raw_text[:sample_length]
    # code-first 不需要工具调用，直接用 base model 生成代码即可
    model = get_kimi_model()
    messages: list[Any] = [
        SystemMessage(content=BANK_IMPORT_AGENT_PROMPT),
        HumanMessage(content=_build_code_prompt(sample_text, len(raw_text))),
    ]

    for attempt in range(2):
        response = await model.ainvoke(messages)
        code = _sanitize_code(_extract_code(response.content or ""))
        output = execute_python.invoke({"code": code, "input_text": raw_text})

        data: Any = None
        try:
            data = _extract_json(output)
        except Exception as exc:
            validation = f"代码输出 JSON 解析失败：{exc}\n代码输出：\n{output}"
        else:
            validation = validate_bank_json(data)

        if validation == "验证通过":
            return {"valid": True, "validation": validation, "data": data}

        messages.append(
            HumanMessage(
                content=_build_code_fix_prompt(sample_text, len(raw_text), code, validation)
            )
        )

    return None


def _split_text(raw_text: str, max_chars: int = 8000) -> list[str]:
    """按字符数分块，尽量在换行处分割，避免把一题截断。"""
    if len(raw_text) <= max_chars:
        return [raw_text]
    chunks = []
    start = 0
    while start < len(raw_text):
        end = start + max_chars
        if end >= len(raw_text):
            chunks.append(raw_text[start:])
            break
        # 在 end 附近找上一个换行，优先保留题目完整性
        newline_pos = raw_text.rfind("\n", start, end)
        if newline_pos == -1 or newline_pos == start:
            newline_pos = end
        chunks.append(raw_text[start:newline_pos])
        start = newline_pos
    return chunks


async def _organize_bank_single(raw_text: str) -> dict[str, Any]:
    """单块整理逻辑（核心工具调用循环）"""
    model = get_kimi_model().bind_tools([execute_python])
    messages: list[Any] = [
        SystemMessage(content=BANK_IMPORT_AGENT_PROMPT),
        HumanMessage(content=_build_initial_prompt(raw_text)),
    ]
    data: Any = None
    validation = "未知错误"

    for attempt in range(2):
        response = await model.ainvoke(messages)

        # 处理工具调用循环
        while response.tool_calls:
            tool_messages: list[ToolMessage] = []
            for tool_call in response.tool_calls:
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args", {})
                if tool_name == "execute_python":
                    output = execute_python.invoke(tool_args)
                else:
                    output = f"未知工具：{tool_name}"
                tool_messages.append(
                    ToolMessage(content=str(output), tool_call_id=tool_call.get("id", ""))
                )
            messages.extend([response, *tool_messages])
            response = await model.ainvoke(messages)

        last_content = response.content or ""

        try:
            data = _extract_json(last_content)
        except Exception as exc:
            data = None
            validation = f"JSON 解析失败：{exc}"
        else:
            validation = validate_bank_json(data)

        if validation == "验证通过":
            return {"valid": True, "validation": validation, "data": data}

        messages.append(HumanMessage(content=_build_fix_prompt(raw_text, last_content, validation)))

    return {"valid": False, "validation": validation, "data": data}


async def organize_bank(raw_text: str) -> dict[str, Any]:
    """
    同步整理文档为标准题库 JSON。

    返回字典包含 valid / validation / data 字段。
    实现为真正的工具调用 Agent：
    1. 优先尝试让模型编写 Python 代码解析文档（最快，适合规整格式）
    2. 代码方案失败后，fallback 到直接整理（单块或分块）

    当文档较长时，会自动按字符数分块整理，最后合并为一个题库。
    """
    # 优先尝试代码解析方案
    code_result = await _organize_by_code(raw_text)
    if code_result and code_result["valid"]:
        return code_result

    # 单块即可容纳时直接处理
    if len(raw_text) <= 10000:
        return await _organize_bank_single(raw_text)

    chunks = _split_text(raw_text, max_chars=8000)
    all_questions: list[Any] = []
    first_name = ""
    first_description = ""
    last_validation = code_result["validation"] if code_result else "未知错误"

    for idx, chunk in enumerate(chunks):
        result = await _organize_bank_single(chunk)
        if not result["valid"]:
            # 记录最后失败原因，但继续处理后续块，尽量多保留可用题目
            last_validation = result["validation"]
            continue
        data = result["data"]
        if not first_name:
            first_name = data.get("name", "")
            first_description = data.get("description", "")
        all_questions.extend(data.get("questions", []))

    if not all_questions:
        return {"valid": False, "validation": last_validation, "data": None}

    merged = {
        "name": first_name or "整理题库",
        "description": first_description,
        "questions": all_questions,
    }
    validation = validate_bank_json(merged)
    if validation != "验证通过":
        return {"valid": False, "validation": validation, "data": merged}

    return {"valid": True, "validation": validation, "data": merged}


async def _organize_bank_stream_single(
    raw_text: str,
) -> AsyncGenerator[dict[str, Any], None]:
    """单块流式整理（核心工具调用循环）。"""
    model = get_kimi_model().bind_tools([execute_python])
    messages: list[Any] = [
        SystemMessage(content=BANK_IMPORT_AGENT_PROMPT),
        HumanMessage(content=_build_initial_prompt(raw_text)),
    ]
    last_content = ""
    data: Any = None
    validation = "未知错误"

    yield {"type": "thought", "content": "正在分析文档内容并整理为标准题库 JSON..."}

    for attempt in range(2):
        response = await model.ainvoke(messages)

        # 真实工具调用循环
        while response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args", {})
                # 避免 SSE 消息过大，对大参数做摘要展示
                display_args: dict[str, Any] = {}
                if tool_name == "execute_python":
                    display_args = {
                        "code_length": len(tool_args.get("code", "")),
                        "input_length": len(tool_args.get("input_text", "")),
                    }
                else:
                    display_args = {k: v for k, v in tool_args.items()}
                yield {
                    "type": "tool_call",
                    "content": "",
                    "tool_name": tool_name,
                    "tool_args": display_args,
                }
                if tool_name == "execute_python":
                    output = execute_python.invoke(tool_args)
                else:
                    output = f"未知工具：{tool_name}"
                # 避免 SSE 消息过大，tool_result 截断展示
                yield {
                    "type": "tool_result",
                    "tool_name": tool_name,
                    "tool_result": output[:500] + ("..." if len(output) > 500 else ""),
                }
                tool_message = ToolMessage(
                    content=str(output), tool_call_id=tool_call.get("id", "")
                )
                messages.extend([response, tool_message])
            response = await model.ainvoke(messages)

        last_content = response.content or ""
        yield {
            "type": "tool_result",
            "tool_name": "llm_generate",
            "tool_result": f"生成 {len(last_content)} 字符",
        }

        try:
            data = _extract_json(last_content)
        except Exception as exc:
            data = None
            validation = f"JSON 解析失败：{exc}"
        else:
            validation = validate_bank_json(data)

        # validate_bank_json 的 data 可能很大，用摘要替代
        question_count = 0
        if isinstance(data, dict) and isinstance(data.get("questions"), list):
            question_count = len(data["questions"])
        yield {
            "type": "tool_call",
            "content": "",
            "tool_name": "validate_bank_json",
            "tool_args": {"question_count": question_count},
        }
        yield {
            "type": "tool_result",
            "tool_name": "validate_bank_json",
            "tool_result": validation,
        }

        if validation == "验证通过":
            yield {"type": "chunk_done", "valid": True, "data": data}
            return

        yield {
            "type": "thought",
            "content": f"第 {attempt + 1} 次校验未通过，正在修正：{validation}",
        }
        messages.append(HumanMessage(content=_build_fix_prompt(raw_text, last_content, validation)))

    yield {"type": "chunk_done", "valid": False, "validation": validation, "data": data}


async def _organize_bank_stream_code(
    raw_text: str,
) -> AsyncGenerator[dict[str, Any], None]:
    """流式执行 code-first 解析方案，生成兼容前端的事件。"""
    sample_length = 5000
    sample_text = raw_text[:sample_length]
    model = get_kimi_model()
    messages: list[Any] = [
        SystemMessage(content=BANK_IMPORT_AGENT_PROMPT),
        HumanMessage(content=_build_code_prompt(sample_text, len(raw_text))),
    ]

    for attempt in range(2):
        yield {
            "type": "thought",
            "content": f"正在生成 Python 解析代码（尝试 {attempt + 1}）...",
        }
        response = await model.ainvoke(messages)
        code = _sanitize_code(_extract_code(response.content or ""))

        yield {
            "type": "tool_call",
            "content": "",
            "tool_name": "execute_python",
            "tool_args": {
                "code_length": len(code),
                "input_length": len(raw_text),
            },
        }
        output = execute_python.invoke({"code": code, "input_text": raw_text})
        yield {
            "type": "tool_result",
            "tool_name": "execute_python",
            "tool_result": output[:500] + ("..." if len(output) > 500 else ""),
        }

        data: Any = None
        try:
            data = _extract_json(output)
        except Exception as exc:
            data = None
            validation = f"代码输出 JSON 解析失败：{exc}\n代码输出：\n{output}"
        else:
            validation = validate_bank_json(data)

        # validate_bank_json 的 data 可能很大，用摘要替代
        question_count = 0
        if isinstance(data, dict) and isinstance(data.get("questions"), list):
            question_count = len(data["questions"])
        yield {
            "type": "tool_call",
            "content": "",
            "tool_name": "validate_bank_json",
            "tool_args": {"question_count": question_count},
        }
        yield {
            "type": "tool_result",
            "tool_name": "validate_bank_json",
            "tool_result": validation,
        }

        if validation == "验证通过":
            yield {"type": "final", "valid": True, "validation": validation, "data": data}
            return

        messages.append(
            HumanMessage(
                content=_build_code_fix_prompt(sample_text, len(raw_text), code, validation)
            )
        )

    yield {"type": "final", "valid": False, "validation": validation, "data": data}


async def organize_bank_stream(raw_text: str) -> AsyncGenerator[dict[str, Any], None]:
    """
    流式整理文档，生成前端兼容的 SSE 事件。

    事件类型与 deepagents 保持一致：start / thought / tool_call /
    tool_result / final / heartbeat。
    现在工具调用是真实的：模型可先调用 execute_python 预处理文档。
    长文档会自动分块，流式输出每块的处理过程。
    """
    yield {"type": "start", "content": "Agent 开始整理"}

    # 优先尝试 code-first 快速路径
    code_final: dict[str, Any] | None = None
    async for event in _organize_bank_stream_code(raw_text):
        if event.get("type") == "final":
            code_final = event
            break
        yield event

    if code_final and code_final.get("valid"):
        yield code_final
        return

    yield {
        "type": "thought",
        "content": "代码解析未成功，切换到分块整理模式...",
    }

    if len(raw_text) <= 10000:
        async for event in _organize_bank_stream_single(raw_text):
            if event.get("type") == "chunk_done":
                yield {
                    "type": "final",
                    "valid": event["valid"],
                    "validation": event.get("validation", "验证通过"),
                    "data": event.get("data"),
                }
            else:
                yield event
        return

    chunks = _split_text(raw_text, max_chars=8000)
    all_questions: list[Any] = []
    first_name = ""
    first_description = ""
    last_validation = "未知错误"

    for idx, chunk in enumerate(chunks):
        yield {
            "type": "thought",
            "content": f"正在处理第 {idx + 1}/{len(chunks)} 块文档（{len(chunk)} 字符）...",
        }
        async for event in _organize_bank_stream_single(chunk):
            if event.get("type") == "chunk_done":
                if event.get("valid"):
                    data = event["data"]
                    if not first_name:
                        first_name = data.get("name", "")
                        first_description = data.get("description", "")
                    all_questions.extend(data.get("questions", []))
                else:
                    last_validation = event.get("validation", "未知错误")
                break
            yield event

    if not all_questions:
        yield {"type": "final", "valid": False, "validation": last_validation, "data": None}
        return

    merged = {
        "name": first_name or "整理题库",
        "description": first_description,
        "questions": all_questions,
    }
    validation = validate_bank_json(merged)
    yield {
        "type": "final",
        "valid": validation == "验证通过",
        "validation": validation,
        "data": merged,
    }


# 兼容性入口：保留原有函数签名，但内部不再使用 deepagents.create_deep_agent
def get_bank_import_agent(temperature: float = 0.2):
    """
    已废弃的兼容性入口。

    原实现使用 deepagents.create_deep_agent；由于其在长输入下不稳定，
    当前整理逻辑已迁移到 organize_bank / organize_bank_stream。
    此处返回一个占位对象，保持旧代码不报错。
    """
    return _BankImportAgentPlaceholder()


class _BankImportAgentPlaceholder:
    """兼容旧调用方式的占位对象。"""

    async def ainvoke(self, state: dict[str, Any]) -> dict[str, Any]:
        raw_text = ""
        for msg in state.get("messages", []):
            if msg.get("role") == "user":
                raw_text = msg.get("content", "")
                break
        return {"messages": [{"role": "assistant", "content": json.dumps((await organize_bank(raw_text))["data"])}]}

    async def astream(self, state: dict[str, Any]):
        raw_text = ""
        for msg in state.get("messages", []):
            if msg.get("role") == "user":
                raw_text = msg.get("content", "")
                break
        async for event in organize_bank_stream(raw_text):
            yield {"model": {"messages": [{"content": json.dumps(event)}]}}
