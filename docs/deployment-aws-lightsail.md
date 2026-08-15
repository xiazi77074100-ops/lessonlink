# AWS Lightsail 本番デプロイ

MVP検証では、Lightsail の Linux インスタンス1台に Caddy、2つのフロントエンド、
FastAPI、PostgreSQLを Docker Compose で配置する。CaddyがTLS証明書を自動取得・更新する。

## 料金と構成

- リージョン: Asia Pacific (Tokyo)
- OS: Ubuntu 24.04 LTS
- 最小構成: 1 GB RAM。メモリ不足の場合は2 GBへ変更する
- 開放ポート: SSH (22、自分のIPのみ)、HTTP (80)、HTTPS (443)
- DBも同居するため単一障害点になる。MVP検証後は自動スナップショットまたはRDSを検討する

## 1. Lightsailを準備

1. Lightsailコンソールで東京リージョンに Linux/Unix の Ubuntu インスタンスを作成する。
2. Static IPを作成してインスタンスへ割り当てる。
3. 独自ドメインのAレコードをStatic IPへ向ける。
4. NetworkingでTCP 80/443を許可し、SSH 22の送信元を自分のIPに制限する。

独自ドメインをまだ用意しない短期テストでは、Static IPが `203.0.113.10` なら
`203-0-113-10.sslip.io` のようなIP連動ホスト名も利用できる。ただし外部サービス依存のため、
継続運用には独自ドメインを推奨する。

## 2. サーバーへ配置

SSH接続後にDocker EngineとCompose plugin、Gitをインストールし、リポジトリをcloneする。
Ubuntu公式パッケージを使う場合の例:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2 git
sudo usermod -aG docker "$USER"
```

いったんログアウトして再接続した後:

```bash
git clone <repository-url> LessonLink
cd LessonLink
cp .env.production.example .env.production
chmod 600 .env.production
```

`.env.production` にドメイン、ランダムなDB/JWTシークレット、LINEの認証情報を設定する。
このファイルはGit管理しない。

ランダム値は次のように生成できる:

```bash
openssl rand -hex 32
```

## 3. 起動

```bash
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
docker compose --env-file .env.production -f docker-compose.production.yml ps
docker compose --env-file .env.production -f docker-compose.production.yml logs --tail=100
```

Caddyがドメインを確認できれば、自動的にHTTPSが有効になる。

- Admin: `https://<DOMAIN>/`
- Parent LIFF: `https://<DOMAIN>/parent/`
- API health: `https://<DOMAIN>/api/v1/health`

## 4. LINE Developersを更新

LINE Login ChannelのLIFF設定で Endpoint URLを `https://<DOMAIN>/parent/` にする。
Scopeは `openid` と `profile` を有効にし、LIFF Appを公開する。その後、スマートフォンの
LINEからLIFF URLを開き、招待参加、子供紐付け、出欠回答、通知を順に確認する。

## 5. 更新とバックアップ

```bash
git pull --ff-only
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
```

データを保護するため、実利用開始前にLightsailの自動スナップショットを有効にする。
さらに定期的な `pg_dump` を別ストレージへ保存する。
