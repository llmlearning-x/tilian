# TILIAN 与 Postcards 共用云服务器部署方案

> 目标：在 Postcards（旅行邮箱）项目已有的火山引擎 ECS 上，同时部署运行 TILIAN（题炼）项目。  
> 服务器公网 IP：`115.190.7.207`（无域名，仅 IP 访问）  
> 数据库：Postcards 与 TILIAN 均使用阿里云 RDS（数据库不在本服务器上）

---

## 一、设计原则

1. **互不侵入**：TILIAN 的部署不破坏 Postcards 现有目录、配置与 CI/CD。
2. **仅 IP 访问**：国内服务器无域名，采用路径前缀 `/tilian/` 区分两个项目。
3. **RDS 直连**：数据库使用阿里云 RDS MySQL 8.0，服务器上无需安装数据库。
4. **Nginx 统一入口**：Nginx 作为唯一 80 端口入口，按路径路由到对应服务。
5. **可回滚**：保留各自独立部署脚本，任何一方更新不影响另一方。

---

## 二、服务器资源评估

由于数据库在阿里云 RDS 上，服务器仅需运行应用服务和 Nginx，资源需求较低。

| 服务 | 预估内存 | CPU | 说明 |
|---|---|---|---|
| Postcards Node.js API | ~512 MB | 低 | PM2 限制 512M |
| TILIAN FastAPI API | ~300-400 MB | 中 | Python + AI 依赖 |
| Nginx | ~50 MB | 低 | 静态资源 + 反向代理 |
| 系统开销 | ~300-500 MB | 低 | OS + 其他进程 |
| **合计建议配置** | **≥ 2 核 4G** | | 数据库在 RDS，服务器压力较小 |

---

## 三、端口与服务规划

| 服务 | 监听地址 | 端口 | 说明 |
|---|---|---|---|
| Nginx | `0.0.0.0` | 80 | 统一入口 |
| Postcards API | `127.0.0.1` | 3000 | Node.js + Fastify + PM2（已有） |
| TILIAN API | `127.0.0.1` | 8001 | Python + FastAPI + systemd |

> 所有后端服务仅监听本地回环，不直接暴露到公网，统一由 Nginx 反向代理。  
> 数据库通过内网/公网连接阿里云 RDS，需在 RDS 白名单中放通 `115.190.7.207`。

---

## 四、访问路径规划

由于服务器无域名，统一使用 IP + 路径前缀区分：

| 访问地址 | 用途 |
|---|---|
| `http://115.190.7.207/` | Postcards H5 |
| `http://115.190.7.207/api/*` | Postcards API |
| `http://115.190.7.207/uploads/*` | Postcards 上传图片 |
| `http://115.190.7.207/stamps/*` | Postcards 邮票素材 |
| `http://115.190.7.207/tilian/` | TILIAN H5 |
| `http://115.190.7.207/tilian/api/*` | TILIAN API |
| `http://115.190.7.207/tilian/uploads/*` | TILIAN 上传文档 |

---

## 五、服务器目录规划

```
/data/
├── postcards/                 # Postcards 项目（已有）
│   ├── dist/                  # Node.js 构建产物
│   ├── h5/                    # H5 静态资源
│   ├── uploads/               # 用户上传图片
│   ├── stamps/                # 邮票素材
│   ├── package.json
│   └── ecosystem.config.js
│
├── tilian/                    # TILIAN 项目（新增）
│   ├── backend/               # Python 后端源码
│   ├── dist/                  # Vue3 前端构建产物
│   ├── uploads/               # 学习文档上传目录
│   ├── venv/                  # Python 虚拟环境
│   ├── .env                   # 环境变量
│   └── requirements.txt
│
└── logs/
    ├── postcards/             # Postcards 日志
    └── tilian/                # TILIAN 日志
```

---

## 六、前置条件

### 6.1 阿里云 RDS 白名单

TILIAN 后端部署前，需要在阿里云 RDS 控制台将火山引擎服务器公网 IP 加入白名单：

```
115.190.7.207
```

