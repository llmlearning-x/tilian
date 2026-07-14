import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from database import get_db
from models import (
    GenerationJob,
    InvitationCode,
    Question,
    QuestionBank,
    QuizItem,
    QuizSession,
    User,
    UserQuestionStat,
)
from schemas import BankImportPayload, QuestionBankResponse
from security import get_current_admin

router = APIRouter(prefix="/api/admin/bank-imports", tags=["admin"])


class BankStatusUpdate(BaseModel):
    status: Literal["ready", "draft"]


def _split_answer(answer_str: str) -> list[str]:
    """拆分答案字符串，支持逗号、分号、空格、中文逗号等分隔符。"""
    if not answer_str:
        return []
    parts = re.split(r"[,\s;，]+", answer_str)
    return [p.strip().upper() for p in parts if p.strip()]


def _extract_option_label(column_name: str) -> str | None:
    """从列名中提取选项标签，如 option_A -> A，optionB -> B。"""
    col = str(column_name).strip()
    # 统一处理 option_A / optionA / Option A 等写法
    normalized = re.sub(r"[^a-zA-Z0-9_]", "", col)
    suffix = normalized.split("option")[-1].strip("_")
    if len(suffix) == 1 and suffix.isalpha():
        return suffix.upper()
    return None


def _parse_spreadsheet(raw: bytes, filename: str) -> list[dict]:
    """解析 CSV/Excel 文件为题库问题列表。"""
    ext = Path(filename).suffix.lower()
    try:
        if ext == ".csv":
            df = pd.read_csv(BytesIO(raw), dtype=str, keep_default_na=False)
        else:
            df = pd.read_excel(BytesIO(raw), dtype=str, keep_default_na=False)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"无法解析表格文件：{exc}") from exc

    if df.empty:
        raise HTTPException(status_code=422, detail="表格文件为空")

    # 定位选项列：option_A / optionA / Option A 等
    option_cols = []
    for col in df.columns:
        label = _extract_option_label(col)
        if label:
            option_cols.append((label, col))
    option_cols.sort(key=lambda x: x[0])

    if not option_cols:
        raise HTTPException(
            status_code=422,
            detail="未找到选项列，请使用 option_A、option_B 等表头",
        )

    questions = []
    for row_index, row in df.iterrows():
        qnum = row_index + 2  # Excel 行号从 2 开始（含表头）
        qtype = str(row.get("type", "")).strip().lower()
        stem = str(row.get("stem", "")).strip()

        options = []
        for label, col in option_cols:
            content = str(row.get(col, "")).strip()
            if content:
                options.append({"label": label, "content": content})

        answer = _split_answer(str(row.get("answer", "")).strip())
        explanation = str(row.get("explanation", "")).strip()

        difficulty = 2
        difficulty_raw = str(row.get("difficulty", "")).strip()
        if difficulty_raw:
            try:
                difficulty = int(float(difficulty_raw))
            except ValueError:
                pass

        questions.append(
            {
                "type": qtype,
                "stem": stem,
                "options": options,
                "answer": answer,
                "explanation": explanation,
                "difficulty": difficulty,
            }
        )

    return questions


def _parse_word(raw: bytes) -> tuple[str, str | None, list[dict]]:
    """解析 Word 模板文件，返回 (name, description, questions)。"""
    from docx import Document

    try:
        doc = Document(BytesIO(raw))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"无法解析 Word 文件：{exc}") from exc

    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    type_map = {"单选题": "single", "多选题": "multiple", "判断题": "judgment"}
    name = ""
    description = None
    questions: list[dict] = []

    current_type: str | None = None
    current_question: dict | None = None

    for para in paragraphs:
        # 题库元信息
        if para.startswith("题库名称："):
            name = para.replace("题库名称：", "").strip()
            continue
        if para.startswith("题库描述："):
            description = para.replace("题库描述：", "").strip()
            continue

        # 题型标记：【单选题】或 单选题
        if para.startswith("【") and para.endswith("】"):
            inner = para[1:-1]
            if inner in type_map:
                current_type = type_map[inner]
                continue
        if para in type_map:
            current_type = type_map[para]
            continue

        if current_type is None:
            continue

        # 选项行：A. xxx 或 A、xxx
        option_match = re.match(r"^([A-Z])[\.．、\)\]\s]+(.+)$", para)
        if option_match and current_question is not None:
            label, content = option_match.groups()
            current_question["options"].append({"label": label, "content": content.strip()})
            continue

        # 答案行
        answer_match = re.match(r"^答案[\：:]\s*(.+)$", para)
        if answer_match and current_question is not None:
            current_question["answer"] = _split_answer(answer_match.group(1).strip())
            continue

        # 解析行
        explanation_match = re.match(r"^解析[\：:]\s*(.+)$", para)
        if explanation_match and current_question is not None:
            current_question["explanation"] = explanation_match.group(1).strip()
            continue

        # 难度行
        difficulty_match = re.match(r"^难度[\：:]\s*(\d+)$", para)
        if difficulty_match and current_question is not None:
            current_question["difficulty"] = int(difficulty_match.group(1))
            continue

        # 题干行：1. xxx 或 1、xxx
        stem_match = re.match(r"^(\d+)[\.．、\)\]\s]+(.+)$", para)
        if stem_match:
            if current_question is not None:
                questions.append(current_question)
            current_question = {
                "type": current_type,
                "stem": stem_match.group(2).strip(),
                "options": [],
                "answer": [],
                "explanation": "",
                "difficulty": 2,
            }
            continue

    if current_question is not None:
        questions.append(current_question)

    if not name:
        raise HTTPException(
            status_code=422,
            detail="Word 模板未找到题库名称，请在文档开头填写“题库名称：xxx”",
        )

    return name, description, questions


