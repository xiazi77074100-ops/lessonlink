# CLAUDE.md

このリポジトリで作業するときは、まず以下を読むこと。

## 1. 進捗確認（最優先）

**`TASKS.md`** に現在のPhase進捗チェックリストがある。作業を始める前に必ず読み、「次にやること」セクションから再開する。Phaseやタスクが完了するたびに `TASKS.md` を更新してコミットすること（他PCでも進捗が分かるようにするための唯一の情報源）。

## 2. 仕様の正

- `要件.md` — ユーザーが最初に書いた要求プロンプト（中国語）。参考資料として保持するが、レビューにより一部変更されている。
- `docs/product-requirements.md` — **確定仕様**。`要件.md` と矛盾する場合はこちらを優先する。
- `docs/architecture.md` — システム構成、認証モデル、テナント分離方針。
- `docs/database.md` — 全テーブル定義、ER概略。
- `docs/backlog.md` — MVPで実装しないと決めた項目。ここにある内容は勝手に実装しない。

## 3. プロジェクト構成

```
backend/           FastAPI (async) + SQLAlchemy 2.x + Alembic + PostgreSQL
frontend-admin/    React + Vite + TS + MUI（管理者ダッシュボード、PC/タブレット優先）
frontend-parent/   React + Vite + TS（LINE LIFF Mini App、スマホ専用、1画面完結）
docs/               仕様書
TASKS.md            進捗トラッカー
```

## 4. 開発方針（要件.md 41〜50節より）

- Phaseごとに開発する。一度に全部作らない。
- 各Phase完了時: テスト実行 → TypeScript/lint確認 → ドキュメント更新 → `TASKS.md` 更新 → コミット → 何が完了し何が残っているか報告。
- MVPスコープ外の思いつきは実装せず `docs/backlog.md` に追記する。
- Simple > Feature Rich。Multi-tenant / Security first。over-engineeringしない。

## 5. コマンド

Backend:
```bash
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt   # 初回のみ
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m ruff check app tests
.venv/Scripts/uvicorn app.main:app --reload
```

Docker（Phase 1完了後）:
```bash
docker compose up
```

## 6. 注意点

- LINE連携（Phase 9以降）にはユーザーが LINE Developers Console で作成する Provider / Messaging API Channel / LIFF App の認証情報が必要。ローカルの `.env` にのみ設定し、コミットしない。
- テナント分離（`organization_id`）を無視したクエリを書かない。JWTに埋め込まれた `organization_id` のみを信用する。
