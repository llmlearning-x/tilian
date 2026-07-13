"""
DeepAgents 题库整理 Agent 的单元测试。

本文件主要覆盖与 LLM 无关的纯逻辑路径；涉及 LLM 调用的路径通过 mock
`get_kimi_model` 来避免真实请求，保证测试稳定、快速。
"""
import asyncio
import json
from io import BytesIO
from unittest.mock import patch

import pytest
from docx import Document
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from database import SessionLocal
from main import app
from models import User
from security import get_password_hash

from deepagents_agent.agent import (
    _extract_code,
    _sanitize_code,
    _split_text,
    organize_bank_stream,
)
from deepagents_agent.tools import validate_bank_json

client = TestClient(app)


SAMPLE_QUESTION = {
    "type": "single",
    "stem": "1 + 1 等于多少？",
    "options": [
        {"label": "A", "content": "1"},
        {"label": "B", "content": "2"},
        {"label": "C", "content": "3"},
        {"label": "D", "content": "4"},
    ],
    "answer": ["B"],
    "explanation": "基础加法。",
    "difficulty": 1,
}


def _admin_headers():
    """获取一个测试管理员账号的 Token。"""
    username = "agent_admin"
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            user = User(
                username=username,
                email=f"{username}@example.com",
                hashed_password=get_password_hash("secret123"),
                role="admin",
            )
            db.add(user)
            db.commit()
    login = client.post(
        "/api/auth/login",
        json={"username": username, "password": "secret123"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_split_text_basic():
    text = "line\n" * 100
    chunks = _split_text(text, max_chars=50)
    assert all(len(c) <= 50 for c in chunks)
    assert "".join(chunks) == text


def test_split_text_short():
    text = "short text"
    assert _split_text(text, max_chars=100) == [text]


def test_extract_code_from_markdown():
    content = "```python\nprint('hello')\n```"
    assert _extract_code(content) == "print('hello')"


def test_extract_code_no_fences():
    content = "print('hello')"
    assert _extract_code(content) == "print('hello')"


def test_sanitize_code_removes_input_assignment():
    code = "_bank_agent_input_text_ = 'override'\nprint('ok')"
    cleaned = _sanitize_code(code)
    assert "override" not in cleaned
    assert "print('ok')" in cleaned


def test_sanitize_code_removes_input_text_alias():
    code = "input_text = 'alias'\nprint('ok')"
    cleaned = _sanitize_code(code)
    assert "alias" not in cleaned
    assert "print('ok')" in cleaned


def test_validate_bank_json_ok():
    payload = {
        "name": "测试题库",
        "description": "desc",
        "questions": [SAMPLE_QUESTION],
    }
    assert validate_bank_json(payload) == "验证通过"


def test_validate_bank_json_bad_answer():
    payload = {
        "name": "测试题库",
        "description": "desc",
        "questions": [{**SAMPLE_QUESTION, "answer": ["Z"]}],
    }
    result = validate_bank_json(payload)
    assert result != "验证通过"
    assert "answer" in result.lower() or "选项" in result


def _make_fake_model(code: str):
    """构造一个 Fake LLM，让 code-first 路径执行给定的代码。"""
    response = AIMessage(content=code, tool_calls=[])

    class FakeModel:
        async def ainvoke(self, messages):
            return response

        def bind_tools(self, tools):
            return self

    return FakeModel()


def test_organize_bank_stream_code_first_success():
    raw_text = "1\t1+1=?\tA:1\tB:2\tC:3\tD:4\tB"
    generated_code = """import json
result = {
    "name": "测试题库",
    "description": "来自单元测试",
    "questions": [
        {
            "type": "single",
            "stem": "1+1=?",
            "options": [
                {"label": "A", "content": "1"},
                {"label": "B", "content": "2"},
                {"label": "C", "content": "3"},
                {"label": "D", "content": "4"},
            ],
            "answer": ["B"],
            "explanation": "基础加法",
            "difficulty": 1,
        }
    ]
}
print(json.dumps(result, ensure_ascii=False))
"""

    async def run():
        with patch(
            "deepagents_agent.agent.get_kimi_model",
            return_value=_make_fake_model(generated_code),
        ):
            events = []
            async for event in organize_bank_stream(raw_text):
                events.append(event)
            return events

    events = asyncio.run(run())
    types = [e["type"] for e in events]

    assert "start" in types
    assert "final" in types
    final = events[-1]
    assert final["valid"] is True
    assert final["data"]["name"] == "测试题库"
    assert len(final["data"]["questions"]) == 1

    # tool_call 事件中的 tool_args 不应携带大段文本或完整 data
    tool_calls = [e for e in events if e["type"] == "tool_call"]
    for tc in tool_calls:
        args = tc.get("tool_args", {})
        if tc.get("tool_name") == "execute_python":
            assert "input_text" not in args
            assert "code" not in args
            assert isinstance(args.get("code_length"), int)
        if tc.get("tool_name") == "validate_bank_json":
            assert "data" not in args


def test_stream_endpoint_returns_sse_and_done(monkeypatch):
    """流式上传接口应返回 SSE，最后一条事件为 [DONE]。"""

    async def fake_stream(raw_text: str):
        yield {"type": "start", "content": "ok"}
        yield {
            "type": "final",
            "valid": True,
            "validation": "验证通过",
            "data": {"name": "mock", "description": "", "questions": []},
        }

    monkeypatch.setattr("routers.deepagents.organize_bank_stream", fake_stream)

    docx_buffer = BytesIO()
    docx = Document()
    docx.add_paragraph("test content")
    docx.save(docx_buffer)

    response = client.post(
        "/api/admin/bank-organizer/stream",
        files={
            "file": (
                "test.docx",
                docx_buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=_admin_headers(),
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")

    # 解析 SSE：每行 data: ...，最后为 data: [DONE]
    body = response.text.strip()
    lines = [line for line in body.split("\n") if line]
    assert lines[0].startswith("data:")
    assert lines[-1] == "data: [DONE]"

    final_line = lines[-2]
    final_event = json.loads(final_line[len("data: ") :])
    assert final_event["type"] == "final"
    assert final_event["valid"] is True
