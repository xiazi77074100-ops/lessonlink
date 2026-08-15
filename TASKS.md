# Progress Tracker — 習い事管理くん (LessonLink)

このファイルが「今どこまで進んでいるか」の唯一の正とする。Phaseを進めるたびに更新し、コミットする。他のPCで `git pull` すればそのまま続きを把握できる。

進め方の原則は `要件.md` 41節（Phase順） / 45〜47節（各Phase完了時の報告義務）に従う。

## 全体ステータス

現在地: **Phase 1（Project Setup）完了 → Phase 2（Database）へ**

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

- [ ] SQLAlchemy モデル実装（organizations, admin_users, parents, children, parent_children, events, attendances, invitations, notifications, audit_logs）
- [ ] Alembic 初期マイグレーション生成・適用確認
- [ ] Seed script（`docs/database.md` 相当のダミーデータ、要件.md 38節: 組織1・管理者1・子供20・保護者15・活動5）
- [ ] Index / Unique制約の実機確認

## Phase 3 — Admin Authentication

- [ ] `POST /api/v1/auth/login`（email+password, bcrypt検証, JWT発行）
- [ ] `GET /api/v1/me`
- [ ] 認可ミドルウェア（JWT検証 → current_user注入）
- [ ] Admin frontend: ログイン画面

## Phase 4 — Organization

- [ ] 組織作成・取得・更新 API
- [ ] Admin frontend: 組織作成/設定画面

## Phase 5 — Child / Parent

- [ ] 子供 CRUD API
- [ ] 保護者一覧・詳細 API
- [ ] parent_children 紐付けAPI（生年月日照合ロジック含む、product-requirements.md 2.1）
- [ ] Admin frontend: 子供一覧・登録画面

## Phase 6 — Event

- [ ] 活動 CRUD + キャンセル API
- [ ] Admin frontend: 活動一覧・作成・詳細画面

## Phase 7 — Attendance

- [ ] 出欠 upsert API（冪等性、architecture.md 6節）
- [ ] 集計API（参加/欠席/遅刻/未回答カウント）
- [ ] Admin frontend: ダッシュボード集計表示

## Phase 8 — Invitation

- [ ] 招待コード発行API + QRコード生成
- [ ] 招待経由の保護者参加フロー（コード検証、期限/上限チェック）
- [ ] Admin frontend: 招待QR発行画面

## Phase 9 — LINE

- [ ] ⚠️ ユーザー側でLINE Developers Provider / Messaging API Channel / LIFF App を作成し `.env` に設定（Claude Codeでは代行不可）
- [ ] LIFF ID Token検証（サーバー側でline_user_id確定）
- [ ] Parent frontend: LINEログイン → 子供選択 → 生年月日照合 → 紐付け
- [ ] Parent frontend: 出欠回答画面（1画面、10秒以内）

## Phase 10 — Notification

- [ ] LineNotificationChannel 実装（Messaging API呼び出し）
- [ ] 「未回答者に通知」API（parent_id単位で統合、product-requirements.md 2.5）
- [ ] notifications テーブルへの送信ログ記録

## Phase 11 — Testing

- [ ] Unit test一式
- [ ] API test一式
- [ ] テナント分離テスト（要件.md 36節 Test1-6）
- [ ] E2E（要件.md 37節のHappy Path）

## Phase 12 — UX Polish

- [ ] Loading / Empty / Error / Success / Disabled / Permission denied 状態確認
- [ ] モバイルUI確認
- [ ] 日本語UI最終チェック

---

## 次にやること

1. （任意）Docker Desktopを起動した状態で `docker compose up` の実機確認
2. Phase 2着手: `backend/app/models/` にSQLAlchemyモデルを実装（`docs/database.md` の全テーブル）
3. Alembic初期マイグレーション生成・適用
4. Seedスクリプト作成
