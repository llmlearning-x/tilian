#!/bin/bash
set -e

# ============================================================
# TILIAN 手动部署脚本
# 在本机执行，将代码推送到与 Postcards 共用的火山引擎服务器
# 服务器公网 IP：115.190.7.207
# ============================================================

SERVER="root@115.190.7.207"
REMOTE_DIR="/data/tilian"
BACKEND_DIR="app/backend"
FRONTEND_DIR="app/frontend"

echo "==> 构建前端..."
cd "$(dirname "$0")/../../.."
cd "$FRONTEND_DIR"
npm install
npm run build

echo "==> 同步后端代码到服务器..."
cd "$(dirname "$0")/../../.."
rsync -avz --delete \
  --exclude='venv' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  --exclude='uploads' \
  --exclude='.env' \
  --exclude='backend.log' \
  --exclude='aiquiz.db' \
  --exclude='*.pyc' \
  "$BACKEND_DIR/" "$SERVER:$REMOTE_DIR/backend/"

echo "==> 同步 Alembic 迁移到服务器..."
rsync -avz --delete \
  app/alembic/ "$SERVER:$REMOTE_DIR/alembic/"
rsync -avz \
  app/alembic.ini "$SERVER:$REMOTE_DIR/alembic.ini"

echo "==> 同步前端构建产物到服务器..."
rsync -avz --delete \
  "$FRONTEND_DIR/dist/" "$SERVER:$REMOTE_DIR/dist/"

echo "==> 服务器：安装/更新依赖并迁移数据库..."
ssh "$SERVER" "bash -s" <<'EOF'
set -e
REMOTE_DIR="/data/tilian"
mkdir -p "$REMOTE_DIR/uploads" /data/logs/tilian

# 创建虚拟环境（如果不存在）
if [ ! -d "$REMOTE_DIR/venv" ]; then
    python3 -m venv "$REMOTE_DIR/venv"
fi

source "$REMOTE_DIR/venv/bin/activate"
cd "$REMOTE_DIR/backend"
pip install --upgrade pip
pip install -r requirements.txt

# 数据库迁移（alembic.ini 位于 /data/tilian）
cd "$REMOTE_DIR"
alembic upgrade head
EOF

echo "==> 服务器：修正目录权限..."
ssh "$SERVER" "chown -R www-data:www-data $REMOTE_DIR/backend $REMOTE_DIR/alembic $REMOTE_DIR/dist $REMOTE_DIR/uploads"

echo "==> 服务器：重启 TILIAN 后端服务..."
ssh "$SERVER" "systemctl restart tilian-backend || pm2 reload tilian-backend"

echo "==> 服务器：重载 Nginx..."
ssh "$SERVER" "nginx -t && systemctl reload nginx"

echo "✅ TILIAN 部署完成"
echo ""
echo "健康检查：curl http://115.190.7.207/tilian/health"
