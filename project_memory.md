# Project Memory

## プロジェクト全体像

`private/` 配下に個人プロジェクトを格納するワークスペース。

### routine-app/
- **目的**: ルーティンタスク管理 + フィットネストラッカーの統合アプリ「Daily」
- **形式**: スタンドアロンHTML（`index.html` 1ファイル）
- **デプロイ先**: GitHub Pages — https://lin-pay.github.io/routine-app/
- **GitHub**: https://github.com/lin-pay/routine-app
- **バックエンド**: Firebase (Authentication + Firestore)
  - プロジェクト: routine-app-5eff3
  - Google認証、承認済みドメインに `lin-pay.github.io` 追加済み
  - データ構造: `users/{uid}/data/{tasks|completions|fitness|reports|flashcards|settings|notifLog}`

#### ルーティンタブ (✅)
- 曜日チェックボックス（毎日・平日・週末プリセット）、リマインド時刻（任意、`time`）
- 今日該当タスクのみ表示、日付ナビで過去日の修正可
- ストリーク: 該当日ベースで連続判定
- カテゴリなし（フラット）、完了済みを下に自動ソート
- 進捗リング + モチベーション帯（パーフェクトデー連続・30日達成率・ストリーク途切れ警告）
- 📊 継続記録ビュー: 18週ヒートマップ、パーフェクトデー連続/自己最高、達成率、タスク別ストリーク
- 🎉 マイルストーン祝福（3/7/14/21/30/50/75/100/150/200/300/365日 と全タスク達成）
- ⚙ 設定ビュー: 通知の許可/ON・OFF/時刻、テスト通知、ログアウト
- 🔔 通知: 前面通知（設定不要）+ FCMプッシュ（VAPID鍵設定で有効化）→ `docs/notifications.md`

#### フィットネスタブ (💪)
- デザイン: ダークグリーン + JetBrains Mono（fitness_tracker.jsx ベース）
- 曜日スケジュール: 月=筋トレB, 火=休養, 水=筋トレA, 木=休養, 金=休養, 土=筋トレC, 日=ラン（ロング）（2026-06-09に月⇔水を入れ替え、2026-10-23から火・木のランをやめて月水土日のみ。10/22以前の日付は `SCHEDULE_OLD` で旧予定（火・木=ラン）のまま表示）
- 筋トレA/B/C: 各3〜4種目、3セット、重量×レップ記録
- ラン: 距離・時間・心拍・ペース（自動計算）・メモ
- 体重・食事メモ
- 週次サマリー（4カラムグリッド、最大重量、日別ログ）
- 推移タブ: 体重・各種目の最大重量（懸垂はA/B/C統合）・ラン距離/ペース/平均心拍をスパークラインで表示。改善方向（重量↑/ペース↓など）を緑、悪化方向を赤で表示
- トレーナーアドバイス（「アドバイス」タブ）: 毎週金曜8:00に自動生成、Firestore保存（直近12件）
  - 生成スクリプト: `fitness-report.mjs`（Firebase Admin SDK + Claude CLI）
  - Mac LaunchAgent (`com.routine-app.fitness-report`) で自動実行していた（毎週金曜 19:40 JST、`claude -p` 呼び出し）— crontabから移行済み(2026-04-07)
  - **2026-06-16 停止**: `claude -p` が別料金になったためユーザー依頼で自動実行を停止。`launchctl bootout` でアンロード後、plistを `com.routine-app.fitness-report.plist.disabled-20260616` にリネーム（このディレクトリの無効化慣習に準拠）。再開するにはリネームを戻して `launchctl bootstrap gui/$(id -u) <plist>` を実行。スクリプト自体は残存（手動実行は可能）
  - ログ: `reports/cron.log`
  - launchdはスリープ中のmissed jobを起床時に自動実行する（cronのPersistent相当）
  - サービスアカウントキー: `routine-app-5eff3-firebase-adminsdk-*.json`（.gitignoreで除外）

