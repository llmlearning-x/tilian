# Postcards（旅行邮箱）项目部署方案分析

> 分析对象：https://github.com/llmlearning-x/Postcards/tree/main  
> 分析日期：2026-07-13

---

## 一、项目概述

**Postcards（旅行邮箱）** 是一款基于旅行场景的明信片记录与社交应用。仓库采用多平台 monorepo 结构，当前已上线的形态包括 H5 页面与 Android App。

| 平台 | 状态 | 线上地址 |
|---|---|---|
| H5 | ✅ 已上线 | http://115.190.7.207 |
| Android App | ✅ 已发布 | GitHub Release v1.0.0 APK |
| iOS App | 🚧 计划中 | — |
| 微信小程序 | 🚧 计划中 | — |
| HarmonyOS | 🚧 计划中 | — |

```
Postcards/
├── Postcards-UniApp/    # 跨端前端（H5 + 小程序 + App）
├── Postcards-Server/    # Node.js 后端 API
├── Postcards-iOS/       # iOS 原生项目
├── Postcards-Android/   # Android 原生项目
├── Postcards-Harmony/   # HarmonyOS 项目
└── docs/                # 产品手册（GitHub Pages）
```

---

## 二、实际部署架构

当前项目采用 **单台云服务器 + Nginx + PM2 + GitHub Actions** 的传统部署模式，属于典型的早期 MVP 方案。

```
┌─────────────────────────────────────────────────────────┐
│                      客户端层                            │
│   H5 浏览器 / Android App / 小程序 / iOS / HarmonyOS    │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                     Nginx（80 端口）                      │
│  ├─ /uploads/  → 静态文件服务（本地目录）                 │
│  ├─ /api/      → 反向代理到 127.0.0.1:3000              │
│  └─ /          → H5 静态资源                             │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│              Node.js + Fastify（PM2 托管）                │
│                   监听 127.0.0.1:3000                    │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                     MySQL 数据库                         │
│              （mysql2 驱动，端口 3306）                    │
└─────────────────────────────────────────────────────────┘
```

---

## 三、后端服务部署

### 3.1 技术栈（实际代码）

| 组件 | 实际使用 | 备注 |
|---|---|---|
| 运行时 | Node.js 20 | GitHub Actions 指定版本 |
| Web 框架 | Fastify 4.x | `package.json` 依赖 |
| 语言 | TypeScript | 构建输出到 `dist/` |
| 数据库 | MySQL | 依赖 `mysql2` |
| 鉴权 | JWT | `@fastify/jwt` |
| 上传/图片 | `@fastify/multipart` + `sharp` | 本地磁盘存储 |
| 进程管理 | PM2 | `ecosystem.config.js` |

> **注意**：README 中写后端使用 Express、数据库为 MySQL + Redis；架构设计文档中写后端使用 Go/NestJS、PostgreSQL + MongoDB + Redis。这些与仓库实际代码存在不一致。

### 3.2 PM2 进程配置

文件：`Postcards-Server/ecosystem.config.js`

```js
module.exports = {
  apps: [{
    name: 'postcards-api',
    script: './dist/index.js',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '512M',
    env: {
      NODE_ENV: 'production',
      PORT: 3000,
    },
    env_file: '/path/to/postcards/.env',      // 需手动替换为真实路径
    error_file: '/path/to/postcards/logs/err.log',
    out_file: '/path/to/postcards/logs/out.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss',
  }],
};
```

### 3.3 Nginx 配置

文件：`Postcards-Server/nginx.conf`

```nginx
server {
    listen 80;
    server_name your-server-ip;    # 需替换为真实 IP/域名

    # 用户上传图片静态文件
    location /uploads/ {
        alias /path/to/postcards/uploads/;
        expires 30d;
        add_header Cache-Control "public, immutable";
        add_header Access-Control-Allow-Origin "*";
    }

    # API 反代到 Node.js
    location /api/ {
        proxy_pass         http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        client_max_body_size 15M;
    }

    # 健康检查
    location /health {
        proxy_pass http://127.0.0.1:3000;
    }
}
```

### 3.4 环境变量

文件：`Postcards-Server/.env.example`

```bash
# 数据库
DB_HOST=your-rds-host.mysql.rds.aliyuncs.com
DB_PORT=3306
DB_NAME=postcards
DB_USER=your_db_user
DB_PASS=your_db_password

# JWT 密钥
JWT_SECRET=change-this-to-a-random-64-char-string-in-production
JWT_REFRESH_SECRET=change-this-to-another-random-64-char-string

# 服务配置
PORT=3000
HOST=0.0.0.0
NODE_ENV=production

# 图片存储目录（绝对路径）
UPLOAD_DIR=/path/to/postcards/uploads
UPLOAD_BASE_URL=https://your-domain.com/uploads

# CORS 允许来源
CORS_ORIGIN=https://your-domain.com

# 邮票图片访问域名
STAMPS_BASE_URL=https://your-domain.com/stamps

# 图片限制
MAX_FILE_SIZE_MB=10
```

### 3.5 本地部署脚本

文件：`Postcards-Server/deploy.sh`

