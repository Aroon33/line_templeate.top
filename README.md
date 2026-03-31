# line-template.top システムREADME

最終更新: 2026-03-21
対象サーバー: `160.251.239.184`（184）
プロジェクトルート: `/var/www/line-template.top`

---

## 1) このシステムは何か

`line-template.top` は、**LINE連携系テンプレート（API + UI）**の構成です。

主な構成:
- `api/`（Python API）
- `ui/`（Python UIアプリ）
- `public/`（公開トップ）
- `ops/`（デプロイ/サービス定義テンプレ）

---

## 2) ディレクトリ構成

- `api/`
  - `app/main.py`, `app/models.py`, `app/database.py` など
  - `requirements.txt`, `.venv/`
- `ui/`
  - `app/main.py`, `templates/index.html`
  - `requirements.txt`, `.venv/`
- `ops/`
  - `README_DEPLOY.md`
  - `line-platform-api.service.example`
  - `line-platform-ui.service.example`
  - `ssl_setup.sh`
- `assets/`, `public/`

---

## 3) デプロイ情報（既存メモ由来）

`ops/README_DEPLOY.md` には以下の参考情報あり:
- 予約ポート例: UI `127.0.0.1:3101`, API `127.0.0.1:8101`
- nginx/service テンプレ運用
- API/UI未起動時は 502 になる

※ 一部パス/ドメイン表記は旧名称（`line-platform`, `sns-template.com`）のため、
実運用時は `line-template.top` 向けに統一すること。

---

## 4) 初期確認コマンド

```bash
# 全体
ls -la /var/www/line-template.top

# API/UI
ls -la /var/www/line-template.top/api
ls -la /var/www/line-template.top/ui

# deploy notes
cat /var/www/line-template.top/ops/README_DEPLOY.md
```

---

## 5) 運用前チェック

1. `.env` の機密値確認
2. API/UI の起動手順確定
3. systemdユニット化
4. nginxリバースプロキシ設定
5. `https://<domain>` と APIヘルスチェック確認

---

## 6) 障害時初動

1. API/UIプロセス生存確認
2. nginx設定テスト (`nginx -t`)
3. 502時は upstream（API/UI）から調査
4. 復旧後、ops配下に手順を追記

---

## 7) 重要追加仕様（マルチ公式LINE対応 / ズレ防止）

### 7-1. 前提
- 1ユーザーが複数のLINE公式アカウントに登録する可能性がある
- LINE仕様上、**同じ人でも公式LINEごとに `line_user_id` は別**

### 7-2. 正しいデータ設計

#### users（人としての統一）
- `id`
- `email`
- `password`
- `created_at`

役割: 人間の本体を1件に統合管理

#### accounts（公式LINE）
- `id`
- `name`
- `channel_id`
- `channel_secret`
- `access_token`

役割: 公式LINEアカウント単位の管理

#### user_line_accounts（中間テーブル / 必須）
- `id`
- `user_id`（内部ユーザーID）
- `account_id`（公式LINEアカウントID）
- `line_user_id`（その公式LINEでのユーザーID）
- `created_at`

役割: 「1人のユーザー」×「複数公式LINE」の対応表を正しく保持する

### 7-3. 識別ルール（必須）
- ユーザー特定は **`account_id + line_user_id` の組み合わせ**で行う
- `line_user_id` 単体でのユーザー特定は禁止

### 7-4. Webhook処理フロー（必須）
1. Webhook受信
2. 受信先 `account_id` を特定
3. イベント内 `line_user_id` を取得
4. `user_line_accounts` を `account_id + line_user_id` で検索
5. `user_id` を解決
6. 業務処理実行

### 7-5. 返信ルール（必須）
- 返信は**受信した `account_id` の公式LINEからのみ**送信する
- 他の公式LINEアカウントからの返信は禁止

### 7-6. NG事項（禁止）
- `users` に `line_user_id` を直接1つだけ保持する設計
- `account_id` を無視してユーザー特定する処理
- Aアカウントで受信しBアカウントから返信するクロス送信

### 7-7. 最終的な完成形
- ユーザーは内部で1件に統合
- 外部LINE IDはアカウント単位で分離
- 会話はアカウントごとに独立
- 内部集計・分析はユーザー単位で統合


---

