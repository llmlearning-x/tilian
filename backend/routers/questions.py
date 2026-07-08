from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import Question, QuestionBank, User
from schemas import DraftQuestionUpdate, QuestionCreate, QuestionResponse
from security import get_current_active_user

router = APIRouter(prefix="/api/questions", tags=["questions"])


def _editable_bank(db: Session, bank_id: int, user: User) -> QuestionBank:
    bank = db.get(QuestionBank, bank_id)
    allowed = bank and ((bank.source_type == "platform" and user.role == "admin") or bank.owner_id == user.id)
    if not allowed:
        raise HTTPException(status_code=403, detail="无权维护该题库")
    return bank


@router.post("/", response_model=QuestionResponse)
def create_question(payload: QuestionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    _editable_bank(db, payload.bank_id, user)
    question = Question(**payload.model_dump())
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


@router.patch("/{question_id}", response_model=QuestionResponse)
def update_question(question_id: int, payload: DraftQuestionUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    _editable_bank(db, question.bank_id, user)
    for key, value in payload.model_dump().items():
        setattr(question, key, value)
    db.commit()
    db.refresh(question)
    return question


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(question_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    _editable_bank(db, question.bank_id, user)
    db.delete(question)
    db.commit()
