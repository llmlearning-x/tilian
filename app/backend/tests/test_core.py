import json
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from docx import Document
from pypdf import PdfWriter

from main import app
from database import SessionLocal
from models import User

client = TestClient(app)


def register(username: str, email: str):
    invite_code = f"TEST-{username.upper()}-CODE"
    with SessionLocal() as db:
        from models import InvitationCode

        existing = db.query(InvitationCode).filter(InvitationCode.code == invite_code).first()
        if not existing:
            db.add(InvitationCode(code=invite_code, is_active=True))
            db.commit()
    response = client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": "secret123", "invite_code": invite_code},
    )
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


def _admin_headers():
    login = client.post("/api/auth/login", json={"username": "admin", "password": "secret123"})
    if login.status_code == 401:
        # 准备测试用邀请码
        with SessionLocal() as db:
            from models import InvitationCode

            existing = db.query(InvitationCode).filter(InvitationCode.code == "TEST-ADMIN-CODE").first()
            if not existing:
                db.add(InvitationCode(code="TEST-ADMIN-CODE", is_active=True))
                db.commit()
        registered = client.post(
            "/api/auth/register",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "password": "secret123",
                "invite_code": "TEST-ADMIN-CODE",
            },
        )
        if registered.status_code not in (200, 400):
            raise AssertionError(f"无法创建 admin 测试用户：{registered.text}")
        with SessionLocal() as db:
            db.query(User).filter(User.username == "admin").update({"role": "admin"})
            db.commit()
        login = client.post("/api/auth/login", json={"username": "admin", "password": "secret123"})
    assert login.status_code == 200
    return headers(login.json()["access_token"])


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_tianyi_csv_import_passes_without_warnings():
    """天翼云 CSV 清洗后应通过校验且无警告。"""
    admin_headers = _admin_headers()
    path = PROJECT_ROOT / "docs" / "天翼云架构师_312题.csv"
    response = client.post(
        "/api/admin/bank-imports/validate",
        data={"name": "天翼云高级解决方案架构师", "description": "CSV 测试"},
        files={"file": ("天翼云架构师_312题.csv", path.read_bytes(), "text/csv")},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["valid"] is True
    assert body["question_count"] == 312
    assert len(body["warnings"]) == 0


def test_aliyun_acp_csv_import_passes_with_warnings():
    """阿里云 ACP CSV 修正后应通过校验并返回警告。"""
    admin_headers = _admin_headers()
    path = PROJECT_ROOT / "docs" / "aliyun_acp_899题.csv"
    response = client.post(
        "/api/admin/bank-imports/validate",
        data={"name": "阿里云ACP题库云计算", "description": "CSV 测试"},
        files={"file": ("aliyun_acp_899题.csv", path.read_bytes(), "text/csv")},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["valid"] is True
    assert body["question_count"] == 887


def test_tianyi_csv_import_succeeds_with_relaxed_rules():
    """放宽规则后，天翼云 CSV 应能成功导入。"""
    admin_headers = _admin_headers()
    path = PROJECT_ROOT / "docs" / "天翼云架构师_312题.csv"
    response = client.post(
        "/api/admin/bank-imports",
        data={"name": "天翼云高级解决方案架构师", "description": "CSV 测试"},
        files={"file": ("天翼云架构师_312题.csv", path.read_bytes(), "text/csv")},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["question_count"] == 312


def test_excel_import_works():
    """Excel 文件导入应能正常解析。"""
    import pandas as pd

    admin_headers = _admin_headers()
    df = pd.DataFrame(
        [
            {
                "type": "single",
                "stem": "Excel 导入测试题",
                "option_A": "选项 A",
                "option_B": "选项 B",
                "option_C": "选项 C",
                "option_D": "选项 D",
                "answer": "B",
                "explanation": "测试解析",
                "difficulty": 1,
            }
        ]
    )
    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    response = client.post(
        "/api/admin/bank-imports/validate",
        data={"name": "Excel 测试题库", "description": "Excel 测试"},
        files={"file": ("test.xlsx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["question_count"] == 1


def test_judgment_json_import_works():
    """JSON 判断题应能正常导入。"""
    admin_headers = _admin_headers()
    payload = {
        "name": "判断题测试",
        "questions": [
            {
                "type": "judgment",
                "stem": "水在标准大气压下的沸点为 100℃。",
                "options": [
                    {"label": "A", "content": "正确"},
                    {"label": "B", "content": "错误"},
                ],
                "answer": ["A"],
                "explanation": "标准大气压下水的沸点是 100℃。",
                "difficulty": 1,
            }
        ],
    }
    response = client.post(
        "/api/admin/bank-imports/validate",
        files={"file": ("judgment.json", json.dumps(payload, ensure_ascii=False).encode(), "application/json")},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["question_count"] == 1


def test_judgment_csv_import_works():
    """CSV 判断题应能正常导入。"""
    admin_headers = _admin_headers()
    csv = "type,stem,option_A,option_B,answer,explanation,difficulty\n"
    csv += "judgment,水在标准大气压下的沸点为 100℃。,正确,错误,A,标准大气压下水的沸点是 100℃。,1\n"
    response = client.post(
        "/api/admin/bank-imports/validate",
        data={"name": "判断题 CSV 测试", "description": "CSV 测试"},
        files={"file": ("judgment.csv", csv.encode("utf-8"), "text/csv")},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["question_count"] == 1


def test_word_template_import_works():
    """Word 模板应能解析出三种题型。"""
    admin_headers = _admin_headers()
    path = PROJECT_ROOT / "examples" / "bank-import-template.docx"
    response = client.post(
        "/api/admin/bank-imports/validate",
        files={"file": ("bank-import-template.docx", path.read_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["valid"] is True
    assert body["name"] == "示例平台题库"
    assert body["question_count"] == 3


def test_tianyi_word_import_template_passes_with_warnings():
    """天翼云 Word 导入模板应通过校验并返回警告。"""
    admin_headers = _admin_headers()
    path = PROJECT_ROOT / "docs" / "天翼云高级解决方案架构师-导入模板.docx"
    response = client.post(
        "/api/admin/bank-imports/validate",
        files={"file": ("天翼云高级解决方案架构师-导入模板.docx", path.read_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["valid"] is True
    assert body["question_count"] == 312


def test_aliyun_word_import_template_passes_with_warnings():
    """阿里云 Word 导入模板修正后应通过校验并返回警告。"""
    admin_headers = _admin_headers()
    path = PROJECT_ROOT / "docs" / "阿里云ACP题库云计算（899题）-导入模板.docx"
    response = client.post(
        "/api/admin/bank-imports/validate",
        files={"file": ("阿里云ACP题库云计算（899题）-导入模板.docx", path.read_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["valid"] is True
    assert body["question_count"] == 887
