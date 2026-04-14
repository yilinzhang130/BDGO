# BD Go — 部署与更新指南

## 架构概览

```
用户浏览器
    │
    ▼
Vercel (Next.js 前端)          ← git push main 自动部署
https://bdgo-iota.vercel.app
    │  /api/* 反向代理
    ▼
腾讯云 VM: 146.56.247.221
  ├── Docker: bdgo_backend     ← FastAPI，端口 8001（代码打包进镜像）
  ├── Docker: bdgo_nginx       ← Nginx，端口 80，upstream → 172.17.0.1:8001
  └── PostgreSQL 15            ← 宿主机直接运行，端口 5432
        ├── bdgo        (用户/报告数据库)
        └── openclaw_crm (CRM 数据库)
```

**关键约束**：
- VM 在国内，**无法访问 Google / GitHub / PyPI 官方源**（pip 用腾讯镜像）
- `bdgo_backend` 代码打包进镜像，`docker restart` 不更新代码，必须重新 build
- 只有 `/home/ubuntu/bdgo/data` 是 volume 挂载（运行时数据），其余都在镜像里

---

## 后端更新（改了 api/ 下的任何文件）

```bash
# 1. 本地同步代码到 VM
rsync -avz api/ ubuntu@146.56.247.221:~/bdgo/api/

# 2. 在 VM 上重新 build 镜像并替换容器（一条命令）
ssh ubuntu@146.56.247.221 "
  cd ~/bdgo &&
  docker build -t bdgo_backend . &&
  docker rm -f bdgo_backend &&
  docker run -d \
    --name bdgo_backend \
    --restart=always \
    -p 8001:8001 \
    -v /home/ubuntu/bdgo/data:/app/data \
    --env-file /home/ubuntu/bdgo/.env \
    bdgo_backend
"

# 3. 验证
curl http://146.56.247.221/api/health
```

> ⚠️ 不要用 `docker restart` 更新代码，只有修改 `.env` 后才用 `docker rm -f + docker run`（无需 build）。

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
npx vercel env add KEY production                      # 新增（用 printf 管道，避免 \n）
printf "value" | npx vercel env add KEY production
npx vercel env rm KEY production --yes                 # 删除
```

已配置的变量：
| 变量名 | 说明 |
|--------|------|
| `NEXT_PUBLIC_API_URL` | `http://146.56.247.221`（VM 公网 IP） |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Google OAuth（已删除前端入口，保留备用） |

---

## VM 环境变量（`~/bdgo/.env`）

```
DATABASE_URL=postgresql://bdgo:...@172.17.0.1:5432/bdgo
CRM_PG_DSN=host=172.17.0.1 dbname=openclaw_crm user=bdgo password=...
JWT_SECRET=<随机32字节hex>
MINIMAX_API_KEY=sk-cp-...
CORS_ORIGINS=https://bdgo-iota.vercel.app,http://localhost:3000
GOOGLE_CLIENT_ID=488166218680-...（后端保留，前端已不使用）
```

修改 `.env` 后需重新创建容器（无需 rebuild 镜像）：
```bash
ssh ubuntu@146.56.247.221 "
  docker rm -f bdgo_backend &&
  docker run -d --name bdgo_backend --restart=always \
    -p 8001:8001 -v /home/ubuntu/bdgo/data:/app/data \
    --env-file /home/ubuntu/bdgo/.env bdgo_backend
"
```

---

## Nginx 更新

```bash
rsync -avz nginx/ ubuntu@146.56.247.221:~/bdgo/nginx/
ssh ubuntu@146.56.247.221 "docker restart bdgo_nginx"
# Nginx 配置是 volume 挂载的，restart 即可生效
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

## 容器状态检查

```bash
ssh ubuntu@146.56.247.221 "docker ps && curl -s http://localhost:8001/api/health"

# 查看后端日志（最近50行）
ssh ubuntu@146.56.247.221 "docker logs bdgo_backend --tail 50"

# 确认容器内代码版本（检查某个关键字）
ssh ubuntu@146.56.247.221 "docker exec bdgo_backend grep -n 'KEYWORD' /app/api/routers/auth.py"
```

---

## 常见问题

| 现象 | 原因 | 解法 |
|------|------|------|
| 后端改了没生效 | 只做了 `docker restart`，代码在镜像里 | 重新 build 镜像（见上）|
| 前端 `NEXT_PUBLIC_` 变量没生效 | `redeploy` 复用旧 build | 推空 commit 触发新 build |
| `permission denied for table 公司` | PostgreSQL 权限丢失 | 重新 GRANT（见上）|
| nginx `host not found in upstream` | 容器网络隔离，不能用容器名 | upstream 用 `172.17.0.1:8001` |
| VM 重启后容器消失 | 没设 `--restart=always` | `docker update --restart=always <name>` |
