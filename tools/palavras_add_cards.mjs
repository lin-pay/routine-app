// words.json にあって Firestore の単語帳（users/*/data/flashcards）に無い語を、import.html と同じ形のカードで追加する
// 使い方（routine-app で）: node tools/palavras_add_cards.mjs routine-app-5eff3-firebase-adminsdk-*.json words.json  → 追加予定の確認だけ
//                        末尾に --apply を付けると追加する（11語以上は止める）
import { initializeApp, cert } from 'firebase-admin/app';
import { getFirestore } from 'firebase-admin/firestore';
import { readFileSync } from 'fs';
const [keyPath, wordsPath, apply] = process.argv.slice(2);
const app = initializeApp({ credential: cert(JSON.parse(readFileSync(keyPath, 'utf8'))) });
const db = getFirestore(app);
const RAW = JSON.parse(readFileSync(wordsPath, 'utf8'));
const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Sao_Paulo' }).format(new Date());
const users = await db.collection('users').listDocuments();
for (const u of users) {
  const ref = db.doc(`users/${u.id}/data/flashcards`);
  await db.runTransaction(async tx => {
    const snap = await tx.get(ref);
    if (!snap.exists) return;
    const existing = snap.data().cards || [];
    const have = new Set(existing.map(c => (c.pt || '').toLowerCase().trim()));
    const seen = new Set();
    const add = RAW.filter(w => { const k = w[0].toLowerCase().trim(); if (seen.has(k) || have.has(k)) return false; seen.add(k); return true; });
    console.log(u.id.slice(0, 6) + '…', 'existing=' + existing.length, 'toAdd=' + add.map(w => w[0]).join(','), 'today=' + today);
    if (apply !== '--apply' || add.length === 0) return;
    if (add.length > 10) throw new Error('too many new words: ' + add.length);
    const now = Date.now();
    const cards = add.map((w, i) => ({
      id: 'fc_' + now + '_' + i + '_' + Math.random().toString(36).slice(2, 6),
      pt: w[0], ja: w[1], note: w[2] || '', ex: w[3] || '',
      ef: 2.5, interval: 0, reps: 0,
      nextReview: today, rEf: 2.5, rInterval: 0, rReps: 0, rNextReview: today, createdAt: now + i,
    }));
    tx.update(ref, { cards: [...existing, ...cards] });
    console.log('added', cards.length, '→ total', existing.length + cards.length);
  });
}
