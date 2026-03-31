# line-template.top Status (Deep Audit) — 2026-03-21

対象:
- projectId: `proj-184-line-template-top`
- rootDir: `/var/www/line-template.top`
- domain: `https://line-template.top`

---

## 1) 実ディレクトリ監査（確認済み）

主要構成:
- `api/` FastAPI API サービス
- `ui/` FastAPI + Jinja2 UI サービス
- `assets/` 静的素材
- `public/` 公開静的トップ
- `ops/` デプロイ/サービス雛形
- `.env` / `.env.example`

補足:
- Python venv が `api/.venv`, `ui/.venv` に存在
- Node構成（package.json）は確認できず、Python中心構成

---

## 2) 主要ファイル内容の確認結果

### 2-1 API
- `api/requirements.txt`
  - `fastapi`, `uvicorn`, `SQLAlchemy`, `pymysql`, `httpx`, `python-jose`, `passlib` など
- `api/app/main.py`
  - FastAPI本体（大規模）
  - CORS全許可
  - JWT処理
  - LINE push API連携
  - onboarding/survey関連ロジック
  - DB連携（models/database/config/schemas）

### 2-2 UI
- `ui/requirements.txt`
  - `fastapi`, `uvicorn`, `jinja2`, `python-dotenv`
- `ui/app/main.py`
  - `line-platform-ui` FastAPIアプリ
  - `/` テンプレート描画
  - `/health` ヘルス

### 2-3 OPS
- `ops/README_DEPLOY.md`
  - Nginx vhost と SSL配置先
  - 予約ポート:
    - UI: `127.0.0.1:3101`
    - API: `127.0.0.1:8101`
  - ヘルスURL定義（line.sns-template.com / api.sns-template.com）

### 2-4 環境変数
- `.env.example`
  - DB接続定義
  - LINE channel 1〜3
  - LINE Login callback
  - Webhook base URL

---

## 3) 現在の運用上の論点

1. `ops/README_DEPLOY.md` は `line-platform` 名義で記載があり、
   実ディレクトリ `line-template.top` と名称差分あり（混乱要因）
2. APIが大規模単一ファイル傾向（`api/app/main.py`）
   - 機能分割（routes/services）で保守性向上余地
3. docs運用ファイルが未整備（進捗/報告標準/障害対応）

---

## 4) 推奨ドキュメント整備（次ステップ）

優先順:
1. `docs/PROJECT_PROGRESS.md`
2. `docs/REPORTING_STANDARD.md`
3. `docs/OPS_NOTES.md`（実運用コマンド/systemd/nginx整合）
4. `docs/SECURITY_NOTES.md`（機密値、権限、公開範囲）

---

## 5) 互換/整合ルール（提案）

- 名称は `line-template.top` に統一（line-platform表記は注釈付き）
- API/UIの起動ポートは docs と env を一致させる
- 変更報告は日次で `docs/REPORTS/` へ蓄積

---

## 6) 監査サマリ

- 構成確認: 完了
- 主要依存確認: 完了
- デプロイ情報確認: 完了
- docs整備: 未完（これから）

---

作成メモ:
- これは「薄い概要」ではなく、実ファイル内容に基づく深掘り版スナップショット。