#### その他ファイル
- `sw.js`: Service Worker（通知表示専用。キャッシュはしない）
- `notify.mjs`: FCMプッシュ送信スクリプト（`--dry` / `--test` オプションあり）
- `com.routine-app.notify.plist`: 通知送信を15分おきに実行する LaunchAgent テンプレート（未インストール）
- `docs/notifications.md`: 通知機能の全体像と有効化手順
- `fitness_tracker.jsx`: フィットネスタブのデザイン元（Claude.aiアーティファクト版）
- `index (2).html`: Claude.aiからダウンロードした元ファイル
- `fitness-report.mjs`: トレーナーアドバイス自動生成スクリプト
- `reports/`: 生成レポートのローカル保存先（.gitignoreで除外）

### palavras（flashcard.html）
- **目的**: ポルトガル語-日本語フラッシュカードアプリ（忘却曲線ベース）
- **形式**: スタンドアロンHTML（`flashcard.html` → デプロイ時は `index.html`）
- **デプロイ先**: GitHub Pages — https://lin-pay.github.io/palavras/
- **GitHub**: https://github.com/lin-pay/palavras
- **バックエンド**: 同じFirebaseプロジェクト（routine-app-5eff3）を共有
- **アルゴリズム**: SM-2（間隔: 1日→3日→8日→20日→50日...と拡大）
- **機能**: カード追加/編集/削除、復習セッション（4段階評価）、検索、統計
- **デザイン**: ダークテーマ、グリーンアクセント（ブラジルカラー）

## 今回やったこと
- **トレーニング日を月水土日に変更**（2026-10-23、ユーザー依頼「トレーニングの日を月水土日にして」）
  - ルーティンの「💪 トレーニング」タスク（`t_1773838212421`）の `days` を Firestore で直接 `[0,1,2,3,5,6]`（月火水木土日）→ `[0,2,5,6]`（月水土日）に変更。Admin SDK のトランザクションで、確認時の値から変わっていないことを確かめてから書き込んだ。戻すときは `days` を `[0,1,2,3,5,6]` にする（アプリの編集画面で曜日を付け直してもよい）
  - 注意: ストリーク・達成率・ヒートマップは「今の `days`」で過去もさかのぼって計算するので、過去の火・木はカウント対象から外れる（アプリの仕様どおり）
  - トレーニングタブ: `SCHEDULE` の火(2)・木(4)を `rest`（完全休養）に変更。あわせて `schOf(d)` を追加し、`SCHEDULE_FROM='2026-10-23'` より前の日付は `SCHEDULE_OLD`（火・木=ランニング（ゾーン3））で表示する。記録画面と週次サマリー（2か所）の `SCHEDULE[dow]` を `schOf(d)` に置き換えた。理由: 過去の火・木のラン記録（26件中17件）が休養日表示に隠れ、週次のラン回数からも消えてしまうのを防ぐため（前回の月⇔水入れ替えでは過去日を考慮していない）
  - `fitness-report.mjs`（自動実行は停止中）のスケジュール文言も新しい予定に合わせた。月⇔水の入れ替えもまだ反映されていなかったので一緒に直した
  - 検証: Firebase をスタブにした headless Chrome ハーネス（Firestore 実データのコピーを使用、scratchpad 内）で、旧コードとの差分が「10/27(火)・10/29(木) がラン→休養」だけであることを確認。5/28(木) など過去のラン記録が表示されること、切り替えをまたぐ週（10/19〜25）の週次表示が旧予定のままであること、ルーティンの週間表示で「トレーニング」が月・水・土・日に出ることも確認。書き込みは0件