## 8) OPENCLAW追加要件（3公式LINEシナリオ設計）

### 8-1. 前提（運用アカウント）
- 副業LINE
- 不動産LINE
- AIマネジメントLINE

### 8-2. 共通ゴール（全LINE共通）
1. 登録
2. アンケート取得
3. 会員登録（LINEログイン or フォーム）
4. ユーザー情報DB保存
5. フロント商品誘導 または 目的別導線へ分岐

### 8-3. 初期フロー（全LINE共通）
登録直後に以下を必ず実施する:
1. あいさつメッセージ送信
2. アンケート誘導
3. 回答後に会員登録誘導

### 8-4. アンケート仕様（必須）
最低取得項目:
- 名前
- 年齢層
- 性別
- 興味（分岐キー）
- 現状（悩み）

保存先:
- `user_profiles` テーブル

### 8-5. 会員登録仕様（重要）
登録方法:
- LINEログイン（推奨）
- またはフォーム入力

紐付けルール:
- 内部 `user_id` に統合
- かつ `account_id` 単位で保持

### 8-6. LINE別シナリオ

#### 8-6-1. 副業LINE（教育→フロント販売）
目的:
- 教育後、低単価フロント商品（500〜1000円）へ誘導

フロー:
登録 → アンケート → 教育メッセージ配信 → フロント商品提示

商品例:
- ノウハウPDF
- 動画講座
- コミュニティ参加

#### 8-6-2. AIマネジメントLINE（NOTE/コンテンツ販売）
目的:
- AI活用教育後、NOTEまたはコンテンツ販売

フロー:
登録 → アンケート → AI活用教育 → NOTE誘導

分岐:
- 初心者: 基礎NOTE
- 経験者: 応用NOTE

#### 8-6-3. 不動産LINE（売却見込み獲得 / 最重要）
目的:
- 売却見込みユーザーの抽出と案件化

フロー:
登録 → 不動産アンケート → 売却意欲判定 → 高温抽出 → 個別対応/案件化

追加アンケート項目（不動産）:
- 物件種別
- エリア
- 売却予定時期
- 査定希望
- ローン残債

ステータス:
- 今すぐ売却: `HOT`
- 検討中: `WARM`
- 情報収集: `COLD`

### 8-7. DB追加設計（必須）

#### user_profiles
- `user_id`
- `account_id`
- `name`
- `age`
- `interest`
- `answers` (JSON)

#### user_status
- `user_id`
- `account_id`
- `status` (`HOT` / `WARM` / `COLD` / etc)

### 8-8. 自動返信ロジック
処理キー:
- `(user_id + account_id)`

ルール:
- アンケート未回答: 再促進メッセージ
- 回答済み: 次ステップ導線へ進行
- ステータス別: 配信文面と提案内容を出し分け

### 8-9. UI要件（必須）
- LINE別ユーザー一覧
- ステータス色分け表示
- アンケート内容表示
- 会話履歴表示

### 8-10. NG事項
- LINEごとに別ユーザーとして内部管理する
- アンケート未設計のまま導線運用を開始する
- ステータス管理なしで運用する

### 8-11. 最終ゴール
ユーザー登録
→ アンケート取得
→ 会員登録
→ DB統合
→ LINE別最適導線
→ 収益化 or リード獲得

### 8-12. 実務メモ（成功要因）
- 成功の鍵はアンケート設計
- 分岐質問の品質が成約率を左右する


---

## 9) 副業LINE シナリオ仕様

### 9-1. 目的
副業初心者ユーザーに教育を行い、低単価フロント商品（500〜1000円）を販売する。

### 9-2. 全体フロー
登録
→ アンケート
→ 教育メッセージ
→ フロント商品誘導

### 9-3. 初回メッセージ（テンプレ）
🎁ご登録ありがとうございます！

このLINEでは
「初心者でも収益化できる副業情報」を配信しています📈

まずはあなたに合った情報をお届けしたいので
【30秒の簡単アンケート】にご協力ください👇

👉（アンケートURL）

### 9-4. アンケート項目
- 現在の状況（会社員 / 主婦 / フリーランス / 学生）
- 副業経験（なし / 少しある / 収益化済）
- 目標収益（月1〜5万 / 5〜10万 / 10万以上）
- 興味分野（SNS / AI / 物販 / 投資）
- 悩み（自由記述）

