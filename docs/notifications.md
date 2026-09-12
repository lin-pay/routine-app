# Daily — 通知機能のしくみと設定

## 全体像

通知は 2 層構成になっている。

| 層 | 動く条件 | 設定の手間 |
|---|---|---|
| **① 前面通知**（既定で動く） | アプリを開いている／バックグラウンドで生きている間 | なし |
| **② プッシュ通知** | アプリを閉じていても届く | 設定済み（送信元の Mac が起きている必要あり） |

どちらも同じ `tag`（`am` / `pm` / `t<タスクID>`）を使うので、両方が動いていても
同じ通知が二重に積み上がることはない（後から来たものが置き換わる）。

## 通知の種類

| 種類 | 既定時刻 | 内容 |
|---|---|---|
| ☀️ 朝のまとめ | 07:30 | 今日該当するルーティンの件数と名前 |
| ⏰ タスクごと | タスクに設定した時刻 | 「🔥 N日連続中 — 今日でN+1日目」 |
| 🌙 夜の未完了 | 21:00 | 残り件数＋連続記録が途切れるタスクの警告 |

予定時刻を過ぎてから **45分以内**（`NWIN`）に一度だけ発火する。過ぎすぎた通知は出さない。
1日1回までの制御は、前面通知は `localStorage`（キー `daily_notif_log`）、
プッシュは Firestore の `users/{uid}/data/notifLog` で行う。

## ① 前面通知（設定不要）

1. アプリを開く → ヘッダーの **⚙ → 「🔔 通知を許可する」**
2. 「リマインダー」を ON にして、時刻を調整する
3. 「テスト通知を送る」で見た目を確認

**iPhone / iPad の注意**: Safari のタブで開いている状態では `Notification` API が使えない。
Safari の共有ボタン →「ホーム画面に追加」してから、そのアイコンで開くこと。
設定画面にもその旨のガイドが出る。

実装: `index.html` の `checkNotifs()`。60秒ごとの `setInterval` と
`visibilitychange`（復帰時）で予定時刻を過ぎているか確認し、Service Worker
（`sw.js`）の `showNotification()` で表示する。

## ② プッシュ通知（アプリを閉じていても届く）

**FCM は使わず、標準の Web Push（RFC 8291 / 8292）を直接使っている。**
Firebase コンソールでのウェブプッシュ証明書の発行は不要で、VAPID 鍵はローカル生成したもの。
iOS 16.4+ の Apple Push（`web.push.apple.com`）も Chrome（`fcm.googleapis.com`）も同じ標準なので、
送信側のコードは共通。

### 鍵

| | 置き場所 |
|---|---|
| 公開鍵 | `index.html` の `const VAPID_KEY='...'`（公開して問題ない値） |
| 秘密鍵 | `vapid.json`（`.gitignore` の `*.json` で除外済み。**リポジトリに入れないこと**） |

鍵を作り直す場合（作り直すと既存の購読は全部無効になる）:

```bash
node -e "const k=require('web-push').generateVAPIDKeys();require('fs').writeFileSync('vapid.json',JSON.stringify({...k,subject:'https://lin-pay.github.io/routine-app/'},null,2));console.log(k.publicKey)"
```

出た公開鍵を `index.html` の `VAPID_KEY` に貼って push する。
アプリ側は鍵が変わると `InvalidStateError` を検知して自動で購読し直す。

### 端末の登録

アプリ（ホーム画面のアイコンから）を開き、⚙ で通知が ON になっていれば、
起動から数秒後に自動で購読が作られ `users/{uid}/data/settings.pushSubs` に保存される。
通知したい端末ごとに 1 回開けばよい。

`pushSubs` のキーは endpoint の SHA-256 先頭 12 バイト（endpoint は `/` を含み
Firestore のマップキーにできないため）。値は `{ endpoint, p256dh, auth, ua, at }`。

### 送信

```bash
cd /Users/nagaoka/gcp-migration/rinpe04naga06/private/routine-app
node notify.mjs --dry     # 送らずに、何を送るかだけ表示
node notify.mjs --test    # 時刻判定を無視してテスト通知を1通送る
node notify.mjs           # 本番（時刻を過ぎた未送信ぶんだけ送る）
```

15分おきの自動実行（LaunchAgent）:

```bash
cp com.routine-app.notify.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.routine-app.notify.plist
launchctl list | grep routine-app        # 確認
tail -f reports/notify.log               # ログ
```

停止する場合（このディレクトリの慣習に合わせてリネームで無効化）:

```bash
launchctl bootout gui/$(id -u)/com.routine-app.notify
mv ~/Library/LaunchAgents/com.routine-app.notify.plist{,.disabled-$(date +%Y%m%d)}
```

失効した購読（HTTP 404 / 410）は `notify.mjs` が自動で `pushSubs` から削除する。

**制約**: 送信元は Mac なので、**Mac がスリープ／電源オフの間は送信されない**。
launchd はスリープ中に取りこぼしたジョブを起床時に実行するため、
起きた直後にまとめて届くことがある（ただし予定時刻から45分以上経っていれば送らない）。
常時配信したい場合は Cloud Functions + Cloud Scheduler へ移すことになるが、
Firebase の Blaze（従量課金）プランが必要。

## ファイル

| ファイル | 役割 |
|---|---|
| `index.html` | 通知設定 UI、前面通知のスケジューラ、Web Push の購読登録 |
| `sw.js` | Service Worker。`push` / `notificationclick` を処理して通知を表示 |
| `notify.mjs` | Firestore を読んで Web Push 送信（firebase-admin + web-push） |
| `vapid.json` | VAPID 鍵ペア（**gitignore 済み・バックアップ推奨**） |
| `com.routine-app.notify.plist` | 15分おき実行の LaunchAgent 定義 |

## Firestore のデータ

```
users/{uid}/data/settings
  notif: { on, morningOn, morning, eveningOn, evening, taskOn }
  pushSubs: { "<endpointのハッシュ>": { endpoint, p256dh, auth, ua, at } }

users/{uid}/data/notifLog          # notify.mjs の送信済みフラグ（当日ぶんのみ）
  "2026-09-12:am": 1
  "2026-09-12:t:t_1712...": 1

users/{uid}/data/tasks
  items: [{ id, name, icon, days[], time, createdAt }]   # time が新フィールド（リマインド時刻 "HH:MM"）
```
