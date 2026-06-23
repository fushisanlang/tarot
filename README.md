# 知我 — 在线塔罗占卜

AI 驱动的塔罗占卜网站。78 张韦特塔罗、13+ 种牌阵、DeepSeek 流式解读。

## 技术栈

- **后端** — Flask + SQLAlchemy + gunicorn
- **AI** — DeepSeek Chat (OpenAI SDK, stream)
- **前端** — 原生 HTML/CSS/JS，Anti-Slop 暗色主题
- **数据库** — MySQL 8.4
- **缓存/限频** — Redis 7
- **部署** — Docker Compose

## 快速开始

### 1. 配置环境变量

```bash
cp .env.example .env
# 填写你的密钥
```

环境变量 | 说明 | 默认值
---|---|---
`DEEPSEEK_API_KEY` | DeepSeek API 密钥 | —
`MYSQL_ROOT_PASSWORD` | MySQL root 密码 | —
`DB_PASSWORD` | MySQL tarot 用户密码 | tarot_pw_2026
`REDIS_PASSWORD` | Redis 密码 | tarot_redis_pw_2026

### 2. Docker 部署

```bash
docker build . -t tarot-backend
docker compose up -d
```

访问 http://localhost:5002

### 3. 本地开发（直接连远程 MySQL/Redis）

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 先改 config.py 里的远程 MySQL/Redis 地址
# DB_HOST 和 REDIS_HOST 填远程服务器 IP

flask run
```

## 牌阵

内置 13+ 种牌阵：

- 三张牌阵（过去/现在/未来）
- 凯尔特十字（10 张大阵）
- 关系牌阵
- 事业指引
- 财运分析
- 灵性成长
- …

牌阵定义在 `data/tarot-data.json` 中，可自由扩展。

## 项目结构

```
tarot/
├── docker-compose.yml          # 三容器编排
├── Dockerfile                  # 纯 pip 构建
├── .env.example                # 环境变量模板
│
├── tarot/
│   ├── app.py                  # Flask 入口，自动建表
│   ├── config.py               # 配置（MySQL/Redis/限频）
│   ├── models.py               # ORM 模型
│   ├── routes.py               # API + SSE 流式输出
│   ├── tarot_engine.py         # Fisher-Yates 抽牌引擎
│   └── ai_reader.py            # DeepSeek 调用 + 提示词模板
│
├── static/
│   ├── index.html              # 前端单页
│   ├── style.css               # Anti-Slop 暗色主题
│   ├── app.js                  # SSE 流式读取 + 卡牌渲染
│   ├── card_images.json        # 牌编号 → 图片文件映射
│   └── cards/                  # 78 张韦特塔罗图
│
└── data/
    └── tarot-data.json         # 78 张牌数据 + 牌阵定义
```

## 部署架构

```
┌───────────────┐     ┌───────────────┐
│  tarot-front  │────→│  tarot-api    │
│  (浏览器)     │ SSE │  gunicorn:5002 │
└───────────────┘     └───┬───┬───────┘
                          │   │
                    ┌─────┘   └──────┐
                    ▼                ▼
              MySQL 8.4           Redis 7
              持久化数据            限频缓存
```

## 限频策略

- 每 IP 每天免费 N 次（默认 10，由 `DAILY_LIMIT` 控制）
- 主防：Redis `INCR + EXPIRE`
- 兜底：MySQL `rate_limits` 表

## License

MIT