- **トレーニング記録の入力をどうするか相談を受けた**（2026-10-23）→ 実データを確認したうえで案を出し、返事待ち（「未完了」参照）
  - 細かい記録（重量×回数・ラン）は 3/17〜6/8 の筋トレ25回・ラン26回で止まっている。体重は 4/30 まで、食事メモは0件
  - 5月はトレーニングタブに15回記録しているのに、ルーティンの「トレーニング」✓は1回だけ。逆に9月はルーティンの✓が3回あってトレーニングタブの記録はない → 同じことを2か所に入れる二重入力になっていて、どちらか片方しか続いていない
- **（アプリとは無関係）セントラル・テージョの展示パネルの写真32枚を日本語訳**（2026-09-30、Telegram経由の依頼）→ `docs/central_tejo_panels_ja.md`。「情報を削らない」という指示だったので要約はせず全文を訳した。判読できない箇所は［判読不能］、不確かな数字は（？）と明記。未コミット
- **ルーティンタブに通知機能と継続性向上機能を追加**（2026-09-12）
  - 新規ファイル: `sw.js`（Service Worker）、`notify.mjs`（FCMプッシュ送信）、`com.routine-app.notify.plist`（LaunchAgentテンプレート）、`docs/notifications.md`（設定手順）
  - **通知**（2層構成。詳細は `docs/notifications.md`）
    - ① 前面通知: 設定不要。60秒interval + `visibilitychange` で予定時刻を監視し、`sw.js` の `showNotification()` で表示。1日1回の制御は `localStorage['daily_notif_log']`
    - ② プッシュ通知: **FCMは使わず標準 Web Push（RFC 8291/8292）**。Firebaseコンソールでのウェブプッシュ証明書発行が不要になるため（コンソール作業は自動化できない）。VAPID鍵はローカル生成し、公開鍵を `index.html` の `VAPID_KEY`、秘密鍵を `vapid.json`（`.gitignore` の `*.json` で除外）に配置。購読は `swReg.pushManager.subscribe()` → `users/{uid}/data/settings.pushSubs` に merge 書き込み（キーは endpoint の SHA-256 先頭12バイト。endpointは `/` を含みFirestoreのマップキーにできないため）。送信は `notify.mjs`（web-push パッケージ）を LaunchAgent で15分おき実行、送信済みフラグは `users/{uid}/data/notifLog`、失効購読(404/410)は自動削除
    - **設定済み・実機疎通確認済み**（2026-09-12）。LaunchAgent `com.routine-app.notify`（15分おき）をインストール済み。iPhone(iOS 18.7)が `web.push.apple.com` に購読登録され、`node notify.mjs --test` で成功1/失敗0
    - VAPIDの `sub` クレームは `https://lin-pay.github.io/routine-app/`（URL形式）。**Apple の push サービスで受理されることを実機で確認済み**（mailto にする必要はない）
    - 通知の種類: ☀️朝のまとめ(既定07:30) / ⏰タスクごとの時刻 / 🌙夜の未完了(既定21:00)。予定時刻から45分以内(`NWIN`)に一度だけ発火
    - 前面通知とプッシュは同じ `tag`（am/pm/t<id>）を使うので二重に積み上がらない
  - **継続性機能**
    - 📊 継続記録ビュー（ヘッダー📊）: パーフェクトデー連続/自己最高、達成率(30日/7日)、のべ完了数、最長ストリーク、18週ヒートマップ（幅いっぱいにflexで伸縮）、タスク別カード（現在/最長ストリーク・30日達成率バー・次の節目まで）
    - 🎉 マイルストーン祝福: ストリークが 3/7/14/21/30/50/75/100/150/200/300/365 日に到達、または全タスク達成で紙吹雪オーバーレイ＋バイブ
    - ホームに「モチベーション帯」: パーフェクトデー連続数・30日達成率、連続3日以上のタスクが未完了なら「⚠️ N日連続が今日で途切れます」警告
    - タスク行のストリーク表示を「N回連続」→「N日連続 → 今日でN+1日目」に変更、7日以上で未完了なら警告色
    - ⚙ 設定ビュー（ヘッダー⚙）: 通知許可・各通知のON/OFFと時刻・テスト通知・アカウント/ログアウト（ログアウトはヘッダーから設定内へ移動）
  - **データモデル追加**: タスクに `time`（"HH:MM" リマインド時刻、任意）、新ドキュメント `users/{uid}/data/settings`（notif設定 + pushTokens）、`users/{uid}/data/notifLog`
  - **バグ修正**: フィットネス「助言」タブのレポート送り矢印が `data-a="rPrev"/"rNext"` でルーティン日付ナビと `switch` の case 衝突を起こし、レポート切替の代わりに日付が動いていた → `repPrev`/`repNext` にリネーム
  - **Service Worker で HTML をネットワーク優先取得**: GitHub Pages が `Cache-Control: max-age=600` を返すため、デプロイ後10分ほど古いアプリが表示され続ける問題があった（特に iOS のホーム画面アプリ）。`fetch` イベントで `req.mode==='navigate'` のみ `fetch(url,{cache:'no-store'})`、オフライン時のみ `daily-shell-v1` キャッシュにフォールバック。CDPで「ファイル変更→即反映」「オフライン時はキャッシュ」「復帰後は再び最新」を確認
  - 統計ロジックはNodeハーネスで検証（ストリーク/最長/達成率/パーフェクトデー/空データ）、UIはheadless Chromeでスクリーンショット確認、28ステップのクリック操作スモークテストをPASS、SWのpushハンドラは `ServiceWorker.deliverPushMessage`（CDP）で正常系・不正ペイロードとも確認
  - デプロイ済み: commit `9be229c` を main にpush、GitHub Pages 反映を確認（`sw.js` 200 / index.html に新コード含む）。index.html・sw.js・notify.mjs・plist・docs/notifications.md・project_memory.md のみコミット、palavras関連の未コミット変更は対象外