### 9-5. アンケート後処理
- `user_profiles` に回答保存
- `user_status` 初期化（`未対応` → `教育中`）

### 9-6. 自動返信（アンケート後テンプレ）
ありがとうございます！

あなたに合った内容をお送りしますね😊

実は今だけ
「最短で収益化する方法」をまとめた教材を
限定価格で公開しています👇

通常3,000円 → 今だけ【980円】

👉（購入リンク）

### 9-7. ステータス遷移
`未対応` → `教育中` → `購入済`

### 9-8. 運用メモ
- フロント商品は低価格帯を維持
- CV（即購入導線）を最優先


---

## 10) AIマネジメントLINE シナリオ仕様

### 10-1. 目的
AI活用ユーザーを教育し、NOTEやコンテンツへ誘導する。

### 10-2. 全体フロー
登録
→ アンケート
→ レベル判定
→ NOTE誘導

### 10-3. 初回メッセージ（テンプレ）
ご登録ありがとうございます🤖

このLINEでは
「AIを使って収益化する方法」を配信しています。

まずはあなたのレベルに合わせて案内するので
【30秒アンケート】お願いします👇

👉（アンケートURL）

### 10-4. アンケート項目
- AI使用経験（未経験 / 少し / 日常的）
- 利用目的（副業 / 業務効率 / 情報収集）
- 興味分野（ChatGPT / 画像生成 / 自動化）
- 収益目標（月〜5万 / 5〜10万 / 10万以上）
- 悩み（自由記述）

### 10-5. 分岐ロジック
- 初心者: 基礎NOTE
- 中級以上: 応用NOTE

### 10-6. 自動返信（NOTE誘導テンプレ）
ありがとうございます！

あなたの回答をもとに
最適な内容をまとめました👇

👉（NOTEリンク）

※初心者でも理解できる内容です

### 10-7. ステータス遷移
`未対応` → `教育中` → `コンテンツ閲覧`

### 10-8. 運用メモ
- NOTE導線を主導線として設計する
- 教育 → 信頼形成 → 購入導線を固定する


---

## 11) 不動産LINE シナリオ仕様

### 11-1. 目的
売却意欲のあるユーザーを抽出し、リード化する。

### 11-2. 全体フロー
登録
→ アンケート
→ 売却意欲判定
→ HOT/WARM/COLD分類
→ 最適導線

### 11-3. 初回メッセージ（テンプレ）
ご登録ありがとうございます🏠

このLINEでは
「不動産を高く売る方法」を無料で配信しています。

まずは状況を把握したいので
【30秒アンケート】にご協力ください👇

👉（アンケートURL）

### 11-4. アンケート項目
- 物件種別（マンション / 戸建て / 土地）
- エリア（市区町村）
- 売却予定（すぐ / 3ヶ月 / 半年 / 未定）
- 査定経験（あり / なし）
- ローン残債（あり / なし）
- 売却理由（自由記述）

### 11-5. ステータス判定ロジック
- すぐ売却: `HOT`
- 3ヶ月以内: `HOT`
- 半年以内: `WARM`
- 未定: `COLD`

### 11-6. 自動返信テンプレ

#### HOT
ご回答ありがとうございます！

かなり良い条件なので
【無料査定】を優先的にご案内できます👇

👉（査定リンク）

#### WARM
ありがとうございます！

まずは損しないために
「売却前に知るべきポイント」をまとめました👇

👉（コンテンツリンク）

#### COLD
ありがとうございます！

今後のために
「不動産売却の基礎」をまとめています👇

👉（記事リンク）

### 11-7. DB連携
- `user_profiles` に回答保存
- `user_status` に `HOT/WARM/COLD` を設定

### 11-8. 運用メモ
- 最優先は `HOT` 抽出
- UIで優先対応（色分け・上位表示）可能にする


---

## 12) シナリオJSON / DBスキーマ / Webhook実装雛形

### 12-1. シナリオJSON共通フォーマット
```json
{
  "scenario_name": "string",
  "steps": [
    {
      "step_id": "string",
      "trigger": {
        "type": "keyword | event | status",
        "value": "string"
      },
      "action": {
        "type": "send_message | update_status | next_step",
        "template_id": "string"
      },
      "next_step_id": "string"
    }
  ]
}
```

