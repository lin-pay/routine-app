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
- 曜日スケジュール: 月=筋トレB, 火=ラン, 水=筋トレA, 木=ラン, 金=休養, 土=筋トレC, 日=ラン（2026-06-09に月⇔水を入れ替え）
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
- **ルーティンタブに通知機能と継続性向上機能を追加**（2026-09-12）
  - 新規ファイル: `sw.js`（Service Worker）、`notify.mjs`（FCMプッシュ送信）、`com.routine-app.notify.plist`（LaunchAgentテンプレート）、`docs/notifications.md`（設定手順）
  - **通知**（2層構成。詳細は `docs/notifications.md`）
    - ① 前面通知: 設定不要。60秒interval + `visibilitychange` で予定時刻を監視し、`sw.js` の `showNotification()` で表示。1日1回の制御は `localStorage['daily_notif_log']`
    - ② プッシュ通知: `index.html` の `VAPID_KEY` に Firebase の ウェブプッシュ証明書の公開鍵を入れると有効化。端末トークンは `users/{uid}/data/settings.pushTokens` に merge 書き込み。送信は `notify.mjs`（Firebase Admin SDK）を LaunchAgent で15分おき実行、送信済みフラグは `users/{uid}/data/notifLog`
    - **VAPID_KEY は未設定**。設定するまでは前面通知のみ動作する（設定画面にその旨を表示）
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
  - 統計ロジックはNodeハーネスで検証（ストリーク/最長/達成率/パーフェクトデー/空データ）、UIはheadless Chromeでスクリーンショット確認、28ステップのクリック操作スモークテストをPASS
  - **未デプロイ**（コミット・push はしていない）

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
- **通知機能のデプロイ**: `index.html` / `sw.js` / `notify.mjs` / `com.routine-app.notify.plist` / `docs/notifications.md` が未コミット。commit + push で GitHub Pages に反映される
- **プッシュ通知の有効化（任意）**: Firebase Console → routine-app-5eff3 → プロジェクトの設定 → Cloud Messaging → ウェブプッシュ証明書 で鍵ペアを生成し、`index.html` の `const VAPID_KEY=''` に貼る。その後アプリで通知を許可して端末トークンを登録 → `cp com.routine-app.notify.plist ~/Library/LaunchAgents/ && launchctl bootstrap gui/$(id -u) ...` で送信を常駐（詳細は `docs/notifications.md`）
  - 制約: 送信元がMacなのでスリープ/電源オフ中は送信されない。常時配信するなら Cloud Functions + Cloud Scheduler（Blazeプラン必須）への移行が必要

## 重要な設計判断・注意点
- git config (user.name, user.email) はリポジトリローカルに設定（グローバル未変更）
- gh CLIは ~/bin/gh にインストール、~/.bashrc にPATH追加済み
- force pushで既存リポジトリの内容を上書き済み（データはFirestoreなので影響なし）
- Firebaseサービスアカウントキーは `.gitignore` で除外必須（秘密鍵）
- スケジュール管理: `launchctl list com.routine-app.fitness-report` で確認。plistは `~/Library/LaunchAgents/com.routine-app.fitness-report.plist`
- palavras (`lin-pay/palavras`) のローカルクローンは Mac 側には無く、デプロイは VM 側で行う運用。Mac から修正する場合は一時ディレクトリに `git clone https://github.com/lin-pay/palavras.git` してコピー → push → 削除する（gh CLI も Mac には無い）。なお Mac でクローンするとコミット committer が `nagaoka@MacBook-Pro.local` になる点に注意（必要なら `git -C <clone> commit --amend --reset-author` で修正）