> 如果 Postcards 已经在使用阿里云 RDS，说明该 IP 可能已经在白名单中。TILIAN 使用同一个 RDS 实例或另一个 RDS 实例时，都需要确认已放行该 IP。

### 6.2 创建数据库与用户

在阿里云 RDS MySQL 中创建一个独立数据库供 TILIAN 使用（例如 `quizdb`），并创建一个专用账号（例如 `quiz`）。

```sql
CREATE DATABASE quizdb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'quiz'@'%' IDENTIFIED BY 'your-strong-password';
GRANT ALL PRIVILEGES ON quizdb.* TO 'quiz'@'%';
FLUSH PRIVILEGES;
```

### 6.3 服务器环境

服务器上需要已安装：
- Python 3.11
- Node.js 20（用于构建 TILIAN 前端；也可在 CI 中构建后上传）
- Nginx
- Postcards 已有环境（Node.js + PM2 + Nginx）

如果未安装 Python 3.11：

```bash
# Ubuntu/Debian 示例
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx
```

---

## 七、TILIAN 后端部署

### 7.1 创建目录并上传代码

```bash
sudo mkdir -p /data/tilian
sudo chown -R $USER:$USER /data/tilian

# 从开发机 rsync 推送
rsync -avz --delete \
  --exclude='venv' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  --exclude='uploads' \
  --exclude='.env' \
  --exclude='backend.log' \
  --exclude='aiquiz.db' \
  --exclude='*.pyc' \
  app/backend/ root@115.190.7.207:/data/tilian/backend/

# 同步 Alembic 迁移（首次及后续结构变更都需要）
rsync -avz --delete \
  app/alembic/ root@115.190.7.207:/data/tilian/alembic/
rsync -avz \
  app/alembic.ini root@115.190.7.207:/data/tilian/alembic.ini
```

### 7.2 创建虚拟环境并安装依赖

```bash
ssh root@115.190.7.207 "bash -s" <<'EOF'
cd /data/tilian
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
EOF
```

### 7.3 配置环境变量

服务器上创建 `/data/tilian/backend/.env`：

```bash
# 阿里云 RDS MySQL 8.0
DATABASE_URL=mysql+pymysql://quiz:your-password@rm-bp12t8q5bo58ct10d4o.mysql.rds.aliyuncs.com:3306/quizdb

# JWT
SECRET_KEY=replace-with-a-random-64-char-string

# Redis（可选；当前代码未强依赖）
REDIS_URL=redis://127.0.0.1:6379/0

# AI 模型（必须配置，否则文档生成不可用）
LLM_API_URL=https://api.moonshot.cn/v1/chat/completions
LLM_API_KEY=your-moonshot-api-key
LLM_MODEL=moonshot-v1-8k
AGENT_LLM_MODEL=moonshot-v1-32k

# 文件上传
UPLOAD_DIR=/data/tilian/uploads
MAX_UPLOAD_BYTES=10485760

# CORS（仅 IP 访问）
CORS_ORIGINS=["http://115.190.7.207"]

# 关闭调试
DEBUG=False
```

> 注意：`DATABASE_URL` 中的主机地址已填入你提供的阿里云 RDS MySQL 外网地址，需替换为实际用户名、密码和数据库名。

### 7.4 数据库迁移

```bash
ssh root@115.190.7.207 "bash -s" <<'EOF'
cd /data/tilian
source /data/tilian/venv/bin/activate
alembic upgrade head
EOF
```

> 首次部署可执行 `python init_demo_data.py` 初始化演示数据，生产环境可选。

### 7.5 使用 systemd 托管后端

将 `systemd/tilian-backend.service` 上传到服务器：

```bash
scp deploy/shared-server/systemd/tilian-backend.service \
  root@115.190.7.207:/etc/systemd/system/tilian-backend.service
```

启动服务：

```bash
ssh root@115.190.7.207 "bash -s" <<'EOF'
mkdir -p /data/logs/tilian
chown -R www-data:www-data /data/tilian /data/logs/tilian
systemctl daemon-reload
systemctl enable tilian-backend
systemctl start tilian-backend
systemctl status tilian-backend
EOF
```

