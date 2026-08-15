# Database Design — 習い事管理くん (LessonLink)

PostgreSQL / SQLAlchemy 2.x / Alembic。全テーブル共通: `id UUID PK (default gen_random_uuid())`, `created_at`, `updated_at`（timestamptz, UTC保存）。

## 共通Mixin

- `TimestampMixin`: created_at, updated_at
- `TenantMixin`: organization_id (FK, NOT NULL, indexed)
- `SoftDeleteMixin`: deleted_at (nullable) — organizations, admin_users, parents, children に適用

## 1. organizations

| column | type | note |
|---|---|---|
| id | uuid PK | |
| name | varchar(255) NOT NULL | |
| organization_type | varchar(50) NOT NULL | サッカー/野球/空手/ダンス/バレエ/ピアノ/スイミング/その他 |
| address | varchar(255) | |
| phone | varchar(30) | |
| email | varchar(255) | |
| plan | varchar(20) NOT NULL DEFAULT 'free' | free/basic/pro/business（将来課金用、ロジック未実装） |
| deleted_at | timestamptz | |
| created_at / updated_at | timestamptz | |

## 2. admin_users

| column | type | note |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK → organizations | |
| email | varchar(255) NOT NULL | unique (全体でunique。1メールは1組織にのみ所属を想定) |
| password_hash | varchar(255) NOT NULL | bcrypt |
| display_name | varchar(100) NOT NULL | |
| role | varchar(20) NOT NULL | OWNER / ADMIN / (将来STAFF) |
| deleted_at | timestamptz | |
| created_at / updated_at | timestamptz | |

Index: `(organization_id)`, unique `(email)`

## 3. parents

| column | type | note |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK → organizations | |
| line_user_id | varchar(64) NOT NULL | LINE ID Token検証後にサーバーが確定させる値 |
| display_name | varchar(100) NOT NULL | |
| email | varchar(255) | optional |
| phone | varchar(30) | optional |
| deleted_at | timestamptz | |
| created_at / updated_at | timestamptz | |

**Unique制約: `(organization_id, line_user_id)`**（グローバルではなくテナント単位。product-requirements.md 2.2参照）

## 4. children

| column | type | note |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK → organizations | |
| first_name / last_name | varchar(50) NOT NULL | |
| first_name_kana / last_name_kana | varchar(50) | |
| birth_date | date NOT NULL | 保護者紐付け時の本人確認に使用 |
| grade | varchar(20) | 自由入力（例: 小1, 年長） |
| status | varchar(20) NOT NULL DEFAULT 'ACTIVE' | ACTIVE / INACTIVE |
| deleted_at | timestamptz | |
| created_at / updated_at | timestamptz | |

Index: `(organization_id, status)`

## 5. parent_children（多対多）

| column | type | note |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK | 非正規化して直接テナントフィルタ可能にする |
| parent_id | uuid FK → parents | |
| child_id | uuid FK → children | |
| verified_at | timestamptz NOT NULL | 生年月日照合による本人確認が成立した日時 |
| created_at / updated_at | timestamptz | |

Unique制約: `(parent_id, child_id)`

## 6. events

| column | type | note |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK | |
| title | varchar(255) NOT NULL | |
| description | text | |
| start_at | timestamptz NOT NULL | UTC保存, 表示はAsia/Tokyo |
| end_at | timestamptz NOT NULL | |
| location_name | varchar(255) | |
| location_address | varchar(255) | |
| status | varchar(20) NOT NULL DEFAULT 'DRAFT' | DRAFT / PUBLISHED / CANCELLED / COMPLETED |
| created_at / updated_at | timestamptz | |

Index: `(organization_id, start_at)`, `(organization_id, status)`

## 7. attendances

| column | type | note |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK | |
| event_id | uuid FK → events | |
| child_id | uuid FK → children | |
| status | varchar(20) NOT NULL DEFAULT 'NO_RESPONSE' | ATTENDING / ABSENT / LATE / NO_RESPONSE |
| note | varchar(500) | |
| responded_by_parent_id | uuid FK → parents (nullable) | |
| responded_at | timestamptz (nullable) | |
| created_at / updated_at | timestamptz | |

**Unique制約: `(event_id, child_id)`**。イベント作成時に対象の全ACTIVE子供分を `NO_RESPONSE` で先に生成しておく（一覧取得と集計を単純化するため）。出欠登録APIはこの行への upsert として実装する。

## 8. invitations

| column | type | note |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK | |
| invitation_code | varchar(32) NOT NULL unique | URLセーフなランダム文字列 |
| expires_at | timestamptz | null許容=無期限 |
| max_uses | integer | null許容=無制限 |
| used_count | integer NOT NULL DEFAULT 0 | |
| status | varchar(20) NOT NULL DEFAULT 'ACTIVE' | ACTIVE / DISABLED / EXPIRED |
| created_by_admin_id | uuid FK → admin_users | |
| created_at / updated_at | timestamptz | |

## 9. notifications

| column | type | note |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK | |
| parent_id | uuid FK → parents | |
| type | varchar(30) NOT NULL | EVENT_CREATED / ATTENDANCE_REMINDER / EVENT_CANCELLED |
| channel | varchar(20) NOT NULL DEFAULT 'LINE' | LINE / EMAIL(将来) / PUSH(将来) |
| payload | jsonb | 送信内容のスナップショット |
| status | varchar(20) NOT NULL DEFAULT 'PENDING' | PENDING / SENT / FAILED |
| sent_at | timestamptz | |
| created_at / updated_at | timestamptz | |

## 10. audit_logs

| column | type | note |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK | |
| actor_type | varchar(20) NOT NULL | ADMIN / PARENT / SYSTEM |
| user_id | uuid (nullable) | admin_users.id または parents.id |
| action | varchar(50) NOT NULL | 下記参照 |
| resource_type | varchar(50) | |
| resource_id | uuid | |
| metadata | jsonb | |
| created_at | timestamptz | |

action の例:
`CREATE_EVENT, UPDATE_EVENT, CANCEL_EVENT, UPDATE_ATTENDANCE, SEND_REMINDER, ADD_PARENT, ADD_CHILD, PARENT_JOINED, CHILD_BOUND, CHILD_UNBOUND, ATTENDANCE_ANSWERED`

## ER図（概略）

```
organizations 1───* admin_users
organizations 1───* parents
organizations 1───* children
organizations 1───* events
organizations 1───* invitations
organizations 1───* notifications
organizations 1───* audit_logs

parents *───* children   (via parent_children, verified_at必須)
events  1───* attendances *───1 children
attendances *───1 parents (responded_by_parent_id, nullable)
```

## マイグレーション方針

Alembic で管理。Phase 2 で初期マイグレーション一式（上記全テーブル + index + unique constraint）を作成する。