### 12-2. 副業LINEシナリオJSON
```json
{
  "scenario_name": "side_business",
  "steps": [
    {
      "step_id": "start",
      "trigger": { "type": "event", "value": "follow" },
      "action": { "type": "send_message", "template_id": "welcome_side" },
      "next_step_id": "wait_survey"
    },
    {
      "step_id": "wait_survey",
      "trigger": { "type": "event", "value": "survey_completed" },
      "action": { "type": "update_status", "template_id": "education_start" },
      "next_step_id": "offer"
    },
    {
      "step_id": "offer",
      "trigger": { "type": "status", "value": "education" },
      "action": { "type": "send_message", "template_id": "offer_low_ticket" },
      "next_step_id": null
    }
  ]
}
```

### 12-3. AIマネジメントLINEシナリオJSON
```json
{
  "scenario_name": "ai_management",
  "steps": [
    {
      "step_id": "start",
      "trigger": { "type": "event", "value": "follow" },
      "action": { "type": "send_message", "template_id": "welcome_ai" },
      "next_step_id": "survey"
    },
    {
      "step_id": "survey",
      "trigger": { "type": "event", "value": "survey_completed" },
      "action": { "type": "send_message", "template_id": "note_intro" },
      "next_step_id": null
    }
  ]
}
```

### 12-4. 不動産LINEシナリオJSON
```json
{
  "scenario_name": "real_estate",
  "steps": [
    {
      "step_id": "start",
      "trigger": { "type": "event", "value": "follow" },
      "action": { "type": "send_message", "template_id": "welcome_estate" },
      "next_step_id": "survey"
    },
    {
      "step_id": "survey",
      "trigger": { "type": "event", "value": "survey_completed" },
      "action": { "type": "update_status", "template_id": "status_by_answer" },
      "next_step_id": "branch"
    },
    {
      "step_id": "branch",
      "trigger": { "type": "status", "value": "HOT" },
      "action": { "type": "send_message", "template_id": "hot_offer" },
      "next_step_id": null
    }
  ]
}
```

### 12-5. DBスキーマ（SQL）
```sql
-- users
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  email TEXT,
  password TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- accounts（LINE公式）
CREATE TABLE accounts (
  id SERIAL PRIMARY KEY,
  name TEXT,
  channel_id TEXT,
  channel_secret TEXT,
  access_token TEXT
);

-- user_line_accounts（超重要）
CREATE TABLE user_line_accounts (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  account_id INTEGER REFERENCES accounts(id),
  line_user_id TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE (account_id, line_user_id)
);

-- messages
CREATE TABLE messages (
  id SERIAL PRIMARY KEY,
  user_id INTEGER,
  account_id INTEGER,
  role TEXT,
  content TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- user_profiles
CREATE TABLE user_profiles (
  id SERIAL PRIMARY KEY,
  user_id INTEGER,
  account_id INTEGER,
  data JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);

-- user_status
CREATE TABLE user_status (
  id SERIAL PRIMARY KEY,
  user_id INTEGER,
  account_id INTEGER,
  status TEXT,
  updated_at TIMESTAMP DEFAULT NOW()
);
```

### 12-6. Webhook実装雛形（FastAPI）
```python
from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/webhook")
async def webhook(req: Request):
    body = await req.json()
    events = body.get("events", [])

    for event in events:
        line_user_id = event["source"]["userId"]
        message = event.get("message", {}).get("text")

        # ① account_id取得（ヘッダーやURLで識別）
        account_id = get_account_id(req)

        # ② user特定
        user = find_user(account_id, line_user_id)

        # ③ メッセージ保存
        save_message(user.id, account_id, message)

        # ④ シナリオ実行
        response = run_scenario(user, account_id, message)

        # ⑤ LINE返信（受信アカウントからのみ返信）
        send_line_message(account_id, line_user_id, response)

    return {"status": "ok"}


def find_user(account_id, line_user_id):
    # user_line_accounts から検索
    pass


def run_scenario(user, account_id, message):
    # JSONシナリオに基づく処理
    return "返信内容"


def send_line_message(account_id, line_user_id, text):
    # LINE Messaging API
    pass
```

