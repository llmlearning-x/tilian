from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime


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


class QuestionOption(BaseModel):
    label: str
    content: str = Field(min_length=1)


class QuestionPayload(BaseModel):
    type: Literal["single", "multiple", "judgment"]
    stem: str = Field(min_length=1)
    options: list[QuestionOption]
    answer: list[str]
    explanation: str = Field(default="")
    difficulty: int = Field(default=2, ge=1, le=3)

    @model_validator(mode="after")
    def validate_question(self):
        labels = [option.label for option in self.options]
        if len(set(labels)) != len(labels):
            raise ValueError("选项标签不能重复")
        if any(answer not in labels for answer in self.answer):
            raise ValueError("答案必须引用有效选项")
        if self.type == "single" and len(self.answer) != 1:
            raise ValueError("单选题必须有且只有一个答案")
        if self.type == "multiple" and len(self.answer) < 2:
            raise ValueError("多选题必须至少有两个答案")
        if self.type == "judgment":
            if len(labels) != 2:
                raise ValueError("判断题必须包含两个选项")
            if len(self.answer) != 1:
                raise ValueError("判断题必须有且只有一个答案")
        return self


class BankImportPayload(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    questions: list[QuestionPayload] = Field(min_length=1)


class QuestionCreate(QuestionPayload):
    bank_id: int
    source_type: str = "manual"


class QuestionResponse(QuestionPayload):
    model_config = ConfigDict(from_attributes=True)
    id: int
    bank_id: int
    source_type: str
    created_at: datetime

class QuestionBankCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None


class QuestionBankUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None


class QuestionBankResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    source_type: str
    status: str
    owner_id: Optional[int]
    question_count: int = 0
    question_types: list[str] = []
    can_edit: bool = False
    created_at: datetime


class GenerationCreate(BaseModel):
    document_id: int
    bank_name: str = Field(min_length=1, max_length=100)
    single_count: int = Field(ge=0, le=20)
    multiple_count: int = Field(ge=0, le=20)
    difficulty: Literal["easy", "medium", "hard"] = "medium"

    @model_validator(mode="after")
    def validate_total(self):
        total = self.single_count + self.multiple_count
        if not 1 <= total <= 20:
            raise ValueError("单次生成题量必须为 1 到 20 题")
        return self


class DraftQuestionUpdate(QuestionPayload):
    pass


class AccuracyStats(BaseModel):
    correct: int
    attempts: int
    rate: float
