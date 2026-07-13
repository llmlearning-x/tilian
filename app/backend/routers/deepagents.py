"""
DeepAgents 题库整理 Agent 的 FastAPI 路由。

管理员上传任意 PDF/DOCX/TXT/MD/JSON 文档，Agent 使用 Kimi 模型
整理成符合平台导入要求的标准题库 JSON。
"""
import json
import os
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db
from models import User
from security import get_current_admin

# 避免循环导入：Agent 相关工具在运行时引入
from deepagents_agent.agent import organize_bank, organize_bank_stream
from deepagents_agent.cli import read_document
from deepagents_agent.tools import validate_bank_json

router = APIRouter(prefix="/api/admin/bank-organizer", tags=["admin"])

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "md", "markdown", "json"}
MAX_FILE_BYTES = 10 * 1024 * 1024


def _save_upload_to_temp(file: UploadFile) -> tuple[str, str]:
    filename = file.filename or ""
    suffix = filename.lower().split(".")[-1] if "." in filename else ""
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"不支持的文件格式：{suffix}，仅支持 {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = file.file.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="文件大小不能超过 10 MB")

    fd, tmp_path = tempfile.mkstemp(suffix=f".{suffix}")
    with os.fdopen(fd, "wb") as tmp:
        tmp.write(content)
    return tmp_path, suffix


def _build_agent_prompt(raw_text: str) -> str:
    return (
        f"请把以下文档内容整理成标准题库 JSON。\n\n"
        f"文档内容：\n```\n{raw_text}\n```\n\n"
        f"要求：\n"
        f"1. 使用 try_parse_json 解析（如果是 JSON）。\n"
        f"2. 若格式复杂，使用 execute_python 编写脚本预处理。\n"
        f"3. 整理完成后使用 validate_bank_json 验证。\n"
        f"4. 在最终回复中只输出纯 JSON，不要 markdown 代码块。"
    )


@router.post("")
async def organize_bank_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """
    上传非标准文档，由 DeepAgents + Kimi 整理为标准题库 JSON（同步返回）。
    """
    tmp_path, _ = _save_upload_to_temp(file)
    try:
        raw_text = read_document(tmp_path)
        if raw_text.startswith("错误："):
            raise HTTPException(status_code=400, detail=raw_text)

        result = await organize_bank(raw_text)
        if not result["valid"]:
            raise HTTPException(status_code=422, detail=result["validation"])

        bank_data = result["data"]
        return {
            "valid": True,
            "name": bank_data.get("name"),
            "question_count": len(bank_data.get("questions", [])),
            "data": bank_data,
        }
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/stream")
async def organize_bank_document_stream(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """
    上传非标准文档，由 DeepAgents + Kimi 流式整理。

    返回 SSE 流，前端可实时查看 Agent 思考过程、工具调用与执行结果。
    流结束时，最后一条事件为 {type: "final", data: <标准题库JSON>}。
    """
    tmp_path, _ = _save_upload_to_temp(file)
    raw_text = read_document(tmp_path)
    if raw_text.startswith("错误："):
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=400, detail=raw_text)

    async def event_stream():
        try:
            async for event in organize_bank_stream(raw_text):
                yield f"data: {_safe_json(event)}\n\n"
            yield "data: [DONE]\n\n"
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


def _safe_json(obj) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        import json as _json

        return _json.dumps({"type": "raw", "content": str(obj)}, ensure_ascii=False)
