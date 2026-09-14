# x-bot

X (Twitter) で「1 つの人格の雑談 bot」を動かす CLI。書き込みは **twikit(twifork, curl_cffi impersonation)** で行い、**226 / 403 (自動化判定) が出たら Playwright の実ブラウザ UI に自動フォールバック**する。

2026 年時点の X 事情を実測して作り込んだ:
- X は twikit の `login()` フローを廃止 (code 366) → **新規パスワードログイン不可**。認証はログイン済みブラウザのクッキー (`auth_token` + `ct0`) を渡す。
- upstream `twikit` 2.3.3 は 2026 で破損 (create_tweet が 226 "looks automated" / ClientTransaction の KEY_BYTE 破壊 / Cloudflare 403)。`twifork` (import は `twikit` のまま) が生きている。
- POST は fork でもアカウント / IP 依存で 226 が残る → 実ブラウザが確実なフォールバック。

## セットアップ

```
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e .
python -m playwright install chromium
```

クッキーを用意する (最重要ステップ):

```
xbot login --cookies cookies.json
```

非ヘッドレス Chromium が開き X のログイン画面が出る。**手動でログインしたら**ターミナルで Enter → `auth_token` / `ct0` が保存される。クッキーは SSH 鍵並みの秘密。**git に絶対コミットしない**。

形式の参考: `cookies.example.json`(twikit 用クッキー)、`secrets.example.json`(画面名/パスワード)。実ファイル `cookies.json` / `secrets.json` は本ツールでは両方とも未使用で可(認証はブラウザクッキーのみ)。`.gitignore` で両者を除外済み。

環境変数:
- `XBOT_COOKIES` — cookies.json の場所 (既定 `cookies.json`)
- `XBOT_SCREEN_NAME` — 自分の screen_name (`check`/`mentions` が使う。例 `Japanese_gguf`)
- `XBOT_WATCH` — いいね監視対象 (既定 `qa_a_aa`)

リポジトリ直下の `.env`(KEY=VALUE 形式)は自動で読まれる。実値のサンプルに差し替えて使ってよい。

## 使い方

```
xbot check --me Japanese_gguf          # 認証疎通 + ホーム TL
xbot tl --count 30                     # タイムライン
xbot user qa_a_aa --tab Tweets         # 特定ユーザーのツイート/リプライ
xbot tweet 1234567890 --thread         # 1 ツイート or スレッド表示
xbot mentions                          # 最近のメンション
xbot post "未来の自分にコードを読ませると毎回「これ誰が書いたの」って言われる"   # 投稿
xbot post "呼んだ？" --reply-to 1234567890   # 返信
xbot like 1234567890 2345678901        # いいね
xbot rt 1234567890                     # リポスト
xbot follow some_user                  # フォロー
xbot act actions.json --gap 30         # 一括アクション
```

`act` の JSON 形式 (`actions.example.json`):

```json
[
  { "op": "like", "id": "1234567890" },
  { "op": "rt",   "id": "2345678901", "sleep": 5 },
  { "op": "reply","id": "3456789012", "text": "それな", "sleep": 8 },
  { "op": "post", "text": "久しぶりに窓から出た" }
]
```

### フォールバックの挙動

書き込みは常に twikit を先に試す。
- `Unauthorized` / `Forbidden` → **認証切れ**。勝手に再ログインしない。`xbot login` でクッキー更新 → 1 回だけリトライ。
- メッセージに `automated / 226 / Cloudflare / KEY_BYTE` を含む → **実ブラウザで同じ操作を再実行**。
- `--no-fallback` を付けると実ブラウザ起動をしない。`--headless` でヘッドレス化。

## 人格 / 自動運用

- `PERSONA.md` — bot の人格と文体。エージェント駆動で使うなら必ず読ませる。
- `prompts/AGENT.md` — LLM エージェント (例: `opencode run --auto`) に渡す起動プロンプト。
  定期実行例:

  ```
  opencode run --auto --dir . -- "prompts/AGENT.md を読んで運用せよ"
  ```

  参考: Windows タスクスケジューラで 5〜90 分間隔にすると、完全放置で動く自走 bot になる。

## 禁止事項 (地雷)

- **ログインは 1 回だけ。連打禁止。** 連打すると「セッション集中管理」になり新規トークンが数分で死ぬ。3 回失敗したら数時間〜1 日クールダウン。
- クッキーを別 IP から使わない。X は IP 範囲が変わるとセッションを即破棄する。**レジデンシャル IP のみ**。VPS / DC IP / 無料プロキシは全部 401 で刺される。
- `secrets.json` / `cookies.json` はコミット禁止 (.gitignore 済み)。
- 自動運用まわりは節度: 常識の範囲で (DM ・無断晒し・政治宗教への深入り禁止)。

## 開発

```
pip install -e .[dev]   # なし。素の pytest で十分
```

テストは twikit に依存しない層 (classify_error / cookie 形式) を対象にしておく。
ライブラリ仕様が変わる可能性が高いので `twikit` の import は関数内で行っている (client.py)。

## License

MIT