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
  - データ構造: `users/{uid}/data/{tasks|completions|fitness|reports|flashcards}`

#### ルーティンタブ (✅)
- 曜日チェックボックス（毎日・平日・週末プリセット）
- 今日該当タスクのみ表示
- ストリーク: 該当日ベースで連続判定
- カテゴリなし（フラット）、完了済みを下に自動ソート
- 進捗リング

#### フィットネスタブ (💪)
- デザイン: ダークグリーン + JetBrains Mono（fitness_tracker.jsx ベース）
- 曜日スケジュール: 月=筋トレA, 火=ラン, 水=筋トレB, 木=ラン, 金=休養, 土=筋トレC, 日=ラン
- 筋トレA/B/C: 各3〜4種目、3セット、重量×レップ記録
- ラン: 距離・時間・心拍・ペース（自動計算）・メモ
- 体重・食事メモ
- 週次サマリー（4カラムグリッド、最大重量、日別ログ）
- 推移タブ: 体重・各種目の最大重量（懸垂はA/B/C統合）・ラン距離/ペース/平均心拍をスパークラインで表示。改善方向（重量↑/ペース↓など）を緑、悪化方向を赤で表示
- トレーナーアドバイス（「アドバイス」タブ）: 毎週金曜8:00に自動生成、Firestore保存（直近12件）
  - 生成スクリプト: `fitness-report.mjs`（Firebase Admin SDK + Claude CLI）
  - Mac LaunchAgent (`com.routine-app.fitness-report`) で自動実行（毎週金曜 19:40 JST）— crontabから移行済み(2026-04-07)
  - ログ: `reports/cron.log`
  - launchdはスリープ中のmissed jobを起床時に自動実行する（cronのPersistent相当）
  - サービスアカウントキー: `routine-app-5eff3-firebase-adminsdk-*.json`（.gitignoreで除外）

#### その他ファイル
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
- フィットネスタブに「推移」タブを追加（記録/週次/推移/助言/今日 の5タブ構成）
  - 体重・各筋トレ種目の最大重量・ラン距離/ペース/平均心拍をスパークライン（インラインSVG）で表示
  - 懸垂はpullupA/B/C（曜日別ID）を「懸垂」名で統合
  - 各カードに最新値・回数・期間・初回比較デルタ（改善=緑/悪化=赤、ペース・心拍・体重は低い方が改善扱い）
  - 「アドバイス」ラベルを「助言」に短縮（5タブ収納のため）、tabのfont-sizeを11pxに縮小
- ルーティンタブに日付ナビゲーション（◀ 日付 ▶ ●）を追加し、過去日のタスク完了/未完了を修正可能に
  - 過去日ではタスク追加・編集・削除・ストリーク表示を非表示にし、チェックのON/OFFのみ操作可能
  - 未来日へは進めない制限付き

## 未完了・次にやること
- 特になし

## 重要な設計判断・注意点
- git config (user.name, user.email) はリポジトリローカルに設定（グローバル未変更）
- gh CLIは ~/bin/gh にインストール、~/.bashrc にPATH追加済み
- force pushで既存リポジトリの内容を上書き済み（データはFirestoreなので影響なし）
- Firebaseサービスアカウントキーは `.gitignore` で除外必須（秘密鍵）
- スケジュール管理: `launchctl list com.routine-app.fitness-report` で確認。plistは `~/Library/LaunchAgents/com.routine-app.fitness-report.plist`
