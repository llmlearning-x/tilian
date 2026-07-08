from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from document_parser import extract_text
from models import SourceDocument, User
from security import get_current_active_user

router = APIRouter(prefix="/api/documents", tags=["documents"])
ALLOWED_TYPES = {"pdf", "docx", "txt", "md", "markdown"}


@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    original_name = Path(file.filename or "")
    file_type = original_name.suffix.lower().lstrip(".")
    if file_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="仅支持 PDF、DOCX、TXT 和 Markdown 文件")
    content = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(content) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件不能超过 10 MB")
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}.{file_type}"
    path = upload_dir / stored_name
    path.write_bytes(content)
    try:
        text = extract_text(path, file_type)
        if not text:
            raise ValueError("文档没有可提取文本")
    except Exception as exc:
        path.unlink(missing_ok=True)
        message = "文档没有可提取文本" if "可提取文本" in str(exc) else "文档解析失败"
        raise HTTPException(status_code=422, detail=message) from exc

    document = SourceDocument(
        owner_id=user.id,
        original_name=original_name.name,
        stored_name=stored_name,
        file_type=file_type,
        size_bytes=len(content),
        extracted_text=text,
        parse_status="ready",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return {"id": document.id, "name": document.original_name, "size_bytes": document.size_bytes, "status": "ready"}
