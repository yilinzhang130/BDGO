# BD Go — 部署与更新指南

## 架构概览

```
用户浏览器
    │  https://bdgo.tech
    ▼
Vercel (Next.js 前端)          ← git push origin main 自动部署
https://bdgo.tech  (自定义域名)
https://bdgo-iota.vercel.app   (Vercel 原始域名，仍有效)
    │  /api/* 服务器端 rewrite → VM:8000  （内部 HTTP，无中间层）
    ▼
腾讯云 VM: 106.54.202.181
  ├── bdgo-api.service   ← systemd，uvicorn 直接监听 0.0.0.0:8000
  │     WorkingDir: ~/bdgo/api
  │     Venv:       ~/bdgo/venv
  │     EnvFile:    ~/bdgo/.env
  │     Log:        ~/bdgo/logs/bdgo_api.log
  ├── AIDD API          ← python :8001  (~/drug-discovery/backend)
  └── PostgreSQL 14     ← 127.0.0.1:5432，bdgo 数据库
```

> 目前**没有 Nginx** — uvicorn 直接暴露 8000，Vercel rewrite 直连。
> TLS 由 Vercel 终止，Vercel→VM 是服务器间 HTTP。
> 要隐藏 8000 端口或让第三方直连 API 时再加 nginx。

---

## 后端更新（改了 api/ 下的文件）

**一条命令部署：**
```bash
git push vm main
```

VM 端 `~/bdgo.git/hooks/post-receive` 会自动：
1. `rsync -a --delete` 同步 `api/` 到 `~/bdgo/api/`（仅此一个目录会被覆盖）
2. `sudo systemctl restart bdgo-api`
3. `curl http://localhost:8000/api/health` 健康检查
4. 失败会打印最近 30 行 journal log 并退出非 0

**验证：**
```bash
curl http://106.54.202.181:8000/api/health
```

### push 覆盖范围

`git push vm main` 把**整个仓库**推到 VM 的 bare 仓库 `~/bdgo.git`，但 hook **只把 `api/` 解到工作目录**。其他目录（`frontend/`、`nginx/`、`scripts/`、`docs/`）只存在 bare repo 里，不会落到 `~/bdgo/`。

**完全不受 push 影响的文件/目录：**
- `~/bdgo/.env`（环境变量，手动维护）
- `~/bdgo/venv/`（Python 虚拟环境）
- `~/bdgo/data/`（数据文件）
- `~/bdgo/logs/`（日志）
- `~/bdgo/api.backup.*/`（旧版本备份）

### 本地 push 不上时用腾讯云网页终端

> 控制台 → 云服务器 → 实例 → 登录 → OrcaTerm

```bash
cd ~/bdgo.git && git fetch origin main 2>/dev/null  # 如有需要
# 或直接在 OrcaTerm 里 nano 改文件，然后：
sudo systemctl restart bdgo-api
curl -s http://localhost:8000/api/health
```

### 修改 .env 后

`.env` 不随 push 改动，需要 ssh 进去改然后重启：
```bash
ssh ubuntu@106.54.202.181 "nano ~/bdgo/.env && sudo systemctl restart bdgo-api"
```

### 新增 Python 依赖后

hook 不会自动 `pip install`。改了 `requirements.txt` 后：
```bash
git push vm main    # 代码先到位
ssh ubuntu@106.54.202.181 "
  cd ~/bdgo &&
  venv/bin/pip install -r api/requirements.txt -i https://mirrors.tencent.com/pypi/simple/ &&
  sudo systemctl restart bdgo-api
"
```

---

## 前端更新（改了 frontend/ 下的文件）

```bash
git push origin main
# Vercel 监听 main 分支，自动触发构建，约 1 分钟
```

**如果改了 `NEXT_PUBLIC_` 开头的环境变量：**
- `vercel redeploy` 复用旧 build 产物，新变量不生效
- 必须触发新 build：`git commit --allow-empty -m "chore: rebuild" && git push origin main`

---

## Vercel 环境变量

```bash
cd frontend && npx vercel link --yes --project bdgo   # 只需首次执行

npx vercel env ls                                      # 查看
printf "value" | npx vercel env add KEY production    # 新增
npx vercel env rm KEY production --yes                 # 删除
```

