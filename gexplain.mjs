/**
 * 技術士の過去問の解説を Claude で作る常駐スクリプト（Mac の LaunchAgent com.routine-app.gexplain で動かす）
 *
 *   - users/{uid}/data/gprog を見張り、間違えたことのある問題（r に x がある）で解説がまだないものを、1問ずつ作る
 *   - アプリの結果画面で頼まれた問題（users/{uid}/data/gxreq の q[k] = 頼んだ時刻）も作る（正解した問題・作り直し）
 *   - 問題の画像（users/{uid}/gq/{k}）と公式の正答（data/gq_idx）を claude -p に渡す。Claude Code の既定のシステム
 *     プロンプトとツールは使わない（--system-prompt・--tools ""）ので、1問 約3千トークンの入力で済む
 *   - 結果は users/{uid}/gx/{k} = { s:'run'|'ok'|'err', text, at, model, cost, ms }。アプリはこれを表示する
 *
 * 使い方:
 *   node gexplain.mjs              常駐（LaunchAgent から）
 *   node gexplain.mjs --once       今ある分を作って終わる
 *   node gexplain.mjs --dry        作る予定の問題を表示するだけ
 *   node gexplain.mjs --key R7_shinrin_03   1問だけ作って表示する（Firestore には書かない）
 */
import { initializeApp, cert } from 'firebase-admin/app';
import { getFirestore } from 'firebase-admin/firestore';
import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { spawn } from 'child_process';
import { tmpdir } from 'os';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const keyPath = join(__dirname, 'routine-app-5eff3-firebase-adminsdk-fbsvc-c788b35d58.json');
const statePath = join(__dirname, 'reports', 'gexplain_state.json');   // 24時間に作った数（上限の判定用）
const CLAUDE = '/Users/nagaoka/.local/bin/claude';
const MODEL = 'claude-opus-5-5';
const EFFORT = 'medium';
const DAY_CAP = 100;          // 24時間に作る上限（費用の歯止め。1問 約$0.04）
const RESCAN = 10 * 60e3;     // 見張りが止まっていても拾えるよう、10分ごとに読み直す
const TIMEOUT = 5 * 60e3;     // 1問にかける時間の上限
const STALE = 15 * 60e3;      // 'run' のまま残った解説（途中で止まった）を作り直すまでの時間
// CLAUDE.md を拾わないよう、リポジトリの外の空のフォルダで claude を動かす
const WORK = join(tmpdir(), 'routine-gexplain');

const args = process.argv.slice(2);
const ONCE = args.includes('--once'), DRY = args.includes('--dry');
const ONE = args.includes('--key') ? args[args.indexOf('--key') + 1] : null;

const app = initializeApp({ credential: cert(JSON.parse(readFileSync(keyPath, 'utf8'))) });
const db = getFirestore(app);
const log = (...a) => console.log(new Date().toISOString(), ...a);

const SUBJ = { shinrin: '森林部門 専門科目', kiso: '基礎科目', tekisei: '適性科目' };
const GRP = ['設計・計画', '情報・論理', '解析', '材料・化学・バイオ', '環境・エネルギー・技術'];
const CIRC = '①②③④⑤';
const SYSTEM = `あなたは技術士第一次試験の受験指導の講師です。受験者が解いた過去問について、日本語で解説を書きます。
- 添付の画像は、日本技術士会が公開している過去問の1問です。
- 公式の正答はユーザーが示す番号です。必ずそれを正答として扱い、ほかの番号を正答だと書かないでください。
- 次の形式で書きます。見出しはこのまま使い、マークダウンの記号（#、*、|、\`\`\`）は使いません。
【ポイント】この問題で問われていること（1〜2文）
【正答 ○】正答の理由。「最も不適切なもの」を選ぶ問題なら、どこがどう誤りかを書く。計算問題は途中の式も書く
【選択肢】①〜⑤を1行ずつ、「① 適切。…」「② 不適切。…」の形で、正誤と理由を1〜2文
【覚えること】試験に役立つ要点を2〜3点（制度・用語・数値・公式）
- 確かでない数値・年・名称は書かず、推測で断定しない。
- 全体で800字程度まで。`;

