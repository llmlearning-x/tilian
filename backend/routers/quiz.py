from datetime import datetime, timezone
from typing import Literal
import random

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from database import get_db
from models import Question, QuestionBank, QuizItem, QuizSession, User, UserQuestionStat
from schemas import AccuracyStats
from security import get_current_active_user

router = APIRouter(prefix="/api/quiz", tags=["quiz"])


class QuizStartRequest(BaseModel):
    bank_id: int
    mode: Literal["sequential", "random"] = "sequential"


class QuizSubmitRequest(BaseModel):
    session_id: int
    question_id: int
    answer: list[str]


class MasterRequest(BaseModel):
    question_id: int
    mastered: bool = True


def _readable(bank: QuestionBank, user: User) -> bool:
    return bank.source_type == "platform" or bank.owner_id == user.id or user.role == "admin"


def _format_question(question: Question, seq: int) -> dict:
    return {"id": question.id, "seq": seq, "type": question.type, "stem": question.stem, "options": question.options}


@router.post("/start")
def start_quiz(payload: QuizStartRequest, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    bank = db.get(QuestionBank, payload.bank_id)
    if not bank or bank.status != "ready" or not _readable(bank, user):
        raise HTTPException(status_code=404, detail="题库不存在")
    questions = db.query(Question).filter(Question.bank_id == bank.id, Question.type.in_(["single", "multiple"])).all()
    if not questions:
        raise HTTPException(status_code=400, detail="该题库暂无可练习题目")
    if payload.mode == "random":
        random.shuffle(questions)
    session = QuizSession(bank_id=bank.id, user_id=user.id, mode=payload.mode, total_count=len(questions))
    db.add(session)
    db.flush()
    for seq, question in enumerate(questions):
        db.add(QuizItem(session_id=session.id, question_id=question.id, seq=seq))
    db.commit()
    db.refresh(session)
    return {"session_id": session.id, "total_count": len(questions), "first_question": _format_question(questions[0], 0)}


@router.get("/next/{session_id}")
def next_question(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    session = db.query(QuizSession).filter(QuizSession.id == session_id, QuizSession.user_id == user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="练习不存在")
    if session.finished:
        return {"finished": True, "session_id": session.id, "current_index": session.current_index, "total_count": session.total_count, "correct_count": session.correct_count, "question": None}
    item = db.query(QuizItem).filter(QuizItem.session_id == session.id, QuizItem.seq == session.current_index).first()
    if not item:
        raise HTTPException(status_code=409, detail="练习进度异常")
    return {"finished": False, "session_id": session.id, "current_index": session.current_index, "total_count": session.total_count, "correct_count": session.correct_count, "question": _format_question(item.question, item.seq)}


@router.get("/sessions/unfinished")
def list_unfinished_sessions(bank_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    """获取当前用户未完成的练习会话，用于断点续练。"""
    query = db.query(QuizSession).filter(QuizSession.user_id == user.id, QuizSession.finished.is_(False))
    if bank_id is not None:
        query = query.filter(QuizSession.bank_id == bank_id)
    sessions = query.order_by(QuizSession.started_at.desc()).all()
    return [
        {
            "session_id": s.id,
            "bank_id": s.bank_id,
            "bank_name": s.bank.name if s.bank else "未知题库",
            "mode": s.mode,
            "current_index": s.current_index,
            "total_count": s.total_count,
            "correct_count": s.correct_count,
            "started_at": s.started_at.isoformat() if s.started_at else None,
        }
        for s in sessions
    ]


@router.get("/resume/{session_id}")
def resume_session(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    """恢复指定未完成的练习会话。"""
    session = db.query(QuizSession).filter(QuizSession.id == session_id, QuizSession.user_id == user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="练习不存在")
    if session.finished:
        raise HTTPException(status_code=409, detail="练习已结束")
    item = db.query(QuizItem).filter(QuizItem.session_id == session.id, QuizItem.seq == session.current_index).first()
    if not item:
        raise HTTPException(status_code=409, detail="练习进度异常")
    return {
        "session_id": session.id,
        "current_index": session.current_index,
        "total_count": session.total_count,
        "correct_count": session.correct_count,
        "question": _format_question(item.question, item.seq),
    }


def _update_user_stat(db: Session, user_id: int, question_id: int, bank_id: int, is_correct: bool):
    """更新用户的答题统计与错题记录。"""
    stat = db.query(UserQuestionStat).filter(
        UserQuestionStat.user_id == user_id,
        UserQuestionStat.question_id == question_id,
    ).first()
    now = datetime.now(timezone.utc)
    if not stat:
        stat = UserQuestionStat(
            user_id=user_id,
            question_id=question_id,
            bank_id=bank_id,
            correct_count=1 if is_correct else 0,
            wrong_count=0 if is_correct else 1,
            is_mastered=False,
            last_result="correct" if is_correct else "wrong",
            last_answer_at=now,
        )
        db.add(stat)
    else:
        if is_correct:
            stat.correct_count += 1
        else:
            stat.wrong_count += 1
        stat.last_result = "correct" if is_correct else "wrong"
        stat.last_answer_at = now
        # 如果已经斩题，再次答错时取消斩题状态
        if not is_correct and stat.is_mastered:
            stat.is_mastered = False
            stat.mastered_at = None


def _stats(db: Session, question_id: int, user_id: int | None = None) -> AccuracyStats:
    query = db.query(
        func.count(QuizItem.id),
        func.sum(case((QuizItem.is_correct.is_(True), 1), else_=0)),
    ).join(QuizSession, QuizSession.id == QuizItem.session_id).filter(
        QuizItem.question_id == question_id, QuizItem.submitted_at.is_not(None)
    )
    if user_id is not None:
        query = query.filter(QuizSession.user_id == user_id)
    attempts, correct = query.one()
    attempts, correct = int(attempts or 0), int(correct or 0)
    return AccuracyStats(correct=correct, attempts=attempts, rate=round(correct / attempts * 100, 2) if attempts else 0.0)


@router.post("/submit")
def submit_answer(payload: QuizSubmitRequest, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    session = db.query(QuizSession).filter(QuizSession.id == payload.session_id, QuizSession.user_id == user.id).first()
    if not session or session.finished:
        raise HTTPException(status_code=409, detail="练习不存在或已结束")
    item = db.query(QuizItem).filter(
        QuizItem.session_id == session.id,
        QuizItem.question_id == payload.question_id,
        QuizItem.seq == session.current_index,
    ).first()
    if not item:
        raise HTTPException(status_code=409, detail="该题不属于当前答题位置")
    if item.submitted_at is not None:
        raise HTTPException(status_code=409, detail="该题已经提交")
    question = item.question
    answer = sorted(set(payload.answer))
    if not answer:
        raise HTTPException(status_code=422, detail="请选择答案")
    valid_labels = {option["label"] for option in question.options}
    if any(label not in valid_labels for label in answer):
        raise HTTPException(status_code=422, detail="答案包含无效选项")
    is_correct = answer == sorted(question.answer)
    item.user_answer = answer
    item.is_correct = is_correct
    item.submitted_at = datetime.now(timezone.utc)
    session.current_index += 1
    if is_correct:
        session.correct_count += 1
    if session.current_index >= session.total_count:
        session.finished = True
        session.finished_at = datetime.now(timezone.utc)

    # 更新用户答题统计
    _update_user_stat(db, user.id, question.id, session.bank_id, is_correct)

    db.commit()
    return {
        "is_correct": is_correct,
        "correct_answer": question.answer,
        "explanation": question.explanation,
        "can_continue": not session.finished,
        "personal_accuracy": _stats(db, question.id, user.id).model_dump(),
        "global_accuracy": _stats(db, question.id).model_dump(),
    }


@router.get("/result/{session_id}")
def result(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    session = db.query(QuizSession).filter(QuizSession.id == session_id, QuizSession.user_id == user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="练习不存在")
    rate = round(session.correct_count / session.total_count * 100, 2) if session.total_count else 0
    return {"session_id": session.id, "total_count": session.total_count, "correct_count": session.correct_count, "accuracy": rate, "finished": session.finished}


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    sessions = (
        db.query(QuizSession)
        .filter(QuizSession.user_id == user.id, QuizSession.finished.is_(True))
        .order_by(QuizSession.finished_at.desc())
        .all()
    )
    return [
        {
            "session_id": s.id,
            "bank_id": s.bank_id,
            "bank_name": s.bank.name if s.bank else "未知题库",
            "mode": s.mode,
            "total_count": s.total_count,
            "correct_count": s.correct_count,
            "accuracy": round(s.correct_count / s.total_count * 100, 2) if s.total_count else 0,
            "finished_at": s.finished_at.isoformat() if s.finished_at else None,
        }
        for s in sessions
    ]


# =====================================================================
# 错题管理与斩题
# =====================================================================

@router.get("/wrong-questions")
def list_wrong_questions(
    bank_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """获取当前用户的错题本。"""
    query = db.query(UserQuestionStat).filter(
        UserQuestionStat.user_id == user.id,
        UserQuestionStat.wrong_count > 0,
        UserQuestionStat.is_mastered.is_(False),
    )
    if bank_id is not None:
        query = query.filter(UserQuestionStat.bank_id == bank_id)
    stats = query.order_by(UserQuestionStat.last_answer_at.desc()).all()
    return [
        {
            "stat_id": s.id,
            "question_id": s.question_id,
            "bank_id": s.bank_id,
            "bank_name": s.bank.name if s.bank else "未知题库",
            "stem": s.question.stem if s.question else "",
            "type": s.question.type if s.question else "",
            "options": s.question.options if s.question else [],
            "answer": s.question.answer if s.question else [],
            "explanation": s.question.explanation if s.question else "",
            "wrong_count": s.wrong_count,
            "correct_count": s.correct_count,
            "last_result": s.last_result,
            "last_answer_at": s.last_answer_at.isoformat() if s.last_answer_at else None,
        }
        for s in stats
    ]


@router.post("/master")
def master_question(payload: MasterRequest, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    """斩题/取消斩题：标记题目已掌握。"""
    question = db.get(Question, payload.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    stat = db.query(UserQuestionStat).filter(
        UserQuestionStat.user_id == user.id,
        UserQuestionStat.question_id == payload.question_id,
    ).first()
    now = datetime.now(timezone.utc)
    if not stat:
        # 从未做过也能斩题
        stat = UserQuestionStat(
            user_id=user.id,
            question_id=payload.question_id,
            bank_id=question.bank_id,
            is_mastered=payload.mastered,
            mastered_at=now if payload.mastered else None,
        )
        db.add(stat)
    else:
        stat.is_mastered = payload.mastered
        stat.mastered_at = now if payload.mastered else None
    db.commit()
    return {
        "question_id": payload.question_id,
        "is_mastered": payload.mastered,
    }


@router.get("/mastered-questions")
def list_mastered_questions(
    bank_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """获取当前用户已斩题（已掌握）的题目列表。"""
    query = db.query(UserQuestionStat).filter(
        UserQuestionStat.user_id == user.id,
        UserQuestionStat.is_mastered.is_(True),
    )
    if bank_id is not None:
        query = query.filter(UserQuestionStat.bank_id == bank_id)
    stats = query.order_by(UserQuestionStat.mastered_at.desc()).all()
    return [
        {
            "stat_id": s.id,
            "question_id": s.question_id,
            "bank_id": s.bank_id,
            "bank_name": s.bank.name if s.bank else "未知题库",
            "stem": s.question.stem if s.question else "",
            "type": s.question.type if s.question else "",
            "mastered_at": s.mastered_at.isoformat() if s.mastered_at else None,
        }
        for s in stats
    ]
