// 可选：使用 PM2 托管 TILIAN FastAPI 后端
// 如果你希望与 Postcards 使用同一套进程管理工具，可以使用此配置
// 用法：pm2 start /data/tilian/tilian-backend.config.js

module.exports = {
  apps: [
    {
      name: 'tilian-backend',
      script: '/data/tilian/venv/bin/gunicorn',
      args: 'main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8001',
      cwd: '/data/tilian/backend',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      env: {
        PATH: '/data/tilian/venv/bin',
      },
      // 从 .env 文件加载环境变量（需要 pm2 支持）
      env_file: '/data/tilian/backend/.env',
      error_file: '/data/logs/tilian/error.log',
      out_file: '/data/logs/tilian/out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
    },
  ],
};
