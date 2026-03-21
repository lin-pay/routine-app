import { initializeApp, cert } from 'firebase-admin/app';
import { getFirestore } from 'firebase-admin/firestore';
import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const keyPath = join(__dirname, 'routine-app-5eff3-firebase-adminsdk-fbsvc-c788b35d58.json');

// Firebase Admin 初期化
const app = initializeApp({ credential: cert(JSON.parse(readFileSync(keyPath, 'utf8'))) });
const db = getFirestore(app);

// ユーザー検索 & フィットネスデータ取得
const usersSnap = await db.collection('users').listDocuments();
if (usersSnap.length === 0) { console.error('ユーザーが見つかりません'); process.exit(1); }

const uid = usersSnap[0].id;
const fitnessDoc = await db.doc(`users/${uid}/data/fitness`).get();
if (!fitnessDoc.exists) { console.error('フィットネスデータがありません'); process.exit(1); }

const fit = fitnessDoc.data();

// 直近4週間のデータを抽出
const today = new Date();
const fourWeeksAgo = new Date(today);
fourWeeksAgo.setDate(today.getDate() - 28);
const cutoff = fourWeeksAgo.toISOString().slice(0, 10);

function filterByDate(obj) {
  const filtered = {};
  for (const [date, val] of Object.entries(obj || {})) {
    if (date >= cutoff) filtered[date] = val;
  }
  return filtered;
}

const recentData = {
  workouts: filterByDate(fit.workouts),
  runs: filterByDate(fit.runs),
  weight: filterByDate(fit.weight),
  meals: filterByDate(fit.meals),
};

// スケジュール情報
const schedule = {
  月: '筋トレA (バックスクワット, ブルガリアンスプリットスクワット, 懸垂, アブローラー)',
  火: 'ランニング',
  水: '筋トレB (ベンチプレス, OHP, 懸垂, ダンベルロウ)',
  木: 'ランニング',
  金: '休養',
  土: '筋トレC (デッドリフト, RDL, 懸垂, ハンギングレッグレイズ)',
  日: 'ランニング',
};

const prompt = `あなたはフィットネスコーチです。以下の直近4週間のトレーニングデータを分析し、日本語で週次アドバイスレポートを作成してください。

## トレーニングスケジュール
${JSON.stringify(schedule, null, 2)}

## 直近4週間のデータ
### 筋トレ記録 (workouts)
各種目のセットごとの重量(w)とレップ数(r)
${JSON.stringify(recentData.workouts, null, 2)}

### ランニング記録 (runs)
距離(km), 時間(min), 心拍数(hr), メモ
${JSON.stringify(recentData.runs, null, 2)}

### 体重 (kg)
${JSON.stringify(recentData.weight, null, 2)}

### 食事メモ
${JSON.stringify(recentData.meals, null, 2)}

## レポートに含めてほしい内容
1. **今週のハイライト**: 良かった点
2. **重量・レップ数の推移**: 各種目の進捗（伸びている/停滞/下がっている）
3. **ランニングの推移**: ペース・距離の変化
4. **体重の推移**: トレンド
5. **改善アドバイス**: 具体的な提案（重量設定、フォーム、頻度、休養など）
6. **来週の目標提案**: 数値目標を含む

簡潔に、データに基づいた具体的なアドバイスをお願いします。`;

// Claude CLIでレポート生成
const reportDir = join(__dirname, 'reports');
mkdirSync(reportDir, { recursive: true });
const dateStr = today.toISOString().slice(0, 10);
const promptPath = join(reportDir, `.prompt-${dateStr}.txt`);
const reportPath = join(reportDir, `fitness-report-${dateStr}.md`);

// プロンプトをファイル経由で渡す（シェルエスケープ問題を回避）
writeFileSync(promptPath, prompt);
console.log('Claude CLIでレポート生成中...');
const report = execSync(
  `cat "${promptPath}" | claude -p`,
  { encoding: 'utf8', maxBuffer: 1024 * 1024, timeout: 180000 }
);

writeFileSync(reportPath, `# フィットネス週次レポート (${dateStr})\n\n${report}`);

// Firestoreにレポートを保存（アプリから閲覧用）
const reportData = { content: report.trim(), date: dateStr, createdAt: new Date().toISOString() };
const reportsDoc = await db.doc(`users/${uid}/data/reports`).get();
const existing = reportsDoc.exists ? reportsDoc.data().items || [] : [];
existing.unshift(reportData);
// 直近12件（約3ヶ月分）のみ保持
await db.doc(`users/${uid}/data/reports`).set({ items: existing.slice(0, 12) });
console.log(`レポート生成完了: ${reportPath} (Firestoreにも保存済み)`);
