# TILIAN 题炼

面向学习者的基础题库刷题产品。平台题库没有所需内容时，学习者可以上传 PDF、DOCX、TXT 或 Markdown 学习文档，由 AI 生成个人题库并在确认后刷题。

## 功能

- 平台题库与个人题库
- 单选、多选、判断题的顺序/随机练习
- 每题判题、解析、个人历史正确率和全网正确率
- 学习文档生成 1～20 道个人题目
- 生成题预览、编辑、删除和确认
- 管理员 JSON / CSV / Excel / Word 平台题库导入
- 邀请码注册

## 本地运行

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python init_demo_data.py
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

```bash
cd frontend
npm install
npm run dev
```

前端默认访问 `http://localhost:5173`，后端 API 为 `http://localhost:8001`。演示学习者账号：`demo / demo123`。

## 环境变量

```dotenv
DATABASE_URL=sqlite:///./aiquiz.db
SECRET_KEY=replace-in-production
CORS_ORIGINS=["http://localhost:5173"]
UPLOAD_DIR=./uploads

# OpenAI 兼容模型接口；未配置时文档上传可用，但生成任务明确失败
LLM_API_URL=
LLM_API_KEY=
LLM_MODEL=

# 前端可选
VITE_API_BASE_URL=http://localhost:8001/api
```

所有自助注册账号均为学习者。需要管理员时，在受信任的服务器终端执行：

```bash
cd backend
python promote_admin.py 已注册用户名
```


## 管理员导入模板

支持 `.json`、`.csv`、`.xlsx`、`.xls`、`.docx` 五种格式。参考：

- [JSON 模板](./examples/bank-import-template.json)
- [CSV 模板](./examples/bank-import-template.csv)
- [Word 模板](./examples/bank-import-template.docx)

题型支持单选（single）、多选（multiple）、判断（judgment）。判断题固定为 A. 正确 / B. 错误。选项数量不少于 2 个即可，解析为可选项。

## 验证

```bash
cd backend && pytest
cd frontend && npm run build
```

生产数据库使用 Alembic 迁移；现有 SQLite 开发库启动时执行非破坏性兼容字段迁移。
