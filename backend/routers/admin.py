import json
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from database import get_db
from models import Question, QuestionBank, User
from schemas import BankImportPayload, QuestionBankResponse, QuestionPayload
from security import get_current_admin

router = APIRouter(prefix="/api/admin/bank-imports", tags=["admin"])


class BankStatusUpdate(BaseModel):
    status: Literal["ready", "draft"]


async def _parse(file: UploadFile) -> BankImportPayload:
    if not (file.filename or "").lower().endswith(".json"):
        raise HTTPException(status_code=415, detail="平台题库仅支持 UTF-8 JSON 文件")
    raw = await file.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="导入文件不能超过 2 MB")
    try:
        data = json.loads(raw.decode("utf-8"))
        return BankImportPayload.model_validate(data)
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="文件必须使用 UTF-8 编码") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"JSON 格式错误：第 {exc.lineno} 行第 {exc.colno} 列") from exc
    except ValidationError as exc:
        errors = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"])
            errors.append({"location": location, "message": error["msg"]})
        raise HTTPException(status_code=422, detail={"message": "题库校验失败", "errors": errors}) from exc


@router.post("/validate")
async def validate_import(file: UploadFile = File(...), _: User = Depends(get_current_admin)):
    payload = await _parse(file)
    return {"valid": True, "name": payload.name, "question_count": len(payload.questions)}


@router.post("")
async def import_bank(file: UploadFile = File(...), db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    payload = await _parse(file)
    try:
        bank = QuestionBank(name=payload.name, description=payload.description, source_type="platform", status="ready", owner_id=None)
        db.add(bank)
        db.flush()
        for item in payload.questions:
            db.add(Question(**item.model_dump(), bank_id=bank.id, source_type="import"))
        db.commit()
        return {"bank_id": bank.id, "question_count": len(payload.questions)}
    except Exception:
        db.rollback()
        raise


# =====================================================================
# 平台题库管理（上架/下架/删除/列表）
# =====================================================================
admin_bank_router = APIRouter(prefix="/api/admin/banks", tags=["admin"])


@admin_bank_router.get("", response_model=list[QuestionBankResponse])
def list_admin_banks(
    status: Literal["all", "ready", "draft"] = "all",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """管理员查看所有平台题库（包含草稿/下架状态）。"""
    query = db.query(QuestionBank).filter(QuestionBank.source_type == "platform")
    if status != "all":
        query = query.filter(QuestionBank.status == status)
    banks = query.order_by(QuestionBank.created_at.desc()).all()
    for bank in banks:
        bank.question_count = db.query(Question).filter(Question.bank_id == bank.id).count()
        bank.can_edit = True
    return banks


@admin_bank_router.patch("/{bank_id}/status")
def update_bank_status(
    bank_id: int,
    payload: BankStatusUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """上架/下架平台题库：ready=上架，draft=下架。"""
    bank = db.get(QuestionBank, bank_id)
    if not bank or bank.source_type != "platform":
        raise HTTPException(status_code=404, detail="题库不存在")
    bank.status = payload.status
    db.commit()
    return {"bank_id": bank.id, "status": bank.status}


@admin_bank_router.delete("/{bank_id}", status_code=204)
def delete_admin_bank(
    bank_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """删除平台题库及其下所有题目。"""
    bank = db.get(QuestionBank, bank_id)
    if not bank or bank.source_type != "platform":
        raise HTTPException(status_code=404, detail="题库不存在")
    db.query(Question).filter(Question.bank_id == bank.id).delete()
    db.delete(bank)
    db.commit()