| 变量名 | 说明 |
|--------|------|
| `NEXT_PUBLIC_API_URL` | `http://106.54.202.181:8000`（VM + uvicorn 端口） |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Google OAuth（保留备用） |

---

## VM 环境变量（`~/bdgo/.env`）

```
DATABASE_URL=postgresql://bdgo:...@127.0.0.1:5432/bdgo
CRM_PG_DSN=host=127.0.0.1 dbname=bdgo user=bdgo password=...
JWT_SECRET=<随机32字节hex>
MINIMAX_API_KEY=sk-cp-...
CORS_ORIGINS=https://bdgo.tech,https://www.bdgo.tech,https://bdgo-iota.vercel.app,http://localhost:3000
ADMIN_SECRET=<随机32字节hex>
LOG_FORMAT=json
AIDD_SSO_SECRET=<共享密钥，勿入 git>
AIDD_BASE_URL=https://aidd-two.vercel.app
```

改 `.env` 后：
```bash
ssh ubuntu@106.54.202.181 "sudo systemctl restart bdgo-api"
```

---

## Git Remotes 一览

```
origin  ─> GitHub (源码，frontend 走 Vercel 从这里构建)
vm      ─> ubuntu@106.54.202.181:~/bdgo.git  (push 自动部署 api/)
gitee   ─> Gitee 镜像（备用，GitHub 访问不畅时用）
```

---

## PostgreSQL 权限（VM 重启后偶发）

```bash
# Replace <PG_PASSWORD> with the actual postgres superuser password (do NOT commit it)
ssh ubuntu@106.54.202.181 "
  PGPASSWORD=<PG_PASSWORD> psql -U postgres -h 127.0.0.1 -d bdgo -c \"
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
ssh ubuntu@106.54.202.181 "sudo systemctl status bdgo-api | head -10"

# 日志（最近 50 行）
ssh ubuntu@106.54.202.181 "tail -50 ~/bdgo/logs/bdgo_api.log"

# 实时 journal
ssh ubuntu@106.54.202.181 "sudo journalctl -u bdgo-api -f"

# 健康检查
curl http://106.54.202.181:8000/api/health
```

---

## 常见问题

| 现象 | 原因 | 解法 |
|------|------|------|
| push 后 hook 报 HEALTH CHECK FAILED | 代码出错，bdgo-api 启动失败 | 看 hook 打印的 journal log；修了再 push |
| 后端改了没生效 | 只 commit 没 push 到 vm | `git push vm main` |
| SSH `kex_exchange_identification` | macOS crypto.conf 限制 | `ssh -o KexAlgorithms=curve25519-sha256 ubuntu@106.54.202.181` |
| SSH 连不上 | 用网页终端替代 | 腾讯云控制台 → 登录 → OrcaTerm |
| 前端 `NEXT_PUBLIC_` 变量没生效 | `redeploy` 复用旧 build | 推空 commit 触发新 build |
| `permission denied for table 公司` | PostgreSQL 权限丢失 | 重新 GRANT（见上） |
| 依赖装了但还是 ModuleNotFoundError | 忘了重启 bdgo-api | `sudo systemctl restart bdgo-api` |

---

## 回退

hook 没做自动备份。需要回退时手动：
```bash
ssh ubuntu@106.54.202.181 "
  cd ~/bdgo &&
  mv api api.broken.\$(date +%s) &&
  cp -a api.backup.1776536427 api &&
  sudo systemctl restart bdgo-api
"
```

或者 push 旧 commit：`git push vm <旧commit-sha>:main --force`（hook 自动部署旧版本）。

---

## 日后要不要加 Nginx？

当下不需要。加 nginx 的触发点：
- 要对外暴露 80/443 端口（隐藏 8000）
- 要给 API 加独立的 SSL 证书（不经 Vercel）
- 上线多后端 / 蓝绿部署 / 灰度路由
- CDN 前置静态资源

那时再装 nginx，用 `proxy_pass http://127.0.0.1:8000`、加上 `proxy_buffering off` + `X-Accel-Buffering: no` 给 SSE 路径即可。仓库里的 `nginx/default.conf` 已经写好了这套配置，可以直接用。