### 12-7. ここまでで完成する範囲
- ユーザー管理（内部統合）
- LINEアカウント分離運用
- シナリオ駆動返信
- DB永続化
- Webhook受信〜返信のコア導線

### 12-8. 次フェーズ
- LINE Messaging API本実装（署名検証含む）
- UI管理画面
- シナリオエディタ
- 決済連携（Stripe）


---

## 13) 実装指示書（優先度順 / 段階実装）

### 13-0. 前提
- 実装は段階的に進める
- 全機能同時実装は禁止
- 実装順序を厳守する

### 13-1. LINE Messaging API本実装（最優先）

#### 目的
Webhook受信からLINE返信までを正しく動作させる。

#### 必須実装

##### 13-1-1. 署名検証
- `X-Line-Signature` ヘッダーを取得
- `channel_secret` で署名検証
- 検証失敗時はHTTP 400

##### 13-1-2. Webhook受信処理
- `/webhook` エンドポイント実装
- `events` 配列をループ
- `message` イベントを対象に処理

##### 13-1-3. replyToken返信
- `event.replyToken` 取得
- Reply APIで返信
- 初期返信文は固定で可
  - 例: `メッセージを受け取りました`

##### 13-1-4. push message対応
- accountごとの `access_token` で送信
- 管理画面/業務ロジックから送信可能にする

##### 13-1-5. エラーハンドリング
- 例外はすべてログ出力
- LINE APIエラーは詳細ログ出力
- Webhookは再送防止のため最終的にHTTP 200を返す

### 13-2. ユーザー特定ロジック

対象関数:
- `find_user(account_id, line_user_id)`

処理仕様:
1. `user_line_accounts` を `account_id + line_user_id` で検索
2. 存在時: 対応 `user_id` を返す
3. 未存在時:
   - `users` に新規作成
   - `user_line_accounts` に紐付け作成
   - 作成した `user` を返す

注意:
- `line_user_id` 単体検索は禁止
- 必ず `account_id` と組み合わせる

### 13-3. シナリオ実行エンジン

対象関数:
- `run_scenario(user, account_id, message)`

目的:
- ユーザー状態に応じて返信テキストを決定

初期実装（最小）:
- 固定返信のみ返す
- DB保存後に呼ぶ

次段階:
- JSONシナリオ読込
- 現在ステータス取得
- 条件分岐でテンプレ選択
- ステータス更新

入力:
- `user_id`
- `account_id`
- `message`

出力:
- 返信テキスト

### 13-4. アンケート連携

目的:
- ユーザー情報をDB保存し、分岐に使用

処理:
1. フォームからAPIへPOST
2. `user_id + account_id` で対象特定
3. `user_profiles` にJSON保存
   - 名前
   - 属性情報
   - 回答内容
   - イベント
4. 保存後 `survey_completed` を発火
5. `run_scenario` にイベント入力
6. ステータス更新へ反映

### 13-5. UI（最小構成）

必須機能:
1. ユーザー一覧
   - `user_id`
   - `account_id`
   - `status`
   - 最終メッセージ日時
2. ステータス表示
   - `HOT / WARM / COLD`
   - 色分け（任意）
3. メッセージ履歴
   - ユーザー単位
   - 時系列表示

### 13-6. 実装手順（厳守）

1. Webhook受信 → 固定返信
2. メッセージをDB保存
3. ユーザー紐付け処理実装
4. シナリオ処理追加

### 13-7. 最小動作条件（第一段階完了条件）

LINE送信
→ Webhook受信
→ ユーザー特定
→ DB保存
→ 固定返信

### 13-8. 禁止事項
- 全機能同時実装
- `account_id` 無視のユーザー特定
- 例外未処理
- Webhookで200以外を返す運用

### 13-9. この段階で不要な項目
- UI高度機能
- 複雑シナリオ分岐
- 決済連携

### 13-10. 完了定義
以下が確認できれば完了:
1. LINE送信で即返信される
2. DBにメッセージが保存される
3. 同一ユーザーが正しく紐付く


---

## 14) 最終追記（運用必須レベル）

### 14-1. 冪等性（Webhook再送対策）

#### 追加仕様
Webhookは同一イベントが複数回送信される可能性があるため、
`event_id` または `message_id` を用いて重複処理を防止すること。