---

## 八、TILIAN 前端部署

### 8.1 修改前端 base 路径

由于使用 `/tilian/` 路径前缀，需要修改 `app/frontend/vite.config.ts`：

```ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  base: '/tilian/',
  plugins: [vue()],
})
```

### 8.2 配置生产环境变量

创建 `app/frontend/.env.production`：

```bash
VITE_API_BASE_URL=http://115.190.7.207/tilian/api
```

### 8.3 构建并上传

```bash
cd app/frontend
npm install
npm run build

rsync -avz --delete \
  dist/ \
  root@115.190.7.207:/data/tilian/dist/
```

---

## 九、Nginx 统一配置

使用单 IP + 路径隔离方案。将 `nginx/postcards-tilian-path.conf` 上传到服务器：

```bash
scp deploy/shared-server/nginx/postcards-tilian-path.conf \
  root@115.190.7.207:/etc/nginx/conf.d/postcards-tilian.conf
```

然后测试并重载：

```bash
ssh root@115.190.7.207 "nginx -t && systemctl reload nginx"
```

### Nginx 配置要点

```nginx
server {
    listen 80;
    server_name 115.190.7.207;

    # Postcards 静态资源与 API（已有）
    location /uploads/ { ... }
    location /api/ { proxy_pass http://127.0.0.1:3000; }
    location / { alias /data/postcards/h5/; ... }

    # TILIAN 静态资源与 API（新增）
    location /tilian/uploads/ { alias /data/tilian/uploads/; }
    location /tilian/api/ { proxy_pass http://127.0.0.1:8001/api/; }
    location /tilian/ { alias /data/tilian/dist/; try_files ... /tilian/index.html; }
}
```

> 注意 `/tilian/api/` 的 `proxy_pass` 末尾带 `/`，这样 Nginx 转发给后端时会去掉 `/tilian/` 前缀，后端仍按 `/api/...` 处理。

---

## 十、CI/CD 自动部署

已创建 GitHub Actions workflow：`.github/workflows/deploy-tilian.yml`

### 触发方式

| 方式 | 说明 |
|---|---|
| `git push origin tilian-v1.0.0` | 推送以 `tilian-v` 开头的 tag 自动触发 |
| GitHub Actions 页面手动触发 | 可选择只部署后端或前端 |

### 部署流程

1. **build-frontend**：安装 Node.js 依赖，构建 H5，上传构建产物
2. **deploy-backend**：上传后端代码到服务器，安装依赖，执行数据库迁移，重启服务
3. **deploy-frontend**：下载构建产物，上传到服务器 `/data/tilian/dist/`，重载 Nginx

### GitHub Secrets 配置

在 GitHub 仓库 Settings → Secrets and variables → Actions 中添加：

| Secret | 值 | 说明 |
|---|---|---|
| `PROD_HOST` | `115.190.7.207` | 服务器公网 IP |
| `PROD_USERNAME` | `root` | SSH 用户名 |
| `PROD_DEPLOY_KEY` | SSH 私钥内容 | `~/.ssh/volcengine.pem` 的内容 |

### 使用方式

```bash
# 方式 1：推送 tag 自动部署
git tag tilian-v1.0.1
git push origin tilian-v1.0.1

# 方式 2：GitHub Actions 页面手动触发
# 进入仓库 Actions → Deploy TILIAN to Shared Server → Run workflow
```

> 注意：首次配置 GitHub Secrets 前，自动部署不会生效。

---

## 十一、对 Postcards 现有部署的影响

| 项目 | 是否需要调整 | 说明 |
|---|---|---|
| Postcards 后端端口 3000 | 无需调整 | 与 TILIAN 8001 不冲突 |
| Postcards 目录 `/data/postcards` | 无需调整 | 保持独立 |
| Postcards Nginx 配置 | **需要合并** | 将现有配置纳入统一文件，增加 `/tilian/` 路由 |
| Postcards CI/CD | 无需调整 | 完全独立 |
| Postcards 数据库 | 无需调整 | 继续使用阿里云 RDS MySQL |