### 過去の作業
- フィットネス筋トレメニューの月曜と水曜を入れ替え
  - `SCHEDULE`（index.html L223）の月(1)と水(3)の `label` と `w` を入れ替え。月=筋トレB（ベンチプレス, w:'B'）、水=筋トレA（スクワット, w:'A'）に
  - `w` を入れ替えることで `WORKOUTS` の種目セットも連動して切り替わる。種目IDは種目固定（squat/bench等）、懸垂はpullupA/B/Cの曜日別IDだが推移タブで統合表示のため過去データの整合性は維持
  - デプロイ済み: commit `8498a2b` を main にpush（GitHub Pages反映）。index.htmlのみコミット、palavras関連の未コミット変更は対象外
- フィットネス「ラン」記録の「時間 (分)」入力欄で小数点が入力できないバグを修正（commit `81d58ae`）
  - 原因: 距離欄は `inputmode="decimal"` なのに時間欄だけ `inputmode="numeric"`（整数用キーボード=小数点キーなし）（index.html L405）
  - 修正: 時間欄を `inputmode="decimal"` に変更
- palavras 印刷用 単語リスト（品詞別）HTML を生成
  - スクリプト `build_print_html.py`: words.json (2135語) を `note` と PT 末尾でルールベース分類、A4印刷用3カラムレイアウトのHTMLを `docs/palavras_print.html` に出力
  - カテゴリ: 動詞（不定詞 332／活用形 110／その他 21）、名詞 1081、形容詞 133、過去分詞・男性単数 84、女性形 49、複数形 96、女性複数形 5、副詞 11、口語 3、フレーズ 210
  - 各カテゴリ内は PT 昇順、目次つき、@page A4 + @media print 対応