```bash
#!/bin/bash
set -e

SERVER="root@115.175.15.145"        # 硬编码旧 IP，已不一致
REMOTE_DIR="/data/postcards"
APP_NAME="postcards-api"

npm run build

rsync -avz --delete \
  --exclude='.env' \
  --exclude='node_modules' \
  --exclude='uploads' \
  --exclude='logs' \
  dist/ "$SERVER:$REMOTE_DIR/dist/"

rsync -avz \
  package.json \
  ecosystem.config.js \
  "$SERVER:$REMOTE_DIR/"

ssh "$SERVER" "cd $REMOTE_DIR && npm install --omit=dev"
ssh "$SERVER" "cd $REMOTE_DIR && pm2 reload $APP_NAME || pm2 start ecosystem.config.js"
ssh "$SERVER" "pm2 save"
```

> ⚠️ 脚本中硬编码了 `root@115.175.15.145`，但 README 中公布的 H5 生产地址为 `115.190.7.207`，说明服务器信息经历过迁移或清理。

---

## 四、前端 H5 部署

### 4.1 技术栈

| 组件 | 实际使用 |
|---|---|
| 框架 | UniApp 3（Vue 3 + TypeScript + Vite） |
| 状态管理 | Pinia |
| 图标 | Phosphor Icons |
| 构建工具 | `@dcloudio/vite-plugin-uni` |

### 4.2 构建命令

```bash
cd Postcards-UniApp
npm install
npm run build:h5
```

产物目录：`Postcards-UniApp/dist/build/h5/`

### 4.3 部署位置

服务器目标路径：`/data/postcards/h5/`

由 Nginx 直接作为静态站点托管，API 通过同域名 `/api/` 路径代理到后端。

---

## 五、CI/CD 自动化部署

### 5.1 工作流文件

`.github/workflows/deploy-prod.yml`

### 5.2 触发条件

| 触发方式 | 说明 |
|---|---|
| `push tags: - 'v*'` | 推送 `v1.0.0` 等 tag 时自动触发 |
| `workflow_dispatch` | 手动触发，可选择是否部署后端/前端 |

### 5.3 GitHub Secrets

| Secret | 用途 |
|---|---|
| `PROD_HOST` | 生产服务器 IP |
| `PROD_USERNAME` | SSH 用户名 |
| `PROD_DEPLOY_KEY` | SSH 私钥 |

### 5.4 后端部署 Job

```yaml
deploy-backend:
  runs-on: ubuntu-latest
  working-directory: Postcards-Server
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: '20'
        cache: 'npm'
        cache-dependency-path: Postcards-Server/package-lock.json
    - run: npm ci
    - run: npm run build
    - name: Clean old build on server
      uses: appleboy/ssh-action@v1.0.3
      with:
        host: ${{ secrets.PROD_HOST }}
        username: ${{ secrets.PROD_USERNAME }}
        key: ${{ secrets.PROD_DEPLOY_KEY }}
        script: rm -rf /data/postcards/dist
    - name: Deploy to production server
      uses: appleboy/scp-action@v0.1.7
      with:
        host: ${{ secrets.PROD_HOST }}
        username: ${{ secrets.PROD_USERNAME }}
        key: ${{ secrets.PROD_DEPLOY_KEY }}
        source: "Postcards-Server/dist/,Postcards-Server/package.json,Postcards-Server/ecosystem.config.js,Postcards-Server/stamps/"
        target: "/data/postcards/"
        strip_components: 1
    - name: Restart backend
      uses: appleboy/ssh-action@v1.0.3
      with:
        host: ${{ secrets.PROD_HOST }}
        username: ${{ secrets.PROD_USERNAME }}
        key: ${{ secrets.PROD_DEPLOY_KEY }}
        script: |
          cd /data/postcards
          mkdir -p /data/postcards/uploads
          npm install --omit=dev
          pm2 reload postcards-api || pm2 start ecosystem.config.js
          pm2 save
```

### 5.5 前端部署 Job

```yaml
deploy-frontend:
  runs-on: ubuntu-latest
  working-directory: Postcards-UniApp
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: '20'
        cache: 'npm'
        cache-dependency-path: Postcards-UniApp/package-lock.json
    - run: npm ci
    - run: npm run build:h5
    - name: Clean old H5 on server
      uses: appleboy/ssh-action@v1.0.3
      with:
        host: ${{ secrets.PROD_HOST }}
        username: ${{ secrets.PROD_USERNAME }}
        key: ${{ secrets.PROD_DEPLOY_KEY }}
        script: rm -rf /data/postcards/h5/assets /data/postcards/h5/static /data/postcards/h5/index.html
    - name: Deploy to production server
      uses: appleboy/scp-action@v0.1.7
      with:
        host: ${{ secrets.PROD_HOST }}
        username: ${{ secrets.PROD_USERNAME }}
        key: ${{ secrets.PROD_DEPLOY_KEY }}
        source: "Postcards-UniApp/dist/build/h5/"
        target: "/data/postcards/h5"
        strip_components: 4
    - name: Reload nginx
      uses: appleboy/ssh-action@v1.0.3
      with:
        host: ${{ secrets.PROD_HOST }}
        username: ${{ secrets.PROD_USERNAME }}
        key: ${{ secrets.PROD_DEPLOY_KEY }}
        script: nginx -t && systemctl reload nginx
```

