from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base



class InvitationCode(Base):
    __tablename__ = "invitation_codes"

    id = Column(Integer, primary_key=True)
    code = Column(String(64), unique=True, index=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    used_by = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)

    creator = relationship("User", foreign_keys=[created_by], back_populates="created_invitation_codes")
    used_by_user = relationship("User", foreign_keys=[used_by])

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False, default="student")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    question_banks = relationship("QuestionBank", back_populates="owner")
    quiz_sessions = relationship("QuizSession", back_populates="user")
    source_documents = relationship("SourceDocument", back_populates="owner")
    generation_jobs = relationship("GenerationJob", back_populates="owner")
    question_stats = relationship("UserQuestionStat", back_populates="user")
    created_invitation_codes = relationship("InvitationCode", foreign_keys=[InvitationCode.created_by], back_populates="creator")


class KnowledgePoint(Base):
    """Legacy data retained for migration compatibility; no longer used by the product."""
    __tablename__ = "knowledge_points"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    owner_id = Column(Integer, ForeignKey("users.id"))


class QuestionBank(Base):
    __tablename__ = "question_banks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    source_type = Column(String(20), nullable=False, default="document")
    status = Column(String(20), nullable=False, default="ready")
    is_public = Column(Boolean, default=False)  # legacy compatibility
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    owner = relationship("User", back_populates="question_banks")
    questions = relationship("Question", back_populates="bank", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_question_banks_scope", "source_type", "owner_id", "status"),)


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(20), nullable=False)
    stem = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)
    answer = Column(JSON, nullable=False)
    explanation = Column(Text, nullable=False, default="")
    difficulty = Column(Integer, default=2)
    source_type = Column(String(20), nullable=False, default="manual")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    knowledge_point_id = Column(Integer, ForeignKey("knowledge_points.id"), nullable=True)
    bank_id = Column(Integer, ForeignKey("question_banks.id"), nullable=False)

    bank = relationship("QuestionBank", back_populates="questions")


class QuizSession(Base):
    __tablename__ = "quiz_sessions"

    id = Column(Integer, primary_key=True, index=True)
    bank_id = Column(Integer, ForeignKey("question_banks.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mode = Column(String(20), default="sequential")
    current_index = Column(Integer, default=0)
    total_count = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    finished = Column(Boolean, default=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="quiz_sessions")
    bank = relationship("QuestionBank")
    items = relationship("QuizItem", back_populates="session", cascade="all, delete-orphan")


class QuizItem(Base):
    __tablename__ = "quiz_items"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("quiz_sessions.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    seq = Column(Integer, default=0)
    user_answer = Column(JSON)
    is_correct = Column(Boolean, nullable=True)
    time_spent = Column(Integer, default=0)
    submitted_at = Column(DateTime(timezone=True), nullable=True)

    session = relationship("QuizSession", back_populates="items")
    question = relationship("Question")

    __table_args__ = (
        Index("ix_quiz_items_question_submitted", "question_id", "submitted_at"),
        Index("ux_quiz_items_session_question", "session_id", "question_id", unique=True),
    )


class UserQuestionStat(Base):
    """记录用户对每道题的答题统计、错题状态与斩题（掌握）状态。"""

    __tablename__ = "user_question_stats"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    bank_id = Column(Integer, ForeignKey("question_banks.id"), nullable=False, index=True)
    correct_count = Column(Integer, default=0)
    wrong_count = Column(Integer, default=0)
    is_mastered = Column(Boolean, default=False)  # 斩题/已掌握
    last_result = Column(String(20), nullable=True)  # "correct" | "wrong"
    last_answer_at = Column(DateTime(timezone=True), nullable=True)
    mastered_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")
    question = relationship("Question")
    bank = relationship("QuestionBank")

    __table_args__ = (
        Index("ux_user_question_stats_user_question", "user_id", "question_id", unique=True),
        Index("ix_user_question_stats_user_wrong_mastered", "user_id", "wrong_count", "is_mastered"),
    )


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    original_name = Column(String(255), nullable=False)
    stored_name = Column(String(255), nullable=False, unique=True)
    file_type = Column(String(20), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    parse_status = Column(String(20), nullable=False, default="ready")
    extracted_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="source_documents")
    generation_jobs = relationship("GenerationJob", back_populates="document")


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("source_documents.id"), nullable=False)
    bank_name = Column(String(100), nullable=False)
    single_count = Column(Integer, nullable=False, default=0)
    multiple_count = Column(Integer, nullable=False, default=0)
    difficulty = Column(String(20), nullable=False, default="medium")
    status = Column(String(20), nullable=False, default="pending", index=True)
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    draft_questions = Column(JSON, nullable=True)
    bank_id = Column(Integer, ForeignKey("question_banks.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)

    owner = relationship("User", back_populates="generation_jobs")
    document = relationship("SourceDocument", back_populates="generation_jobs")
    bank = relationship("QuestionBank")
