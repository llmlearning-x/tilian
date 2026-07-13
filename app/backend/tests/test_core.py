import json
from io import BytesIO

from fastapi.testclient import TestClient
from docx import Document
from pypdf import PdfWriter

from main import app
from database import SessionLocal
from models import User

client = TestClient(app)


def register(username: str, email: str):
    response = client.post("/api/auth/register", json={"username": username, "email": email, "password": "secret123"})
    assert response.status_code == 200, response.text
    return response.json()


def headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def bank_payload():
    return {
        "name": "数学基础",
        "description": "测试题库",
        "questions": [
            {
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
        ],
    }


def test_platform_import_quiz_and_accuracy():
    admin = register("admin", "admin@example.com")
    with SessionLocal() as db:
        db.query(User).filter(User.username == "admin").update({"role": "admin"})
        db.commit()
    student = register("student", "student@example.com")
    admin_headers = headers(admin["access_token"])
    student_headers = headers(student["access_token"])

    upload = {"file": ("bank.json", json.dumps(bank_payload(), ensure_ascii=False).encode(), "application/json")}
    validated = client.post("/api/admin/bank-imports/validate", files=upload, headers=admin_headers)
    assert validated.status_code == 200
    assert validated.json()["question_count"] == 1

    forbidden = client.post("/api/admin/bank-imports/validate", files=upload, headers=student_headers)
    assert forbidden.status_code == 403

    imported = client.post("/api/admin/bank-imports", files=upload, headers=admin_headers)
    assert imported.status_code == 200, imported.text
    bank_id = imported.json()["bank_id"]

    listed = client.get("/api/banks/", params={"scope": "platform"}, headers=student_headers)
    assert listed.status_code == 200
    assert listed.json()[0]["question_count"] == 1

    started = client.post("/api/quiz/start", json={"bank_id": bank_id, "mode": "sequential"}, headers=student_headers)
    assert started.status_code == 200, started.text
    session = started.json()
    question_id = session["first_question"]["id"]
    submitted = client.post(
        "/api/quiz/submit",
        json={"session_id": session["session_id"], "question_id": question_id, "answer": ["B"]},
        headers=student_headers,
    )
    assert submitted.status_code == 200, submitted.text
    body = submitted.json()
    assert body["is_correct"] is True
    assert body["personal_accuracy"] == {"correct": 1, "attempts": 1, "rate": 100.0}
    assert body["global_accuracy"] == {"correct": 1, "attempts": 1, "rate": 100.0}

    duplicate = client.post(
        "/api/quiz/submit",
        json={"session_id": session["session_id"], "question_id": question_id, "answer": ["B"]},
        headers=student_headers,
    )
    assert duplicate.status_code == 409

    second = client.post("/api/quiz/start", json={"bank_id": bank_id, "mode": "sequential"}, headers=student_headers).json()
    second_submit = client.post(
        "/api/quiz/submit",
        json={"session_id": second["session_id"], "question_id": question_id, "answer": ["A"]},
        headers=student_headers,
    )
    assert second_submit.status_code == 200
    assert second_submit.json()["personal_accuracy"] == {"correct": 1, "attempts": 2, "rate": 50.0}
    assert second_submit.json()["global_accuracy"] == {"correct": 1, "attempts": 2, "rate": 50.0}


def test_document_upload_and_unconfigured_ai_failure(monkeypatch):
    import os
    from config import get_settings

    # 模拟 AI 未配置：清空相关环境变量并重置配置缓存
    monkeypatch.setenv("LLM_API_URL", "")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    get_settings.cache_clear()

    login = client.post("/api/auth/login", json={"username": "student", "password": "secret123"})
    token_headers = headers(login.json()["access_token"])
    uploaded = client.post(
        "/api/documents",
        files={"file": ("lesson.md", "# 第一章\n这是课程材料。".encode(), "text/markdown")},
        headers=token_headers,
    )
    assert uploaded.status_code == 200, uploaded.text
    created = client.post(
        "/api/generation-jobs",
        json={"document_id": uploaded.json()["id"], "bank_name": "第一章练习", "single_count": 1, "multiple_count": 0, "difficulty": "easy"},
        headers=token_headers,
    )
    assert created.status_code == 200, created.text
    job = client.get(f"/api/generation-jobs/{created.json()['id']}", headers=token_headers)
    assert job.json()["status"] == "failed"
    assert job.json()["error_code"] == "AI_NOT_CONFIGURED"

    # 恢复默认配置，避免影响后续测试
    monkeypatch.undo()
    get_settings.cache_clear()

    txt = client.post("/api/documents", files={"file": ("lesson.txt", b"plain lesson", "text/plain")}, headers=token_headers)
    assert txt.status_code == 200
    docx_buffer = BytesIO()
    docx = Document()
    docx.add_paragraph("DOCX 课程材料")
    docx.save(docx_buffer)
    docx_upload = client.post(
        "/api/documents",
        files={"file": ("lesson.docx", docx_buffer.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers=token_headers,
    )
    assert docx_upload.status_code == 200
    pdf_buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(pdf_buffer)
    blank_pdf = client.post("/api/documents", files={"file": ("scan.pdf", pdf_buffer.getvalue(), "application/pdf")}, headers=token_headers)
    assert blank_pdf.status_code == 422
    assert blank_pdf.json()["detail"] == "文档没有可提取文本"


def test_invalid_question_import_is_atomic():
    login = client.post("/api/auth/login", json={"username": "admin", "password": "secret123"})
    admin_headers = headers(login.json()["access_token"])
    invalid = bank_payload()
    invalid["questions"][0]["answer"] = ["Z"]
    response = client.post(
        "/api/admin/bank-imports",
        files={"file": ("invalid.json", json.dumps(invalid).encode(), "application/json")},
        headers=admin_headers,
    )
    assert response.status_code == 422
    banks = client.get("/api/banks/", params={"scope": "platform"}, headers=admin_headers).json()
    assert len(banks) == 1