> 合并 Nginx 时，建议先备份原配置，再使用本方案提供的 `postcards-tilian-path.conf` 替换。

---

## 十二、风险与注意事项

1. **阿里云 RDS 白名单**：必须将 `115.190.7.207` 加入 TILIAN 所用 RDS 实例的白名单。
2. **RDS 连接安全**：建议使用 SSL 连接 RDS，避免在公网传输明文密码。
3. **AI 密钥保密**：`LLM_API_KEY` 必须写入服务器 `.env`，不可提交到 Git。
4. **上传目录隔离**：`/data/postcards/uploads` 与 `/data/tilian/uploads` 必须严格分开。
5. **CORS 配置**：TILIAN 后端 `CORS_ORIGINS` 必须包含 `http://115.190.7.207`。
6. **HTTP 明文风险**：当前仅 IP 访问，建议后续申请域名并配置 HTTPS。
7. **日志磁盘管理**：`/data/logs/tilian` 和 `/data/logs/postcards` 需要配置 logrotate。
8. **数据库备份**：虽然 RDS 有自动备份，但仍建议定期检查备份策略。
9. **邀请码注册**：生产环境注册必须提供有效邀请码，管理员在 `/admin` 页面生成邀请码后分发。

---

## 十三、日志自动清理（logrotate）

已在服务器配置 logrotate，每日轮转 TILIAN 和 Postcards 日志，保留最近 14 天。

配置文件：`/etc/logrotate.d/tilian`

覆盖的日志路径：
- `/data/logs/tilian/*.log`
- `/data/postcards/logs/*.log`

测试命令：

```bash
sudo logrotate -d /etc/logrotate.d/tilian
```

手动触发轮转：

```bash
sudo logrotate -f /etc/logrotate.d/tilian
```

---

## 十四、部署检查清单

- [ ] 确认火山引擎服务器可访问（`ping 115.190.7.207`）
- [ ] 确认阿里云 RDS 白名单已放通 `115.190.7.207`
- [ ] 确认服务器已安装 Python 3.11 和 Nginx
- [ ] 创建 `/data/tilian` 目录并设置正确权限
- [ ] 上传 TILIAN 后端代码到 `/data/tilian/backend`
- [ ] 创建 Python 虚拟环境并安装依赖
- [ ] 创建 `/data/tilian/backend/.env` 并配置 RDS 连接、JWT、AI 密钥
- [ ] 执行 `alembic upgrade head` 完成数据库迁移
- [ ] 创建并启动 `tilian-backend.service`
- [ ] 修改 `vite.config.ts` 增加 `base: '/tilian/'`
- [ ] 创建 `.env.production` 设置 `VITE_API_BASE_URL=http://115.190.7.207/tilian/api`
- [ ] 构建 TILIAN 前端并上传到 `/data/tilian/dist`
- [ ] 上传合并后的 Nginx 配置并 reload
- [x] 测试 `curl http://115.190.7.207/tilian/health`
- [x] 测试 TILIAN 前端能正常加载并调用 `/tilian/api/`
- [x] 确认 Postcards 原有访问路径（`/`、`/api/`、`/uploads/`）不受影响
- [x] 配置 logrotate 与日志清理

---

## 十五、文件清单

本目录下提供了可直接使用的配置文件模板：

| 文件 | 用途 |
|---|---|
| `nginx/postcards-tilian-path.conf` | 单 IP 路径隔离 Nginx 配置 |
| `systemd/tilian-backend.service` | TILIAN 后端 systemd 服务 |
| `pm2/tilian-backend.config.js` | 可选：PM2 托管 TILIAN 后端 |
| `scripts/deploy-tilian.sh` | TILIAN 手动部署脚本 |
| `env/tilian.env.example` | TILIAN 生产环境变量模板 |

---

*文档版本：v1.2*  
*更新日期：2026-07-13*  
*更新说明：新增邀请码注册功能，修正 Alembic 迁移命令工作目录，同步手动部署脚本。*