同一イベントは**1回のみ**処理すること。

#### 理由
LINEでは以下が発生する:
- タイムアウト時の再送
- ネットワーク遅延による重複

対策しない場合の障害:
- 同一メッセージの重複保存
- 同一返信の重複送信

#### 実装指針
- `processed_events` テーブルを用意し `UNIQUE(account_id, event_id)` 制約を付与
- 処理開始時に重複チェック
- 既処理なら即終了（200返却）

### 14-2. タイムアウト対策（非常に重要）

#### 追加仕様
Webhook処理は短時間で完了させること。
重い処理（シナリオ計算・外部API・集計）は非同期または後処理に回すこと。

Webhookは **即時200返却を優先**すること。

#### 理由
- LINEは数秒でタイムアウト
- タイムアウトで再送され、二重処理が発生する

#### 実装指針
- Webhook受信: 検証 + 最小保存 + ACKのみ
- 実処理: Queue/Workerに移譲
- 返信要否判定を軽量化

### 14-3. replyToken制限

#### 追加仕様
`replyToken` は **一度しか使用できない**。再利用禁止。

複数返信が必要な場合は `push message` を使用すること。

#### 理由
この制限を無視すると返信失敗・再送ループ・重複障害が発生する。

### 14-4. ログ設計（推奨→実質必須）

以下を必ずログ出力すること:
- `account_id`
- `line_user_id`
- `user_id`
- 受信メッセージ
- 返信内容

推奨追加項目:
- `event_id`
- `message_id`
- 処理結果（processed/skipped/error）
- エラー詳細（stacktrace）


---

## 15) 冪等性実装（processed_events）

### 15-1. 目的
Webhookの再送や重複イベントによる二重処理を防止する。

### 15-2. テーブル定義
```sql
CREATE TABLE processed_events (
  id SERIAL PRIMARY KEY,
  event_id TEXT UNIQUE,
  created_at TIMESTAMP DEFAULT NOW()
);
```

### 15-3. 使用ルール
1. Webhook受信時に `event_id` を取得
2. `processed_events` を存在チェック
3. 存在する場合は処理をスキップ
4. 存在しない場合のみ処理を実行
5. 処理後に `event_id` を保存

### 15-4. event_id取得ルール（優先順位）
1. `event.message.id`（存在する場合）
2. `event.replyToken`
3. 上記が無い場合はハッシュ生成

### 15-5. 注意事項
- `UNIQUE(event_id)` 制約で重複を防止する
- `INSERT` 時のUNIQUE違反エラーも「重複イベント」として扱う

---

## 16) Webhook最小実装（FastAPI / 開発確認用・本番NG）

### 16-1. 実装コード
```python
from fastapi import FastAPI, Request, HTTPException
import hashlib
import hmac
import base64
import json
import requests

app = FastAPI()

CHANNEL_SECRET = "YOUR_CHANNEL_SECRET"
CHANNEL_ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"

LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"

# ダミーDB（実際はDB接続）
processed_events = set()


def verify_signature(body: bytes, signature: str):
    hash_value = hmac.new(
        CHANNEL_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).digest()
    expected = base64.b64encode(hash_value).decode()
    return hmac.compare_digest(expected, signature)


def is_processed(event_id: str):
    return event_id in processed_events


def mark_processed(event_id: str):
    processed_events.add(event_id)


def get_event_id(event):
    return (
        event.get("message", {}).get("id")
        or event.get("replyToken")
    )


def send_reply(reply_token: str, text: str):
    headers = {
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "replyToken": reply_token,
        "messages": [
            {"type": "text", "text": text}
        ]
    }

    res = requests.post(LINE_REPLY_URL, headers=headers, json=payload)

    if res.status_code != 200:
        print("LINE ERROR:", res.text)


@app.post("/webhook")
async def webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Line-Signature")

    if not verify_signature(body, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    data = json.loads(body)

    for event in data.get("events", []):
        event_id = get_event_id(event)

        if not event_id:
            continue

        if is_processed(event_id):
            continue

        mark_processed(event_id)

        if event["type"] != "message":
            continue

        if event["message"]["type"] != "text":
            continue

        reply_token = event["replyToken"]
        text = event["message"]["text"]

        # 最小動作（固定返信）
        send_reply(reply_token, f"受信: {text}")

    return {"status": "ok"}
```



