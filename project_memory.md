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
- トレーナーアドバイス（「アドバイス」タブ）: 毎週金曜8:00に自動生成、Firestore保存（直近12件）
  - 生成スクリプト: `fitness-report.mjs`（Firebase Admin SDK + Claude CLI）
  - systemd user timer (`fitness-report.timer`) で自動実行、`Persistent=true` でVM停止時もキャッチアップ
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
- 筋トレCのファーマーズウォーク → ハンギングレッグレイズに変更（スペース不要の種目へ）
- トレーナーアドバイス自動生成機能を追加
  - `fitness-report.mjs`: Firebase Admin SDK でFirestoreからデータ取得 → Claude CLI でレポート生成 → Firestoreに保存
  - アプリに「アドバイス」タブを追加（過去レポート閲覧、前後ナビゲーション付き）
  - systemd user timer で毎週金曜8:00自動実行（`Persistent=true` でVM停止時キャッチアップ対応）
  - `loginctl enable-linger` で再起動後もタイマー自動起動
- `.gitignore` 追加（サービスアカウントキー、node_modules、reports を除外）

## 未完了・次にやること
- 特になし（仕様変更・機能追加があれば随時対応）

## 重要な設計判断・注意点
- git config (user.name, user.email) はリポジトリローカルに設定（グローバル未変更）
- gh CLIは ~/bin/gh にインストール、~/.bashrc にPATH追加済み
- force pushで既存リポジトリの内容を上書き済み（データはFirestoreなので影響なし）
- Firebaseサービスアカウントキーは `.gitignore` で除外必須（秘密鍵）
- systemd user timer 管理: `systemctl --user {status|start|stop} fitness-report.timer`