- palavras: 「↩ 1つ戻す」(undo) で復習評価を取り消した後、それ以降の保存が毎回失敗するバグを修正
  - 原因: rev機能追加前から存在する古いカードは `rEf/rInterval/rReps/rNextReview` フィールドを持たないため、`S.lastRating.snap` にこれらが `undefined` として入る。undo の `Object.assign(card, lr.snap)` で card にも explicit な `undefined` プロパティが生え、Firestore の `setDoc` が同期的に reject → 以後そのカードを含む `S.cards` を保存するたびに「⚠ 保存失敗」トーストが出続ける
  - 修正: undo を `for...in` で書き直し、snap値が `undefined` のキーは `delete card[k]` で削除、それ以外は代入する形に変更
  - 防御策: `initializeFirestore` に `ignoreUndefinedProperties: true` を追加、`save()` の catch に `console.error` を追加
  - flashcard.html (routine-app) と index.html (lin-pay/palavras) 両方に反映してプッシュ済み
- フィットネスタブに「推移」タブを追加（記録/週次/推移/助言/今日 の5タブ構成）
  - 体重・各筋トレ種目の最大重量・ラン距離/ペース/平均心拍をスパークライン（インラインSVG）で表示
  - 懸垂はpullupA/B/C（曜日別ID）を「懸垂」名で統合
  - 各カードに最新値・回数・期間・初回比較デルタ（改善=緑/悪化=赤、ペース・心拍・体重は低い方が改善扱い）
  - 「アドバイス」ラベルを「助言」に短縮（5タブ収納のため）、tabのfont-sizeを11pxに縮小
- ルーティンタブに日付ナビゲーション（◀ 日付 ▶ ●）を追加し、過去日のタスク完了/未完了を修正可能に
  - 過去日ではタスク追加・編集・削除・ストリーク表示を非表示にし、チェックのON/OFFのみ操作可能
  - 未来日へは進めない制限付き

## 未完了・次にやること
- **トレーニング記録の入力方式をユーザーに確認中**（2026-10-23）。案1（おすすめ）: ルーティンの「トレーニング」✓に一本化し、トレーニングタブは「今日のメニュー＋前回の数字」を見る画面にする。数字は前回値を入れておいて「前回どおり」の1タップで記録、重さを上げた種目だけ直す。トレーニングタブで記録したらルーティンの✓も自動で付ける。使っていない体重・食事メモ欄は外す。案2: トレーニングタブを廃止してルーティンの✓だけにする（過去データは Firestore に残す）
- 通知は実機まで疎通確認済み
- 運用上の注意: 送信元が Mac なのでスリープ／電源オフ中は送信されない（ユーザーは常時起動運用）。launchd はスリープ中の missed job を起床時に実行するが、予定時刻から45分(`NWIN`)以上経っていれば送らない

## 重要な設計判断・注意点
- git config (user.name, user.email) はリポジトリローカルに設定（グローバル未変更）
- gh CLIは ~/bin/gh にインストール、~/.bashrc にPATH追加済み
- force pushで既存リポジトリの内容を上書き済み（データはFirestoreなので影響なし）
- Firebaseサービスアカウントキーは `.gitignore` で除外必須（秘密鍵）
- `vapid.json`（Web Push の VAPID 鍵ペア）も `.gitignore` の `*.json` で除外。**失うと全端末の購読が無効になり、公開鍵の貼り直し＋再購読が必要**なのでバックアップ推奨
- 通知の LaunchAgent は `com.routine-app.notify`（15分おき）。`launchctl list | grep routine-app` で確認、ログは `reports/notify.log`
- スケジュール管理: `launchctl list com.routine-app.fitness-report` で確認。plistは `~/Library/LaunchAgents/com.routine-app.fitness-report.plist`
- palavras (`lin-pay/palavras`) のローカルクローンは Mac 側には無く、デプロイは VM 側で行う運用。Mac から修正する場合は一時ディレクトリに `git clone https://github.com/lin-pay/palavras.git` してコピー → push → 削除する（gh CLI も Mac には無い）。なお Mac でクローンするとコミット committer が `nagaoka@MacBook-Pro.local` になる点に注意（必要なら `git -C <clone> commit --amend --reset-author` で修正）