---

## 六、方案优点

1. **简单直接**：适合小团队和项目早期阶段，学习曲线低，维护成本小。
2. **自动化程度高**：打 tag 即可同时触发前后端部署，减少人工操作。
3. **手动回滚可控**：通过重新推送旧 tag 即可快速回滚。
4. **静态资源分离**：`/uploads/` 直接由 Nginx 处理，降低 Node.js 负担。
5. **进程守护**：PM2 保证服务崩溃后自动重启，并支持日志管理。
6. **部署灵活**：支持 `workflow_dispatch` 手动选择只部署后端或前端。

---

## 七、存在的问题与风险

### 7.1 文档与代码不一致

| 文档/配置 | 说明 | 实际代码 |
|---|---|---|
| README | 后端框架 Express | Fastify |
| README | 数据库 MySQL + Redis | 仅用 MySQL（无 Redis 依赖） |
| 技术架构设计 | 后端 Go/NestJS、PostgreSQL + MongoDB + Redis | Node.js + Fastify + MySQL |
| 技术架构设计 | 微服务 + K8s | 单体单实例 |

这会导致新成员、运维人员或审计方产生误解，建议统一文档。

### 7.2 安全与权限问题

- `deploy.sh` 中硬编码了 `root@115.175.15.145`，存在敏感信息残留。
- 使用 root 账号直接部署不符合最小权限原则。
- H5 当前使用 HTTP（`http://115.190.7.207`），存在明文传输风险。
- `.env.example` 与 `ecosystem.config.js` 中路径仍为占位符，说明生产配置未完全模板化。

### 7.3 高可用与扩展性不足

- 单实例部署，无负载均衡。
- 无 Docker/Kubernetes，环境一致性依赖手动维护。
- 数据库单点，未体现备份、主从或灾备方案。
- 无灰度发布、蓝绿部署或健康检查自动回滚机制。

### 7.4 CI/CD 缺少质量门禁

- 未运行单元测试。
- 未运行 TypeScript 类型检查（`tsc --noEmit`）。
- 未进行依赖漏洞扫描或代码安全扫描。
- 数据库迁移脚本 `db:migrate` 未在 CI/CD 中自动执行。

### 7.5 监控与日志缺失

- 架构文档提到 Prometheus、Grafana、阿里云 SLS、ARMS，但实际代码中未看到集成。
- PM2 日志仅写入本地文件，无集中化日志与告警。
- 缺少应用级指标监控与告警通知。

### 7.6 静态资源存储局限

- 用户上传图片直接存服务器本地磁盘，扩容困难。
- 随着用户量增长，建议迁移至对象存储（如华为云 OBS / 阿里云 OSS）并配合 CDN。

---

## 八、改进建议

### 8.1 短期改进（低成本）

1. **统一文档**：修正 README 与架构文档中与实际代码不符的技术栈描述。
2. **清理敏感信息**：将 `deploy.sh` 中的服务器 IP、用户名改为环境变量或删除该文件。
3. **使用非 root 账号部署**：创建专用 `deployer` 用户，限制 sudo 权限。
4. **增加 CI 质量门禁**：在 GitHub Actions 中加入 `npm run build` 类型检查、单元测试、lint。
5. **自动执行数据库迁移**：在部署步骤中加入 `npm run db:migrate`。
6. **配置 HTTPS**：为域名申请 SSL 证书，Nginx 强制 HTTP 跳转 HTTPS。

### 8.2 中期改进（架构升级）

1. **容器化**：使用 Dockerfile 打包后端服务，保证环境一致性。
2. **对象存储 + CDN**：将 `uploads/` 迁移至 OBS/OSS，静态资源接入 CDN。
3. **引入反向代理负载均衡**：后续多实例部署时，使用 Nginx 或云 LB 做负载均衡。
4. **数据库高可用**：配置 MySQL 主从、定期备份、监控告警。
5. **集中化日志**：接入 ELK、Loki 或云厂商日志服务。

### 8.3 长期改进（规模化）

1. **Kubernetes 部署**：将服务迁移至 K8s，支持自动扩缩容。
2. **灰度发布**：基于 Ingress/网关实现金丝雀发布。
3. **服务拆分**：当业务复杂后，按领域拆分为独立微服务。
4. **全链路监控**：接入 APM、分布式链路追踪、业务指标大盘。

---

## 九、总结

Postcards 项目当前采用的是 **典型的早期项目「单机 + PM2 + Nginx + GitHub Actions」部署方案**，能够快速支撑 H5 和 Android 上线，自动化部署流程基本跑通，适合 MVP 阶段。

但随着业务发展，项目在 **文档一致性、部署安全、数据库高可用、容器化、CI 质量门禁、监控告警、静态资源上云** 等方面需要持续补强，才能支撑更大规模的用户访问和团队协作。

---

*文档生成时间：2026-07-13*
