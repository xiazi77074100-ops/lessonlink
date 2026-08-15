# 習い事管理くん (LessonLink)

日本の小規模な習い事・スポーツクラブ向け、LINEで完結する出欠管理SaaS。

- 詳しい仕様: [docs/product-requirements.md](docs/product-requirements.md)
- アーキテクチャ: [docs/architecture.md](docs/architecture.md)
- DB設計: [docs/database.md](docs/database.md)
- **今の進捗**: [TASKS.md](TASKS.md)（Phaseごとのチェックリスト。作業を再開するときは必ずここを見る）
- Claude Code向けの作業指針: [CLAUDE.md](CLAUDE.md)

## 構成

```
backend/           FastAPI + SQLAlchemy 2.x + Alembic + PostgreSQL
frontend-admin/    管理者ダッシュボード（React + Vite + TS + MUI）
frontend-parent/   保護者向け LINE Mini App（React + Vite + TS + LIFF）
docs/               仕様書
```

## クイックスタート（Docker）

```bash
git clone <this repo>
cd LessonLink
cp backend/.env.example backend/.env
cp frontend-admin/.env.example frontend-admin/.env
cp frontend-parent/.env.example frontend-parent/.env
docker compose up
```

- Backend API: http://localhost:8000/api/v1/health
- API Docs (Swagger): http://localhost:8000/docs
- Admin Dashboard: http://localhost:5173
- Parent App: http://localhost:5174

## ローカル開発（Dockerを使わない場合）

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt   # Windows
# source .venv/bin/activate && pip install -r requirements-dev.txt  # macOS/Linux

cp .env.example .env
# .env の DATABASE_URL がローカルのPostgreSQLを指すように設定する

.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m ruff check app tests
.venv/Scripts/uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend-admin   # または frontend-parent
npm install
cp .env.example .env
npm run dev
```

## LINE連携について

保護者向け機能（LINEログイン、出欠回答のLINE通知）を実際に動かすには、LINE Developers Console で以下を作成し `backend/.env` / `frontend-parent/.env` に設定する必要があります（開発の初期フェーズでは不要）:

- Provider
- Messaging API Channel（Channel ID / Secret / Access Token）
- LIFF App（LIFF ID）

詳細: [docs/product-requirements.md](docs/product-requirements.md) の 2.4節。

## 開発の進め方

このプロジェクトはPhase単位（[TASKS.md](TASKS.md) 参照）で段階的に開発しています。MVPスコープに含まれない機能は [docs/backlog.md](docs/backlog.md) にまとめてあり、勝手に実装しません。
