# Architecture — 習い事管理くん (LessonLink)

## 1. 全体構成

```
                     ┌─────────────────────────┐
                     │   Admin Web Dashboard    │
                     │  React + Vite + TS + MUI │
                     │  (frontend-admin/)       │
                     └────────────┬─────────────┘
                                  │ HTTPS / JWT (Bearer)
                                  ▼
┌───────────────────────────────────────────────────────┐
│                  FastAPI Backend (backend/)             │
│  /api/v1/...  REST + OpenAPI                             │
│  - Auth (admin: email/password, parent: LINE)            │
│  - Organizations / Children / Parents / Events            │
│  - Attendance / Invitations / Notifications / Audit Log   │
└───────────────────────────┬─────────────────────────────┘
              │ SQLAlchemy 2.x (async) + Alembic
              ▼
     ┌─────────────────┐        ┌──────────────────────┐
     │   PostgreSQL     │        │  LINE Platform         │
     │                  │        │  - LIFF (Login/UI)     │
     └─────────────────┘        │  - Messaging API (Push)│
                                  └───────────┬────────────┘
                                              │ HTTPS / LIFF SDK
                                  ┌───────────▼────────────┐
                                  │  Parent LIFF Mini App    │
                                  │  React + Vite + TS       │
                                  │  (frontend-parent/)      │
                                  └──────────────────────────┘
```

二つのフロントエンドは意図的に別プロジェクトとして分離する（Admin=PC/タブレット中心の管理画面、Parent=LIFF内で動く軽量1画面アプリ、という要求特性が全く異なるため）。共通コンポーネントが増えてきたら `packages/ui` として切り出すが、MVP時点では過剰設計を避けるために行わない。

## 2. 認証モデル

### 2.1 Admin（管理者）
- Email + Password によるログイン (`POST /api/v1/auth/login`)
- Password は bcrypt でハッシュ化して保存
- ログイン成功時、`organization_id`, `role`, `admin_user_id` を含む JWT を発行（access token、有効期限短め + refresh token 方針は Phase 3 で確定）
- 全APIは `Authorization: Bearer <token>` を要求し、ミドルウェアで検証したうえで `current_user` をリクエストコンテキストに注入する

### 2.2 Parent（保護者）
- パスワードを持たない。LIFF SDK 経由で LINE の ID Token を取得し、バックエンドに送信
- バックエンドは LINE の公開鍵で ID Token を検証し、`line_user_id` をサーバー側で確定させる（フロントから渡された `line_user_id` は一切信用しない）
- 検証済みの `line_user_id` を元に `(organization_id, line_user_id)` で `parents` を検索/作成し、独自の短命JWT（parent session）を発行して以降のMini App内APIに使う

## 3. テナント分離の実装方針

- すべてのビジネステーブルは `organization_id` を持つ
- リポジトリ/クエリ層は必ず `WHERE organization_id = :current_org_id` を付与するヘルパー経由でのみアクセスする（生クエリでの直書きを避ける）
- URLパスやリクエストボディに含まれる `organization_id` は信用せず、JWTに埋め込まれた `organization_id` のみを権限判定に使う
- テナント分離は Phase 11 で自動テスト必須項目とする（Organization Aのトークンで Organization Bのリソースにアクセス→ 403/404）

## 4. モジュール構成（backend/）

```
backend/
  app/
    core/          # 設定, security(hash/jwt), exceptions, logging
    db/             # session, base model, mixins (TenantMixin, TimestampMixin, SoftDeleteMixin)
    models/          # SQLAlchemy ORM models
    schemas/         # Pydantic request/response models
    api/
      v1/
        auth.py
        organizations.py
        children.py
        parents.py
        events.py
        attendance.py
        invitations.py
        notifications.py
    services/         # ビジネスロジック（Auth, Attendance, Invitation, Notification, LineClient）
    repositories/     # DBアクセス（テナントスコープ強制）
  alembic/
  tests/
```

## 5. 通知（Notification）抽象

```python
class NotificationChannel(Protocol):
    async def send(self, parent: Parent, message: NotificationMessage) -> None: ...

class LineNotificationChannel(NotificationChannel): ...   # MVPで実装
class EmailNotificationChannel(NotificationChannel): ...  # 将来
```

`notifications` テーブルには送信ログを残す（type, channel, parent_id, payload, status, sent_at）。リマインドは parent_id 単位で未回答の (child, event) をまとめて1メッセージに集約してから `NotificationChannel.send` を呼ぶ。

## 6. 冪等性

- `POST /api/v1/attendance` は `(event_id, child_id)` の一意制約に対して upsert（`ON CONFLICT DO UPDATE`）で実装し、連打しても行が増えない
- キャンセル済み (`CANCELLED`) イベントへの出欠更新はAPI層で拒否する

## 7. エラーハンドリング

FastAPI の例外ハンドラで全ての例外を捕捉し、統一フォーマットで返す:

```json
{ "error": { "code": "EVENT_NOT_FOUND", "message": "活動が見つかりません。" } }
```

内部例外はログにスタックトレースを出力し、クライアントには汎用メッセージのみ返す。

## 8. デプロイ（MVP時点）

- ローカル/検証: `docker compose up`（frontend-admin, frontend-parent, backend, postgres）
- 本番想定: Frontend → 静的ホスティング（Vercel等） / Backend → コンテナホスティング（Azure Container Apps等） / DB → マネージドPostgreSQL
- Redis は導入しない（キャッシュ・レート制限は当面アプリ内メモリ実装で十分な規模）

## 9. CI（Phase 1で最小構成）

GitHub Actions で以下を実行:
- backend: ruff (lint) + mypy(任意) + pytest
- frontend-admin / frontend-parent: tsc --noEmit + eslint + build