def _check_question(raw: dict, index: int) -> tuple[list[str], list[str]]:
    """对单道题目做用户友好的前置校验，返回 (errors, warnings)。"""
    errors: list[str] = []
    warnings: list[str] = []
    qnum = index + 1

    if not isinstance(raw, dict):
        return [f"第 {qnum} 题：题目必须是对象"], []

    qtype = raw.get("type")
    if qtype not in ("single", "multiple", "judgment"):
        errors.append(f"第 {qnum} 题：type 必须是 single、multiple 或 judgment")

    stem = raw.get("stem", "")
    if not isinstance(stem, str) or not stem.strip():
        errors.append(f"第 {qnum} 题：题干 stem 不能为空")

    options = raw.get("options")
    labels: list[str] = []
    if not isinstance(options, list):
        errors.append(f"第 {qnum} 题：options 必须是数组")
    else:
        if qtype in ("single", "multiple") and len(options) < 2:
            errors.append(f"第 {qnum} 题：{qtype == 'single' and '单选题' or '多选题'}至少需要 2 个选项")
        if len(options) > 6:
            warnings.append(f"第 {qnum} 题：选项数量为 {len(options)}，超过 6 个，请检查是否有合并或冗余选项")
        seen = set()
        for i, opt in enumerate(options):
            if not isinstance(opt, dict):
                errors.append(f"第 {qnum} 题：第 {i + 1} 个选项必须是对象")
                continue
            label = opt.get("label")
            content = opt.get("content", "")
            if not isinstance(label, str) or not label.strip():
                errors.append(f"第 {qnum} 题：第 {i + 1} 个选项标签 label 不能为空")
            else:
                if label in seen:
                    errors.append(f"第 {qnum} 题：选项标签 '{label}' 重复")
                seen.add(label)
                if not isinstance(content, str) or not content.strip():
                    errors.append(f"第 {qnum} 题：选项 '{label}' 的 content 不能为空")
            if isinstance(label, str) and label.strip():
                labels.append(label)

        answer = raw.get("answer", [])
        if not isinstance(answer, list) or len(answer) == 0:
            errors.append(f"第 {qnum} 题：answer 必须是包含至少一个答案的非空数组")
        else:
            for ans in answer:
                if ans not in labels:
                    errors.append(
                        f"第 {qnum} 题：答案 '{ans}' 不在选项标签 {labels} 中"
                    )
            if qtype == "single" and len(answer) != 1:
                errors.append(
                    f"第 {qnum} 题：单选题必须有且只有一个答案，当前 {len(answer)} 个"
                )
            if qtype == "multiple" and len(answer) < 2:
                errors.append(
                    f"第 {qnum} 题：多选题必须至少有两个答案，当前 {len(answer)} 个"
                )
            if qtype == "judgment":
                if len(options) != 2:
                    errors.append(f"第 {qnum} 题：判断题必须包含两个选项")
                if len(answer) != 1:
                    errors.append(
                        f"第 {qnum} 题：判断题必须有且只有一个答案，当前 {len(answer)} 个"
                    )

    # explanation 为可选字段，空值不再产生警告
    explanation = raw.get("explanation", "")
    if not isinstance(explanation, str):
        errors.append(f"第 {qnum} 题：解析 explanation 必须是字符串")

    difficulty = raw.get("difficulty", 2)
    if not isinstance(difficulty, int) or not (1 <= difficulty <= 3):
        errors.append(f"第 {qnum} 题：难度 difficulty 必须是 1、2 或 3")

    return errors, warnings


