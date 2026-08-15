# Product Requirements — 習い事管理くん (LessonLink)

本ドキュメントは `要件.md` を正式仕様として整理し、レビューで確定した曖昧点の解決方針を追記したものです。矛盾が生じた場合は本ドキュメントを正とします。

## 1. プロダクト概要

- 対象: 日本の小規模な子供向け習い事・スポーツクラブ（10〜100名規模）
- 種別: B2B2C SaaS
  - Admin（クラブ管理者）: Web Dashboard（PC/タブレット優先、スマホでも動作）
  - Parent（保護者）: LINE Mini App（LIFF ベース、スマホ専用）
- コアループ:
  管理者が組織作成 → 子供登録 → 活動作成 → 招待QR発行 → 保護者がLINEで参加 → 子供を紐付け →
  出欠回答（10秒以内） → 管理者がダッシュボードで集計確認 → 未回答者へLINEリマインド

## 2. スコープ確定方針（要件.mdからの変更点）

組織向けAdminと保護者向けLIFFの最終的な情報設計、招待・通知フロー、Phase 13以降の
UX受入条件は [`ux-product-design.md`](ux-product-design.md) を正とする。

要件.md に対して、以下の点をレビューで確定し、デフォルト方針として採用する（ユーザー確認済み）。

### 2.1 子供の紐付けにおける本人確認（重要・セキュリティ）

要件.md 18節の「名簿から子供をチェックするだけ」の方式は、招待QRを持つ誰でも他家庭の子供名を選んで紐付けできてしまう認可バグになる。

**確定仕様:**
- 招待経由で参加した保護者は、名簿から子供を選択した後、その子供の **生年月日** を入力する。
- サーバー側で `children.birth_date` と一致するか検証し、一致した場合のみ `parent_children` を作成する。
- 紐付けの成功/失敗、および紐付け解除は `audit_logs` に記録する（`CHILD_BOUND`, `CHILD_UNBOUND`）。
- 管理者ダッシュボードから紐付け一覧を確認し、誤紐付けを解除できる。

### 2.2 LINEユーザーの一意性はテナント単位

要件.md 6節の「line_user_id はシステム内で一意」は、同じ保護者が複数の教室（例: サッカー＋水泳）に子供を通わせる実際の利用シーンと矛盾する。

**確定仕様:** `parents` テーブルの一意制約は `(organization_id, line_user_id)` の複合一意とする。同一 LINE ユーザーが複数組織にまたがって別々の Parent レコードを持てる。

### 2.3 「Push Notification 禁止」の解釈

要件.md 30節の禁止リストにある「Push Notification」は **ネイティブアプリのプッシュ通知（APNs/FCM）** を指し、LINEメッセージ通知（15, 16節で要求されている中核機能）は対象外とする。LINE通知はMVPスコープ内。

### 2.4 LINE通知の外部前提条件

出欠リマインドをLINEで実際に送信するには、LINE Developers Console 上で以下をユーザー側で用意する必要がある（Claude Codeでは作成不可）:
- Provider
- Messaging API Channel（Channel ID / Channel Secret / Channel Access Token）
- LIFF App（LIFF ID）

Phase 9（LINE統合）に着手する前にユーザーが取得し `.env` に設定する。それまでの開発・テストは LINE Client のモック実装で進める。

### 2.5 リマインド統合ルール

`POST /api/v1/events/{id}/remind` は `parent_id` 単位でグルーピングし、その保護者が抱える「未回答の (子供×活動) の組み合わせ」を1通のLINEメッセージにまとめて送信する。子供・活動ごとに個別送信はしない。

### 2.6 タイムゾーン

すべての日時は DB には UTC で保存し、表示は Asia/Tokyo に変換する。

### 2.7 将来課金への準備

`organizations.plan` カラム（`free` / `basic` / `pro` / `business`、デフォルト `free`）を追加する。課金ロジック自体はMVPで実装しない。

### 2.8 監査ログの対象拡大

Admin操作に加え、保護者側のイベントも記録する: `PARENT_JOINED`, `CHILD_BOUND`, `CHILD_UNBOUND`, `ATTENDANCE_ANSWERED`。

### 2.9 ソフトデリート

`organizations`, `admin_users`, `parents`, `children` に `deleted_at` を用意する（将来の退会/削除機能のため）。MVPでは削除UIは実装しないが、スキーマは対応させる。

## 3. ロール

| ロール | 権限 |
|---|---|
| OWNER | 組織管理、管理者管理、保護者/子供管理、活動作成、出欠閲覧、リマインド送信 |
| ADMIN | 管理者管理を除き OWNER と同等 |
| STAFF（将来） | 出欠閲覧・活動閲覧のみを想定。DB設計はロール拡張を許容する形にする |

## 4. MVPに含まれないもの（要件.md 30節を継承）

オンライン決済 / 月謝管理 / Stripe / チャット / アルバム / ファイル管理 / GPS・送迎最適化 / 地図 / AI / OCR / Google・Appleログイン / 多言語 / 複雑なレポート / Excel入出力 / ネイティブPush通知 / ポイント / クーポン / 広告 / 定期イベント繰り返し

新たに気づいた「将来的にやりたくなりそうな機能」は `docs/backlog.md` に追記し、その場で実装しない。

## 5. Definition of Done（要件.md 47節を機能単位で適用）

- Backend実装 / Frontend実装 / DBマイグレーション / バリデーション / 認可 / テナント分離確認 / エラーハンドリング / Unitテスト / APIテスト / ドキュメント更新 / 日本語UI確認 / モバイルUI確認

## 6. 最重要 E2E（変更後）

```
Admin登録 → 組織作成 → 子供20人登録 → 活動作成 → 招待QR発行
  ↓
Parent: QRスキャン → LINEログイン → 子供選択 → 生年月日で本人確認 → 紐付け成立
  ↓
Parent: 活動を確認 → 「参加」をタップ → 即保存・完了表示
  ↓
Admin: ダッシュボードで集計確認 → 「未回答者に通知」→ 未回答保護者へ統合LINEメッセージ送信
```
