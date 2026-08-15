# Progress Tracker — 習い事管理くん (LessonLink)

このファイルが「今どこまで進んでいるか」の唯一の正とする。Phaseを進めるたびに更新し、コミットする。他のPCで `git pull` すればそのまま続きを把握できる。

進め方の原則は `要件.md` 41節（Phase順） / 45〜47節（各Phase完了時の報告義務）に従う。

## 全体ステータス

現在地: **Phase 12完了・AWS Lightsail一括デプロイスクリプト実装（AWS CLI認証・実行待ち）**

✅ **解決済み**: 開発機の `C:` ドライブが一時的に空き容量ほぼ0になっていた問題は、Windows Update キャッシュ削除・休止状態(hiberfil.sys)無効化・`docker system prune` で復旧(0 → 約7.4GB空き)。`docker compose up --build` でのフルスタック起動を確認済み(backend:8001, frontend-admin:5173, frontend-parent:5174, postgres:5433 — 5432/8000は別の既存プロジェクトのコンテナが使用中のためポートをずらした。詳細はdocker-compose.ymlのコメント参照)。

## Phase 0 — 要件レビュー & ドキュメント

- [x] 要件.md をレビューし、矛盾点・リスクを洗い出す
- [x] `docs/product-requirements.md` 作成（確定仕様、要件.mdからの変更点まとめ）
- [x] `docs/architecture.md` 作成
- [x] `docs/database.md` 作成（全テーブル定義）
- [x] `docs/backlog.md` 作成
- [x] git init、初回コミット

## Phase 1 — Project Setup

- [x] リポジトリ構成決定（backend / frontend-admin / frontend-parent）
- [x] Backend: FastAPI 最小構成（`app/main.py`, config, security, exceptions, db session, `/api/v1/health`）
- [x] Backend: pytest + ruff 動作確認（`backend/.venv` 作成済み、テストPASS）
- [x] Backend: Alembic 初期設定（マイグレーションはPhase 2で追加）
- [x] Backend: Dockerfile
- [x] Frontend-admin: Vite + React + TS + MUI 雛形(health check画面、build/lint確認済み)
- [x] Frontend-parent: Vite + React + TS 雛形（LIFF連携はPhase 9、health check画面のみ、build/lint確認済み）
- [x] docker-compose.yml（backend + postgres + frontend-admin + frontend-parent）
- [x] `.env.example`（backend/frontend-admin/frontend-parent）
- [x] CI（GitHub Actions: backend lint/test, frontend build/lint）
- [x] README.md（起動手順）
- [x] `docker-compose.yml` の構文検証（`docker compose config` はOK）。実際の `docker compose up` はこのマシンでDocker Desktopが起動しておらず未確認 → 次にDocker Desktopを起動した状態で再確認すること
- [x] Phase 1 完了コミット & 報告

## Phase 2 — Database

- [x] SQLAlchemy モデル実装（organizations, admin_users, parents, children, parent_children, events, attendances, invitations, notifications, audit_logs）— `backend/app/models/`
- [x] Alembic 初期マイグレーション生成・適用確認（`8b06229b4124_initial_schema.py`、`alembic upgrade head` で全10テーブル作成確認済み）
- [x] Seed script（`backend/app/scripts/seed.py`）— 組織1・管理者1(admin@example.com/password123)・子供20・保護者15・parent_children紐付け20・活動5・出欠100件、実行確認済み
- [x] Index / Unique制約の実機確認（psqlで `uq_attendances_event_child` 等のUNIQUE/CHECK制約を確認）
- [x] 副産物の修正: `passlib` が新しい `bcrypt`(5.0.0)と非互換だったため、`bcrypt` ライブラリを直接使う方式に変更(`app/core/security.py`)

## Phase 3 — Admin Authentication

- [x] `POST /api/v1/auth/login`（email+password, bcrypt検証, JWT発行）
- [x] `GET /api/v1/me`
- [x] 認可ミドルウェア（JWT検証 → current_user注入）
- [x] Admin frontend: ログイン画面

## Phase 4 — Organization

- [x] 組織作成・取得・更新 API
- [x] Admin frontend: 組織作成/設定画面

## Phase 5 — Child / Parent

- [x] 子供 CRUD API
- [x] 保護者一覧・詳細 API
- [x] parent_children 紐付けAPI（管理者操作。保護者本人の生年月日照合はPhase 9）
- [x] Admin frontend: 子供一覧・登録画面

## Phase 6 — Event

- [x] 活動 CRUD + キャンセル API
- [x] Admin frontend: 活動一覧・作成・詳細/編集画面

## Phase 7 — Attendance

- [x] 出欠 upsert API（冪等性、architecture.md 6節）
- [x] 集計API（参加/欠席/遅刻/未回答カウント）
- [x] Admin frontend: 活動別ダッシュボード集計表示

## Phase 8 — Invitation

- [x] 招待コード発行API + QRコード生成
- [x] 招待コード検証・期限/上限チェック・原子的消費サービス（LINE本人確認との接続はPhase 9）
- [x] Admin frontend: 招待QR発行画面

## Phase 9 — LINE

- [ ] ⚠️ ユーザー側でLINE Developers Provider / Messaging API Channel / LIFF App を作成し `.env` に設定（Claude Codeでは代行不可）
- [x] LIFF ID Token検証（公式verify API、サーバー側でline_user_id確定。実機検証待ち）
- [x] Parent frontend: LINEログイン → 子供選択 → 生年月日照合 → 紐付け
- [x] Parent frontend: 出欠回答画面（1画面、10秒以内）

## Phase 10 — Notification

- [x] LineNotificationChannel 実装（Messaging API呼び出し、実機検証待ち）
- [x] 「未回答者に通知」API（parent_id単位で統合、product-requirements.md 2.5）
- [x] notifications テーブルへの送信ログ記録

## Phase 11 — Testing

- [x] Unit test一式
- [x] API test一式（PostgreSQL実DBテストをCIにも追加）
- [x] テナント分離テスト（要件.md 36節 Test1-6）
- [x] API E2E（要件.md 37節のHappy Path、LINE送信のみmock）

## Phase 12 — UX Polish

- [x] Loading / Empty / Error / Success / Disabled / Permission denied 状態確認
- [x] モバイルUI対応（レスポンシブ実装・ビルド確認。LIFF実機表示は公開HTTPS準備後）
- [x] 日本語UI最終チェック

---

## 次にやること

1. AWS CLIをインストール・認証し、`deploy/aws-lightsail.ps1` でLightsail作成から公開まで実行
2. LINE DevelopersのLIFF Endpoint URLを公開URLへ変更
3. 実機でLIFFログイン・招待参加・出欠回答・通知を確認
