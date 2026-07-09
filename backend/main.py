from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from config import settings
from routers import admin, banks, deepagents, documents, generation, questions, quiz, users

# 创建数据库表
init_db()

app = FastAPI(title="TILIAN 题炼", description="面向学生的题库练习与文档生成题库系统")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含路由
app.include_router(users.router)
app.include_router(banks.router)
app.include_router(questions.router)
app.include_router(quiz.router)
app.include_router(documents.router)
app.include_router(generation.router)
app.include_router(admin.router)
app.include_router(admin.admin_bank_router)
app.include_router(deepagents.router)

@app.get("/")
async def root():
    return {"message": "欢迎使用 TILIAN 题炼"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
