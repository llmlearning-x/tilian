import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from database import get_db
from models import InvitationCode, Question, QuestionBank, User
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
# 邀请码管理
# =====================================================================
admin_invite_router = APIRouter(prefix="/api/admin/invite-codes", tags=["admin"])


class InviteCodeCreate(BaseModel):
    count: int = Field(1, ge=1, le=50)
    expires_days: Optional[int] = Field(None, ge=1, le=365)


class InviteCodeResponse(BaseModel):
    id: int
    code: str
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime]
    used_at: Optional[datetime]
    used_by: Optional[int]
    used_by_username: Optional[str] = None

    class Config:
        from_attributes = True


@admin_invite_router.post("", response_model=list[InviteCodeResponse])
def create_invite_codes(
    payload: InviteCodeCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """管理员生成邀请码，支持批量与可选有效期。"""
    codes = []
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=payload.expires_days) if payload.expires_days else None

    for _ in range(payload.count):
        while True:
            raw = secrets.token_urlsafe(12)
            candidate = f"TL-{raw[:16].upper()}"
            exists = db.query(InvitationCode).filter(InvitationCode.code == candidate).first()
            if not exists:
                break
        invite = InvitationCode(
            code=candidate,
            created_by=current_admin.id,
            expires_at=expires_at,
        )
        db.add(invite)
        codes.append(invite)

    db.commit()
    for invite in codes:
        db.refresh(invite)
    return codes


@admin_invite_router.get("", response_model=list[InviteCodeResponse])
def list_invite_codes(
    status: Literal["all", "active", "used"] = "all",
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """管理员查看邀请码列表，支持按状态筛选。"""
    query = db.query(InvitationCode)
    if status == "active":
        query = query.filter(InvitationCode.is_active == True, InvitationCode.used_by.is_(None))
    elif status == "used":
        query = query.filter(InvitationCode.used_by.isnot(None))
    invites = query.order_by(InvitationCode.created_at.desc()).offset(skip).limit(limit).all()

    used_by_ids = {i.used_by for i in invites if i.used_by}
    users = {u.id: u.username for u in db.query(User).filter(User.id.in_(used_by_ids)).all()}

    result = []
    for invite in invites:
        data = InviteCodeResponse.model_validate(invite)
        data.used_by_username = users.get(invite.used_by)
        result.append(data)
    return result


@admin_invite_router.delete("/{invite_id}", status_code=204)
def delete_invite_code(
    invite_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """禁用/删除未使用的邀请码；已使用的邀请码不可删除。"""
    invite = db.get(InvitationCode, invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    if invite.used_by is not None:
        raise HTTPException(status_code=400, detail="已使用的邀请码不可删除")
    db.delete(invite)
    db.commit()
    return


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
