from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import Question, QuestionBank, User
from schemas import QuestionBankCreate, QuestionBankResponse, QuestionBankUpdate, QuestionResponse
from security import get_current_active_user

router = APIRouter(prefix="/api/banks", tags=["banks"])


def _can_read(bank: QuestionBank, user: User) -> bool:
    # 学生只能看到已上架题库；管理员/所有者不受 status 限制
    is_visible = bank.status == "ready" or user.role == "admin" or bank.owner_id == user.id
    return is_visible and (bank.source_type == "platform" or bank.owner_id == user.id or user.role == "admin")


def _can_edit(bank: QuestionBank, user: User) -> bool:
    return (bank.source_type == "platform" and user.role == "admin") or (
        bank.source_type != "platform" and bank.owner_id == user.id
    )


def _serialize(bank: QuestionBank, user: User, count: int, types: list[str]) -> QuestionBankResponse:
    return QuestionBankResponse(
        id=bank.id,
        name=bank.name,
        description=bank.description,
        source_type=bank.source_type,
        status=bank.status,
        owner_id=bank.owner_id,
        question_count=count,
        question_types=types,
        can_edit=_can_edit(bank, user),
        created_at=bank.created_at,
    )


@router.get("/", response_model=list[QuestionBankResponse])
def list_banks(
    scope: Literal["platform", "mine"] = "platform",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    query = db.query(QuestionBank).filter(QuestionBank.status == "ready")
    query = query.filter(QuestionBank.source_type == "platform") if scope == "platform" else query.filter(
        QuestionBank.owner_id == user.id, QuestionBank.source_type != "platform"
    )
    result = []
    for bank in query.order_by(QuestionBank.created_at.desc()).all():
        valid_questions = db.query(Question).filter(
            Question.bank_id == bank.id, Question.type.in_(["single", "multiple"])
        )
        result.append(_serialize(bank, user, valid_questions.count(), sorted({q.type for q in valid_questions.all()})))
    return result


@router.post("/", response_model=QuestionBankResponse)
def create_personal_bank(
    payload: QuestionBankCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    bank = QuestionBank(**payload.model_dump(), source_type="document", status="ready", owner_id=user.id)
    db.add(bank)
    db.commit()
    db.refresh(bank)
    return _serialize(bank, user, 0, [])


@router.get("/{bank_id}", response_model=QuestionBankResponse)
def get_bank(bank_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    bank = db.get(QuestionBank, bank_id)
    if not bank or not _can_read(bank, user):
        raise HTTPException(status_code=404, detail="题库不存在")
    questions = db.query(Question).filter(Question.bank_id == bank.id, Question.type.in_(["single", "multiple"])).all()
    return _serialize(bank, user, len(questions), sorted({q.type for q in questions}))


@router.get("/{bank_id}/questions", response_model=list[QuestionResponse])
def get_bank_questions(bank_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    bank = db.get(QuestionBank, bank_id)
    if not bank or not _can_read(bank, user):
        raise HTTPException(status_code=404, detail="题库不存在")
    return db.query(Question).filter(Question.bank_id == bank_id, Question.type.in_(["single", "multiple"])).all()


@router.patch("/{bank_id}", response_model=QuestionBankResponse)
def update_bank(bank_id: int, payload: QuestionBankUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    bank = db.get(QuestionBank, bank_id)
    if not bank or not _can_edit(bank, user):
        raise HTTPException(status_code=403, detail="无权修改该题库")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(bank, key, value)
    db.commit()
    db.refresh(bank)
    count = db.query(func.count(Question.id)).filter(Question.bank_id == bank.id).scalar() or 0
    return _serialize(bank, user, count, [])


@router.delete("/{bank_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bank(bank_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    bank = db.get(QuestionBank, bank_id)
    if not bank or not _can_edit(bank, user):
        raise HTTPException(status_code=403, detail="无权删除该题库")
    db.delete(bank)
    db.commit()