**※本番環境では必ずDB接続版を使用すること（16章は開発確認用）**


---

## 17) Webhook本番実装（FastAPI / PostgreSQL・冪等性DB保証）

### 17-1. 本番要件
- 冪等性は `processed_events(event_id UNIQUE)` で保証する
- 再起動後も重複判定が維持されること
- 複数プロセス環境でも同一イベントを1回だけ処理すること

### 17-2. 追加SQL（推奨）
```sql
CREATE TABLE IF NOT EXISTS processed_events (
  id BIGSERIAL PRIMARY KEY,
  event_id TEXT NOT NULL UNIQUE,
  account_id INTEGER,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_processed_events_created_at
  ON processed_events(created_at);
```

### 17-3. FastAPI実装（DB接続版）
```python
from fastapi import FastAPI, Request
import hashlib
import hmac
import base64
import json
import os
import requests
import psycopg2
from psycopg2.errors import UniqueViolation

app = FastAPI()

CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"
DATABASE_URL = os.getenv("DATABASE_URL")


def get_db_conn():
    return psycopg2.connect(DATABASE_URL)


def verify_signature(body: bytes, signature: str) -> bool:
    if not signature:
        return False
    digest = hmac.new(
        CHANNEL_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, signature)


def get_event_id(event: dict) -> str:
    mid = event.get("message", {}).get("id")
    rt = event.get("replyToken")
    if mid:
        return f"msg:{mid}"
    if rt:
        return f"reply:{rt}"
    # 最終フォールバック
    return "hash:" + hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()


def mark_event_once(conn, event_id: str, account_id: int | None) -> bool:
    """
    True  -> 初回処理（INSERT成功）
    False -> 重複（UNIQUE違反）
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO processed_events(event_id, account_id) VALUES (%s, %s)",
                (event_id, account_id),
            )
        conn.commit()
        return True
    except UniqueViolation:
        conn.rollback()
        return False


def send_reply(access_token: str, reply_token: str, text: str):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}],
    }
    res = requests.post(LINE_REPLY_URL, headers=headers, json=payload, timeout=8)
    if res.status_code >= 300:
        print("LINE_REPLY_ERROR", res.status_code, res.text)


def get_account_from_request(req: Request) -> tuple[int, str]:
    """
    実装側で account_id をURL/ヘッダ/Host から解決し、
    対応する access_token を返す。
    """
    # 例: ?account_id=1
    account_id = int(req.query_params.get("account_id", "1"))
    # TODO: DBのaccountsテーブルから取得
    access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    return account_id, access_token


@app.post("/webhook")
async def webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")

    # 署名不正は400
    if not verify_signature(body, signature):
        return {"ok": False, "error": "invalid_signature"}

    data = json.loads(body)
    account_id, access_token = get_account_from_request(request)

    conn = get_db_conn()
    try:
        for event in data.get("events", []):
            event_id = get_event_id(event)

            # 冪等性保証（DB）
            first_time = mark_event_once(conn, event_id, account_id)
            if not first_time:
                continue

            if event.get("type") != "message":
                continue
            if event.get("message", {}).get("type") != "text":
                continue

            reply_token = event.get("replyToken")
            text = event.get("message", {}).get("text", "")
            line_user_id = event.get("source", {}).get("userId")

            # ここで find_user / save_message / run_scenario を順次接続する
            # user = find_user(account_id, line_user_id)
            # save_message(user.id, account_id, "user", text)
            # reply_text = run_scenario(user, account_id, text)
            reply_text = f"受信: {text}"

            # replyTokenは一度だけ使用
            if reply_token:
                send_reply(access_token, reply_token, reply_text)

            print({
                "account_id": account_id,
                "line_user_id": line_user_id,
                "received": text,
                "reply": reply_text,
                "event_id": event_id,
            })
    except Exception as e:
        # 例外はログ化
        print("WEBHOOK_ERROR", str(e))
    finally:
        conn.close()

    # 再送防止のため常に200を返す
    return {"status": "ok"}
```

### 17-4. 接続順（次アクション）
1. `find_user(account_id, line_user_id)` 実装
2. `messages` 保存処理追加
3. `run_scenario` 実装
