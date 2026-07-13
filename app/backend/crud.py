from sqlalchemy.orm import Session
from models import User, QuestionBank, Question
from schemas import UserCreate, QuestionBankCreate, QuestionCreate
from security import get_password_hash

# 用户相关CRUD操作
def get_user(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(User).offset(skip).limit(limit).all()

def create_user(db: Session, user: UserCreate):
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=get_password_hash(user.password),
        role="student",
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# 题库相关CRUD操作
def get_question_banks(db: Session, skip: int = 0, limit: int = 100):
    return db.query(QuestionBank).offset(skip).limit(limit).all()

def get_question_bank(db: Session, question_bank_id: int):
    return db.query(QuestionBank).filter(QuestionBank.id == question_bank_id).first()

def create_question_bank(db: Session, question_bank: QuestionBankCreate, owner_id: int):
    db_question_bank = QuestionBank(**question_bank.dict(), owner_id=owner_id)
    db.add(db_question_bank)
    db.commit()
    db.refresh(db_question_bank)
    return db_question_bank

# 题目相关CRUD操作
def get_questions(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Question).offset(skip).limit(limit).all()

def get_question(db: Session, question_id: int):
    return db.query(Question).filter(Question.id == question_id).first()

def create_question(db: Session, question: QuestionCreate):
    db_question = Question(**question.dict())
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    return db_question