def _validate_raw(data) -> tuple[list[str], list[str]]:
    """对原始 JSON 对象做用户友好的前置校验，返回 (errors, warnings)。"""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return ["题库根节点必须是对象"], []

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("题库名称 name 不能为空")

    description = data.get("description")
    if description is not None and not isinstance(description, str):
        errors.append("题库描述 description 必须是字符串")

    questions = data.get("questions")
    if not isinstance(questions, list):
        errors.append("questions 必须是数组")
        return errors, warnings
    if len(questions) == 0:
        errors.append("题库至少包含一道题")

    for idx, q in enumerate(questions):
        q_errors, q_warnings = _check_question(q, idx)
        errors.extend(q_errors)
        warnings.extend(q_warnings)

    return errors, warnings


async def _parse(
    file: UploadFile,
    name: str | None = None,
    description: str | None = None,
) -> tuple[BankImportPayload, list[str]]:
    filename = (file.filename or "").lower()
    raw = await file.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="导入文件不能超过 2 MB")

    if filename.endswith(".json"):
        try:
            data = json.loads(raw.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=422, detail="文件必须使用 UTF-8 编码") from exc
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"JSON 格式错误：第 {exc.lineno} 行第 {exc.colno} 列",
            ) from exc
        # JSON 文件使用文件内嵌的名称和描述
        if not isinstance(data, dict):
            raise HTTPException(status_code=422, detail="JSON 根节点必须是对象")
    elif filename.endswith((".csv", ".xlsx", ".xls")):
        if not name or not name.strip():
            raise HTTPException(
                status_code=422,
                detail="CSV/Excel 导入需要填写题库名称",
            )
        questions = _parse_spreadsheet(raw, file.filename or "")
        data = {"name": name, "description": description, "questions": questions}
    elif filename.endswith(".docx"):
        word_name, word_description, questions = _parse_word(raw)
        data = {
            "name": word_name,
            "description": word_description or description,
            "questions": questions,
        }
    else:
        raise HTTPException(
            status_code=415,
            detail="仅支持 Word（.docx）、Excel（.xlsx/.xls）、CSV、JSON 文件",
        )

    friendly_errors, warnings = _validate_raw(data)
    if friendly_errors:
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"校验未通过，共发现 {len(friendly_errors)} 处错误",
                "errors": friendly_errors,
                "warnings": warnings,
            },
        )

    try:
        return BankImportPayload.model_validate(data), warnings
    except ValidationError as exc:
        errors = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"])
            errors.append({"location": location, "message": error["msg"]})
        raise HTTPException(
            status_code=422,
            detail={"message": "题库校验失败", "errors": errors, "warnings": warnings},
        ) from exc


@router.post("/validate")
async def validate_import(
    file: UploadFile = File(...),
    name: str = Form(""),
    description: str | None = Form(None),
    _: User = Depends(get_current_admin),
):
    payload, warnings = await _parse(file, name=name, description=description)
    return {
        "valid": True,
        "name": payload.name,
        "question_count": len(payload.questions),
        "warnings": warnings,
    }


@router.post("")
async def import_bank(
    file: UploadFile = File(...),
    name: str = Form(""),
    description: str | None = Form(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    payload, _warnings = await _parse(file, name=name, description=description)
    try:
        bank = QuestionBank(
            name=payload.name,
            description=payload.description,
            source_type="platform",
            status="ready",
            owner_id=None,
        )
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
    """删除平台题库及其下所有题目、练习记录与生成任务关联。"""
    bank = db.get(QuestionBank, bank_id)
    if not bank or bank.source_type != "platform":
        raise HTTPException(status_code=404, detail="题库不存在")

    question_ids = [
        q.id for q in db.query(Question.id).filter(Question.bank_id == bank.id).all()
    ]
    if question_ids:
        db.query(QuizItem).filter(QuizItem.question_id.in_(question_ids)).delete(
            synchronize_session=False
        )
        db.query(UserQuestionStat).filter(
            UserQuestionStat.question_id.in_(question_ids)
        ).delete(synchronize_session=False)

    db.query(QuizSession).filter(QuizSession.bank_id == bank.id).delete(
        synchronize_session=False
    )
    db.query(GenerationJob).filter(GenerationJob.bank_id == bank.id).update(
        {GenerationJob.bank_id: None}, synchronize_session=False
    )
    db.query(Question).filter(Question.bank_id == bank.id).delete(
        synchronize_session=False
    )
    db.delete(bank)
    db.commit()


# =====================================================================
# 邀请码管理
# =====================================================================
admin_invite_router = APIRouter(prefix="/api/admin/invite-codes", tags=["admin"])


class InviteCodeCreate(BaseModel):
    count: int = Field(1, ge=1, le=50)
    expires_days: Optional[int] = Field(None, ge=1, le=365)


class InviteCodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime]
    used_at: Optional[datetime]
    used_by: Optional[int]
    used_by_username: Optional[str] = None


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
