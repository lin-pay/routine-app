#!/usr/bin/env node
/**
 * Daily — ルーティン未完了リマインダーのプッシュ送信
 *
 *   node notify.mjs            通知時刻を過ぎていて未送信なら送る（LaunchAgent から15分おきに起動）
 *   node notify.mjs --dry      送信せず、何を送るかだけ表示
 *   node notify.mjs --test     時刻判定を無視してテスト通知を1通送る
 *
 * 前提: index.html の VAPID_KEY を設定し、アプリ側で通知を許可して端末トークンを
 *       users/{uid}/data/settings.pushTokens に登録しておくこと（docs/notifications.md 参照）
 */
import { initializeApp, cert } from 'firebase-admin/app';
import { getFirestore, FieldValue } from 'firebase-admin/firestore';
import { getMessaging } from 'firebase-admin/messaging';
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const keyPath = join(__dirname, 'routine-app-5eff3-firebase-adminsdk-fbsvc-c788b35d58.json');
const APP_URL = 'https://lin-pay.github.io/routine-app/';
const ICON = APP_URL + 'icon-daily.png';
const NWIN = 45;   // 予定時刻からこの分数以内なら送る（index.html と揃える）

const DRY = process.argv.includes('--dry');
const TEST = process.argv.includes('--test');

const app = initializeApp({ credential: cert(JSON.parse(readFileSync(keyPath, 'utf8'))) });
const db = getFirestore(app);
const msg = getMessaging(app);

const DAY_MAP = { 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 0: 6 };   // 0=月 … 6=日
const fmtD = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const hm2m = v => { const a = String(v || '').split(':'); return (parseInt(a[0], 10) || 0) * 60 + (parseInt(a[1], 10) || 0); };
const nameList = (ts, max) => ts.slice(0, max).map(t => t.name).join('・') + (ts.length > max ? ` ほか${ts.length - max}件` : '');

// 該当日ベースの連続達成日数（index.html の getStreak と同じ判定）
function getStreak(t, comps) {
  let s = 0;
  const d = new Date();
  if (t.days.includes(DAY_MAP[d.getDay()]) && comps[`${fmtD(d)}:${t.id}`]) s = 1;
  d.setDate(d.getDate() - 1);
  for (let i = 0; i < 365; i++) {
    if (t.days.includes(DAY_MAP[d.getDay()])) {
      if (comps[`${fmtD(d)}:${t.id}`]) s++; else break;
    }
    d.setDate(d.getDate() - 1);
  }
  return s;
}

async function send(uid, tokens, title, body, tag) {
  console.log(`[${uid}] ${tag}: ${title} / ${body} → ${tokens.length}台`);
  if (DRY) return;
  const res = await msg.sendEachForMulticast({
    tokens,
    webpush: {
      notification: { title, body, icon: ICON, badge: ICON, tag },
      fcmOptions: { link: APP_URL },
    },
  });
  // 失効したトークンは掃除する（アプリ側の setDoc と衝突しないよう field 単位で削除）
  await Promise.all(res.responses.map(async (r, i) => {
    if (r.success) return;
    const code = r.error?.code || '';
    console.warn(`  送信失敗: ${code}`);
    if (code.includes('registration-token-not-registered') || code.includes('invalid-argument')) {
      await db.doc(`users/${uid}/data/settings`).update({ [`pushTokens.${tokens[i]}`]: FieldValue.delete() }).catch(() => {});
    }
  }));
  console.log(`  成功 ${res.successCount} / 失敗 ${res.failureCount}`);
}

async function run() {
  const users = await db.collection('users').listDocuments();
  const now = new Date(), ds = fmtD(now), cur = now.getHours() * 60 + now.getMinutes();
  const due = m => { const d = cur - m; return TEST || (d >= 0 && d < NWIN); };

  for (const u of users) {
    const uid = u.id;
    const [setSnap, taskSnap, compSnap, logSnap] = await Promise.all([
      db.doc(`users/${uid}/data/settings`).get(),
      db.doc(`users/${uid}/data/tasks`).get(),
      db.doc(`users/${uid}/data/completions`).get(),
      db.doc(`users/${uid}/data/notifLog`).get(),
    ]);
    const settings = setSnap.exists ? setSnap.data() : {};
    const n = settings.notif || {};
    const tokens = Object.keys(settings.pushTokens || {});
    if (!n.on) { console.log(`[${uid}] 通知OFF — スキップ`); continue; }
    if (!tokens.length) { console.log(`[${uid}] 端末トークンなし — スキップ`); continue; }

    const tasks = (taskSnap.exists ? taskSnap.data().items : []) || [];
    const comps = (compSnap.exists ? compSnap.data().entries : {}) || {};
    const log = (logSnap.exists ? logSnap.data() : {}) || {};
    const sent = [];
    const mark = k => { sent.push(k); log[k] = 1; };

    const di = DAY_MAP[now.getDay()];
    const todays = tasks.filter(t => t.days.includes(di));
    const left = todays.filter(t => !comps[`${ds}:${t.id}`]);

    if (TEST) {
      await send(uid, tokens, '🔔 テスト通知', `未完了 ${left.length}件 / 本日 ${todays.length}件`, 'test');
      continue;
    }

    if (n.morningOn && todays.length && due(hm2m(n.morning)) && !log[`${ds}:am`]) {
      mark(`${ds}:am`);
      await send(uid, tokens, '☀️ 今日のルーティン', `${todays.length}件 — ${nameList(todays, 3)}`, 'am');
    }

    if (n.taskOn) {
      for (const t of todays) {
        const k = `${ds}:t:${t.id}`;
        if (!t.time || comps[`${ds}:${t.id}`] || log[k] || !due(hm2m(t.time))) continue;
        const sk = getStreak(t, comps);
        mark(k);
        await send(uid, tokens, `${t.icon} ${t.name}`,
          sk > 0 ? `🔥 ${sk}日連続中 — 今日で${sk + 1}日目` : 'いま実行する時間です', `t${t.id}`);
      }
    }

    if (n.eveningOn && left.length && due(hm2m(n.evening)) && !log[`${ds}:pm`]) {
      const risky = left.map(t => ({ t, sk: getStreak(t, comps) })).filter(x => x.sk >= 3).sort((a, b) => b.sk - a.sk);
      mark(`${ds}:pm`);
      await send(uid, tokens, '🌙 未完了のルーティン',
        risky.length ? `あと${left.length}件 — ⚠️ ${risky[0].t.name} の${risky[0].sk}日連続が途切れます`
                     : `あと${left.length}件 — ${nameList(left, 3)}`, 'pm');
    }

    if (!sent.length) { console.log(`[${uid}] 送信対象なし`); continue; }
    if (DRY) continue;
    // 当日ぶんだけ残す（古いキーは捨てる）
    const pruned = {};
    for (const k of Object.keys(log)) if (k.slice(0, 10) >= ds) pruned[k] = 1;
    await db.doc(`users/${uid}/data/notifLog`).set(pruned);
  }
}

run().then(() => process.exit(0)).catch(e => { console.error(e); process.exit(1); });
