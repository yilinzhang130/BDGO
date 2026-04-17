# BD Go — 部署与更新指南

## 架构概览

```
用户浏览器
    │  https://bdgo.tech
    ▼
Vercel (Next.js 前端)          ← git push main 自动部署
https://bdgo.tech  (自定义域名)
https://bdgo-iota.vercel.app   (Vercel 原始域名，仍有效)
    │  /api/* 服务器端 rewrite → VM:8000
    ▼
腾讯云 VM: 146.56.247.221
  ├── bdgo-api.service          ← systemd，uvicorn，端口 8000
  │     WorkingDir: ~/bdgo/api
  │     Venv:       ~/bdgo/venv
  │     EnvFile:    ~/bdgo/.env
  ├── Nginx                     ← 端口 80，proxy_pass → 127.0.0.1:8000
  ├── AIDD API                  ← uvicorn，端口 8001 (~/drug-discovery/backend)
  └── PostgreSQL 15             ← 宿主机直接运行，端口 5432
        └── bdgo                (用户/报告/CRM 数据库)
```

> VM 不需要 SSL 证书 — 浏览器只访问 Vercel HTTPS；Vercel → VM 是服务器间 HTTP。

---

## 后端更新（改了 api/ 下的任何文件）

```bash
# 1. 本地同步代码到 VM（需要 SSH 连通）
rsync -avz api/ ubuntu@146.56.247.221:~/bdgo/api/

# 2. 重启服务
ssh ubuntu@146.56.247.221 "sudo systemctl restart bdgo-api"

# 3. 验证
curl http://146.56.247.221/api/health
```

**一条命令搞定（常用）：**
```bash
rsync -avz api/ ubuntu@146.56.247.221:~/bdgo/api/ && \
ssh ubuntu@146.56.247.221 "sudo systemctl restart bdgo-api && sleep 2 && curl -s http://localhost:8000/api/health"
```

### SSH 连不上时（用腾讯云网页终端）

> 控制台 → 云服务器 → 实例 → 登录 → OrcaTerm

```bash
# 直接在网页终端里修改文件，然后重启：
sudo systemctl restart bdgo-api
curl -s http://localhost:8000/api/health
```

### 修改 .env 后

```bash
# 只需重启，不需要重新安装
ssh ubuntu@146.56.247.221 "sudo systemctl restart bdgo-api"
```

### 新增 Python 依赖后

```bash
ssh ubuntu@146.56.247.221 "
  cd ~/bdgo &&
  venv/bin/pip install -r api/requirements.txt -i https://mirrors.tencent.com/pypi/simple/ &&
  sudo systemctl restart bdgo-api
"
```

---

## 前端更新（改了 frontend/ 下的任何文件）

```bash
git add . && git commit -m "..." && git push
# Vercel 监听 main 分支，自动触发构建，约 1 分钟
```

**如果改了 `NEXT_PUBLIC_` 开头的环境变量**：
- `vercel redeploy` 复用旧 build 产物，新变量不生效
- 必须触发新 build：`git commit --allow-empty -m "chore: rebuild" && git push`

---

## Vercel 环境变量

```bash
cd frontend && npx vercel link --yes --project bdgo   # 只需首次执行

npx vercel env ls                                      # 查看
printf "value" | npx vercel env add KEY production    # 新增
npx vercel env rm KEY production --yes                 # 删除
```

已配置的变量：
| 变量名 | 说明 |
|--------|------|
| `NEXT_PUBLIC_API_URL` | `http://146.56.247.221`（VM 公网 IP） |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Google OAuth（保留备用） |

---

## VM 环境变量（`~/bdgo/.env`）

```
DATABASE_URL=postgresql://bdgo:...@127.0.0.1:5432/bdgo
CRM_PG_DSN=host=127.0.0.1 dbname=bdgo user=bdgo password=...
JWT_SECRET=<随机32字节hex>
MINIMAX_API_KEY=sk-cp-...
CORS_ORIGINS=https://bdgo.tech,https://www.bdgo.tech,https://bdgo-iota.vercel.app,http://localhost:3000
AIDD_SSO_SECRET=<共享密钥，勿入git>
AIDD_BASE_URL=https://aidd-two.vercel.app
```

修改 `.env` 后：
```bash
sudo systemctl restart bdgo-api
```

---

## Nginx 更新

```bash
rsync -avz nginx/ ubuntu@146.56.247.221:~/bdgo/nginx/
ssh ubuntu@146.56.247.221 "sudo systemctl restart nginx"
```

---

## PostgreSQL 权限（VM 重启后偶发）

```bash
ssh ubuntu@146.56.247.221 "
  PGPASSWORD=Wazx910130 psql -U postgres -h 127.0.0.1 -d bdgo -c \"
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO bdgo;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO bdgo;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO bdgo;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO bdgo;
  \"
"
```

---

## 状态检查

```bash
# 服务状态
ssh ubuntu@146.56.247.221 "sudo systemctl status bdgo-api | head -10"

# 日志（最近50行）
ssh ubuntu@146.56.247.221 "tail -50 ~/bdgo/logs/bdgo_api.log"

# 健康检查
curl http://146.56.247.221/api/health
```

---

## 常见问题

| 现象 | 原因 | 解法 |
|------|------|------|
| 后端改了没生效 | 忘记 restart | `sudo systemctl restart bdgo-api` |
| SSH `kex_exchange_identification` | macOS crypto.conf 限制 | `ssh -o KexAlgorithms=curve25519-sha256 ubuntu@146.56.247.221` |
| SSH 连不上 | 用网页终端替代 | 腾讯云控制台 → 登录 → OrcaTerm |
| 前端 `NEXT_PUBLIC_` 变量没生效 | `redeploy` 复用旧 build | 推空 commit 触发新 build |
| `permission denied for table 公司` | PostgreSQL 权限丢失 | 重新 GRANT（见上）|