let uid = null, map = {}, prog = null, req = {}, busy = false;
const gx = {};                // k → { s, at }（解説の状態だけ。本文は読まない）
const ready = { idx: false, prog: false, req: false, gx: false };

function loadState() { try { return JSON.parse(readFileSync(statePath, 'utf8')); } catch (e) { return { done: [] }; } }
function recent() { const st = loadState(), now = Date.now(); return st.done.filter(t => now - t < 864e5); }
function markDone() { const d = [...recent(), Date.now()]; mkdirSync(dirname(statePath), { recursive: true }); writeFileSync(statePath, JSON.stringify({ done: d })); }

function indexMap(idx) { const m = {}; (idx?.sets || []).forEach(s => s.qs.forEach(q => { m[q.k] = { s, q }; })); return m; }

// 作る問題: 頼まれたもの（新しいものから）→ 間違えたことのあるもの（答えた順）
function wanted() {
  const now = Date.now(), need = k => {
    if (!map[k]) return false;
    const g = gx[k];
    if (!g) return true;
    if (g.s === 'run') return now - (g.at || 0) > STALE;
    return !!req[k] && req[k] > (g.at || 0);   // 作ったあと（失敗したあと）にもう一度頼まれた
  };
  const asked = Object.keys(req).sort((a, b) => req[b] - req[a]);
  const wrong = Object.entries(prog?.q || {}).filter(([, p]) => (p.r || '').includes('x')).map(([k]) => k);
  return [...new Set([...asked, ...wrong])].filter(need);
}

function claude(input) {
  return new Promise((resolve, reject) => {
    mkdirSync(WORK, { recursive: true });
    const p = spawn(CLAUDE, ['-p', '--input-format', 'stream-json', '--output-format', 'stream-json', '--verbose',
      '--tools', '', '--strict-mcp-config', '--system-prompt', SYSTEM, '--model', MODEL, '--effort', EFFORT, '--no-session-persistence'],
      // 1問ごとに画像が違い、同じ前置きの再利用がないので、キャッシュの書き込み（割増）をしない
      { cwd: WORK, env: { ...process.env, DISABLE_PROMPT_CACHING: '1' } });
    let out = '', err = '';
    const timer = setTimeout(() => { p.kill('SIGTERM'); reject(new Error('timeout')); }, TIMEOUT);
    p.stdout.on('data', d => { out += d; });
    p.stderr.on('data', d => { err += d; });
    p.on('error', e => { clearTimeout(timer); reject(e); });
    p.on('close', code => {
      clearTimeout(timer);
      const r = out.split('\n').filter(Boolean).map(l => { try { return JSON.parse(l); } catch (e) { return null; } }).filter(x => x && x.type === 'result').pop();
      if (!r || r.is_error || r.subtype !== 'success' || !r.result) return reject(new Error(`claude exit ${code}: ${(r && (r.result || r.subtype)) || err.slice(-300) || 'no result'}`));
      resolve({ text: r.result.trim(), cost: r.total_cost_usd || 0, ms: r.duration_ms || 0 });
    });
    p.stdin.end(JSON.stringify(input) + '\n');
  });
}

async function explain(k) {
  const { s, q } = map[k];
  const im = (await db.doc(`users/${uid}/gq/${k}`).get()).data();
  if (!im || !im.img) throw new Error('問題の画像がない');
  const label = `${s.yl} 技術士第一次試験 ${SUBJ[s.s]}${s.s === 'kiso' && q.g ? `（${q.g}群 ${GRP[q.g - 1]}）` : ''} ${q.no}`;
  const a = Array.isArray(q.a) ? q.a : [q.a];
  const ans = a.map(n => CIRC[n - 1]).join('と') + (a.length > 1 ? '（どれを選んでも正解扱い）' : '');
  return claude({ type: 'user', message: { role: 'user', content: [
    { type: 'image', source: { type: 'base64', media_type: 'image/png', data: im.img.split(',', 2)[1] } },
    { type: 'text', text: `この問題（${label}）の公式の正答は ${ans} です。解説を書いてください。` }] } });
}

