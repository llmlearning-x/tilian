"""
演示数据初始化脚本
创建演示用户、题库和题目
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from database import SessionLocal, init_db
from models import User, QuestionBank, Question
from security import get_password_hash
import json


def init_demo_data():
    """初始化演示数据"""
    # 创建所有表
    init_db()

    db: Session = SessionLocal()

    try:
        # 检查是否已有数据
        existing_user = db.query(User).filter(User.username == "demo").first()
        if existing_user:
            print("演示数据已存在，跳过初始化")
            return

        print("开始创建演示数据...")

        # 创建演示用户
        demo_user = User(
            username="demo",
            email="demo@example.com",
            hashed_password=get_password_hash("demo123"),
            is_active=True
        )
        db.add(demo_user)
        db.flush()
        print(f"✓ 创建用户: {demo_user.username}")

        # 创建题库
        bank1 = QuestionBank(
            name="前端开发基础",
            description="HTML、CSS、JavaScript 基础知识",
            is_public=True, source_type="platform", status="ready", owner_id=None
        )
        db.add(bank1)
        db.flush()

        bank2 = QuestionBank(
            name="计算机网络",
            description="HTTP、TCP/IP、网络协议等知识",
            is_public=True, source_type="platform", status="ready", owner_id=None
        )
        db.add(bank2)
        db.flush()
        print(f"✓ 创建题库: {bank1.name}, {bank2.name}")

        # 创建题目 - 前端开发基础
        questions_js = [
            Question(
                type="single",
                stem="以下哪个不是 JavaScript 的基本数据类型？",
                options=[
                    {"label": "A", "content": "String"},
                    {"label": "B", "content": "Boolean"},
                    {"label": "C", "content": "Array"},
                    {"label": "D", "content": "Undefined"}
                ],
                answer=["C"],
                explanation="Array 是对象类型，不是基本数据类型。JavaScript 的基本数据类型有：String、Number、Boolean、Undefined、Null、Symbol、BigInt。",
                difficulty=2,
                source_type="import",
                bank_id=bank1.id
            ),
            Question(
                type="single",
                stem="JavaScript 中，以下哪个方法可以将 JSON 字符串转换为对象？",
                options=[
                    {"label": "A", "content": "JSON.stringify()"},
                    {"label": "B", "content": "JSON.parse()"},
                    {"label": "C", "content": "JSON.object()"},
                    {"label": "D", "content": "JSON.toObj()"}
                ],
                answer=["B"],
                explanation="JSON.parse() 用于将 JSON 字符串转换为 JavaScript 对象，JSON.stringify() 用于将对象转换为 JSON 字符串。",
                difficulty=1,
                source_type="import",
                bank_id=bank1.id
            ),
            Question(
                type="multiple",
                stem="以下哪些是 JavaScript 的声明变量的关键字？",
                options=[
                    {"label": "A", "content": "var"},
                    {"label": "B", "content": "let"},
                    {"label": "C", "content": "const"},
                    {"label": "D", "content": "def"}
                ],
                answer=["A", "B", "C"],
                explanation="JavaScript 中声明变量的关键字有 var、let 和 const。def 是 Python 中定义函数的关键字。",
                difficulty=2,
                source_type="import",
                bank_id=bank1.id
            ),
        ]

        # 创建题目 - 计算机网络
        questions_http = [
            Question(
                type="single",
                stem="HTTP 协议默认使用的端口号是？",
                options=[
                    {"label": "A", "content": "21"},
                    {"label": "B", "content": "80"},
                    {"label": "C", "content": "443"},
                    {"label": "D", "content": "8080"}
                ],
                answer=["B"],
                explanation="HTTP 默认使用端口 80，HTTPS 默认使用端口 443。",
                difficulty=1,
                source_type="import",
                bank_id=bank2.id
            ),
            Question(
                type="single",
                stem="HTTP 状态码 404 表示什么？",
                options=[
                    {"label": "A", "content": "请求成功"},
                    {"label": "B", "content": "服务器内部错误"},
                    {"label": "C", "content": "未找到资源"},
                    {"label": "D", "content": "请求被禁止"}
                ],
                answer=["C"],
                explanation="HTTP 状态码：200 表示成功，404 表示未找到，500 表示服务器错误，403 表示禁止访问。",
                difficulty=1,
                source_type="import",
                bank_id=bank2.id
            ),
            Question(
                type="multiple",
                stem="以下哪些是 HTTP 的请求方法？",
                options=[
                    {"label": "A", "content": "GET"},
                    {"label": "B", "content": "POST"},
                    {"label": "C", "content": "DELETE"},
                    {"label": "D", "content": "CONNECT"}
                ],
                answer=["A", "B", "C", "D"],
                explanation="HTTP 常用请求方法包括：GET、POST、PUT、DELETE、PATCH、HEAD、OPTIONS、CONNECT 等。",
                difficulty=2,
                source_type="import",
                bank_id=bank2.id
            ),
        ]

        for q in questions_js + questions_http:
            db.add(q)

        db.commit()
        print(f"✓ 创建题目: {len(questions_js + questions_http)} 道")
        print("\n演示数据初始化完成！")
        print("\n登录信息：")
        print("  用户名: demo")
        print("  密码: demo123")

    except Exception as e:
        db.rollback()
        print(f"初始化失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_demo_data()
