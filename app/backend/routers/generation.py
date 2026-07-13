import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ai_provider import AIConfigurationError, AIOutputError, ai_provider
from database import SessionLocal, get_db
from models import GenerationJob, Question, QuestionBank, SourceDocument, User
from schemas import DraftQuestionUpdate, GenerationCreate
from security import get_current_active_user

router = APIRouter(prefix="/api/generation-jobs", tags=["generation"])


def _owned_job(db: Session, job_id: int, user: User) -> GenerationJob:
    job = db.query(GenerationJob).filter(GenerationJob.id == job_id, GenerationJob.owner_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="生成任务不存在")
    return job


def _serialize(job: GenerationJob) -> dict:
    return {
        "id": job.id,
        "document_id": job.document_id,
        "bank_name": job.bank_name,
        "status": job.status,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "questions": job.draft_questions or [],
        "bank_id": job.bank_id,
    }


async def _run_generation(job_id: int):
    db = SessionLocal()
    try:
        job = db.get(GenerationJob, job_id)
        if not job:
            return
        job.status = "processing"
        job.error_code = None
        job.error_message = None
        db.commit()
        try:
            questions = await ai_provider.generate_questions(
                job.document.extracted_text,
                job.single_count,
                job.multiple_count,
                job.difficulty,
            )
            job.draft_questions = questions
            job.status = "ready"
            job.finished_at = datetime.now(timezone.utc)
        except AIConfigurationError as exc:
            job.status, job.error_code, job.error_message = "failed", "AI_NOT_CONFIGURED", str(exc)
        except TimeoutError as exc:
            job.status, job.error_code, job.error_message = "failed", "AI_TIMEOUT", str(exc)
        except AIOutputError as exc:
            job.status, job.error_code, job.error_message = "failed", "AI_INVALID_OUTPUT", str(exc)
        except Exception:
            job.status, job.error_code, job.error_message = "failed", "AI_SERVICE_ERROR", "AI 服务调用失败"
        db.commit()
    finally:
        db.close()


def _run_generation_sync(job_id: int):
    asyncio.run(_run_generation(job_id))


@router.post("")
def create_job(
    payload: GenerationCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    document = db.query(SourceDocument).filter(SourceDocument.id == payload.document_id, SourceDocument.owner_id == user.id).first()
    if not document:
        raise HTTPException(status_code=404, detail="源文档不存在")
    job = GenerationJob(owner_id=user.id, **payload.model_dump(), status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)
    background.add_task(_run_generation_sync, job.id)
    return _serialize(job)


@router.get("/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    return _serialize(_owned_job(db, job_id, user))


@router.patch("/{job_id}/questions/{index}")
def update_draft(job_id: int, index: int, payload: DraftQuestionUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    job = _owned_job(db, job_id, user)
    questions = list(job.draft_questions or [])
    if job.status != "ready" or not 0 <= index < len(questions):
        raise HTTPException(status_code=409, detail="当前任务不可编辑或题目不存在")
    questions[index] = payload.model_dump()
    job.draft_questions = questions
    db.commit()
    return _serialize(job)


@router.delete("/{job_id}/questions/{index}")
def delete_draft(job_id: int, index: int, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    job = _owned_job(db, job_id, user)
    questions = list(job.draft_questions or [])
    if job.status != "ready" or not 0 <= index < len(questions):
        raise HTTPException(status_code=409, detail="当前任务不可编辑或题目不存在")
    questions.pop(index)
    job.draft_questions = questions
    db.commit()
    return _serialize(job)


@router.post("/{job_id}/confirm")
def confirm_job(job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    job = _owned_job(db, job_id, user)
    if job.status != "ready" or not job.draft_questions:
        raise HTTPException(status_code=409, detail="当前任务不可确认")
    bank = QuestionBank(name=job.bank_name, description=f"由 {job.document.original_name} 生成", source_type="document", status="ready", owner_id=user.id)
    db.add(bank)
    db.flush()
    for payload in job.draft_questions:
        db.add(Question(**payload, bank_id=bank.id, source_type="ai"))
    job.status = "confirmed"
    job.bank_id = bank.id
    db.commit()
    return {"bank_id": bank.id, "question_count": len(job.draft_questions)}


@router.post("/{job_id}/retry")
def retry_job(job_id: int, background: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    job = _owned_job(db, job_id, user)
    if job.status != "failed":
        raise HTTPException(status_code=409, detail="只有失败任务可以重试")
    job.status = "pending"
    db.commit()
    background.add_task(_run_generation_sync, job.id)
    return _serialize(job)