async function pump() {
  if (busy || !Object.values(ready).every(Boolean)) return;
  busy = true;
  try {
    for (;;) {
      const k = wanted()[0];
      if (!k) break;
      if (recent().length >= DAY_CAP) { log(`24時間の上限 ${DAY_CAP}問に達したので待つ（残り ${wanted().length}問）`); break; }
      const ref = db.doc(`users/${uid}/gx/${k}`), t0 = Date.now();
      gx[k] = { s: 'run', at: t0 };
      await ref.set({ s: 'run', at: t0 });
      let res = null, last = null;
      for (let i = 0; i < 2 && !res; i++) {
        try { res = await explain(k); } catch (e) { last = e; log(`${k}: 失敗 ${i + 1}回目 ${e.message}`); await new Promise(r => setTimeout(r, 20e3)); }
      }
      const at = Date.now();
      if (res) {
        gx[k] = { s: 'ok', at };
        await ref.set({ s: 'ok', text: res.text, at, model: MODEL, cost: res.cost, ms: res.ms });
        markDone();
        log(`${k}: 作成 ${Math.round(res.ms / 1000)}秒 $${res.cost.toFixed(4)} ${res.text.length}字`);
      } else {
        gx[k] = { s: 'err', at };
        await ref.set({ s: 'err', at, msg: String(last && last.message || '').slice(0, 300) });
      }
    }
  } catch (e) { log('エラー', e.message); }
  busy = false;
  if (ONCE) process.exit(0);
}
// 4つの見張りの最初の読み込みがそろってから動く
function tick() {
  if (!Object.values(ready).every(Boolean)) return;
  if (DRY) { console.log(wanted().join('\n') || '(作る問題なし)'); process.exit(0); }
  pump();
}

const users = await db.collection('users').listDocuments();
for (const u of users) if ((await u.collection('data').doc('gq_idx').get()).exists) { uid = u.id; break; }
if (!uid) { log('過去問の索引（data/gq_idx）のあるユーザーがいない'); process.exit(1); }
const base = `users/${uid}`;

if (ONE) {
  map = indexMap((await db.doc(`${base}/data/gq_idx`).get()).data());
  const r = await explain(ONE);
  console.log(r.text, `\n\n(${Math.round(r.ms / 1000)}秒 $${r.cost.toFixed(4)})`);
  process.exit(0);
}

// 見張り。どれかが止まったらいったん終わり、LaunchAgent（KeepAlive）に立ち上げ直してもらう
const fail = what => e => { log(`見張りのエラー（${what}）`, e.message); process.exit(1); };
db.doc(`${base}/data/gq_idx`).onSnapshot(s => { map = indexMap(s.data()); ready.idx = true; tick(); }, fail('gq_idx'));
db.doc(`${base}/data/gprog`).onSnapshot(s => { prog = s.exists ? s.data() : null; ready.prog = true; tick(); }, fail('gprog'));
db.doc(`${base}/data/gxreq`).onSnapshot(s => { req = (s.exists && s.data().q) || {}; ready.req = true; tick(); }, fail('gxreq'));
db.collection(`${base}/gx`).onSnapshot(qs => {
  qs.docChanges().forEach(c => { if (c.type === 'removed') delete gx[c.doc.id]; else { const d = c.doc.data(); gx[c.doc.id] = { s: d.s, at: d.at }; } });
  ready.gx = true; tick();
}, fail('gx'));
setInterval(async () => {
  try {
    prog = (await db.doc(`${base}/data/gprog`).get()).data() || null;
    req = (await db.doc(`${base}/data/gxreq`).get()).data()?.q || {};
    tick();
  } catch (e) { log('読み直しのエラー', e.message); }
}, RESCAN);
log(`開始 uid=${uid.slice(0, 6)}… model=${MODEL} effort=${EFFORT}`);
