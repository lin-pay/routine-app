#!/usr/bin/env python3
"""技術士試験に関わる公式ページの更新を見張り、変わったら Telegram に知らせる（gwatch・2026-11-01 新設）

  - 対象は gwatch.json（日本技術士会・文部科学省の技術士分科会・林野庁）。1日1回、LaunchAgent com.routine-app.gwatch で動かす
  - 見方は4種類
      links … ページ内のリンク（URL と文字）。新しく出たリンクと、文字が変わったリンクを知らせる（新しいお知らせ・資料・PDF）
      rss   … RSS の項目。新しい項目を知らせる（keywords に当たるものだけ）
      text  … ページの本文（start〜end の間）。増えた行・消えた行を知らせる（Q&A の書き換えなど）
      file  … PDF などのファイル。ETag・Last-Modified・サイズが変わったら中身を取り、ハッシュが違えば知らせる
  - 初めての対象は今の状態を覚えるだけ（いちばん最初の実行では「見張りを始めました」を1通送る）
  - 取れない日（エラー・リンクが急に減った）が3回続いたら1回だけ知らせる。送れなかった知らせは次の実行で送り直す
  - 状態 reports/gwatch_state.json、ログ reports/gwatch.log、知らせた変化の履歴 reports/gwatch_changes.jsonl
  - Telegram は trading-agent の trading.telegram_notify を読み取りで借りる（Asset の event_watch と同じ）

使い方（routine-app で）:
  python3 gwatch.py               いつもの実行（変化があれば送る）
  python3 gwatch.py --dry         送らずに表示する（状態も保存しない）
  python3 gwatch.py --list        各対象から取れたもの（件数と先頭）を表示する（保存も送信もしない）
  python3 gwatch.py --only ID     その対象だけ（--dry・--list と組み合わせる）
"""
import argparse
import difflib
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent
TRADING_AGENT = Path.home() / "trading-agent"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) routine-app-gwatch/1.0"
JST = timezone(timedelta(hours=9))
FAIL_ALERT = 3          # 取れない日がこの回数続いたら知らせる
SHRINK = 0.3            # リンクがこの割合を下回るほど減ったら、取れていない（エラーページ・作り替え）とみなす
TITLE_LOOKUPS = 8       # 新しいリンクの文字が短いとき、リンク先の <title> を読みに行く回数の上限（1回の実行で）
MSG_LIMIT = 3800        # Telegram は 4096 字まで
GENERIC = {"開催案内", "議事録", "議事要旨", "配付資料", "HTML版", "こちら", "詳細", "PDF", "資料", "概要"}
DROP_QUERY = {"ref", "utm_source", "utm_medium", "utm_campaign"}

STATE = ROOT / "reports" / "gwatch_state.json"
LOG = ROOT / "reports" / "gwatch.log"
CHANGES = ROOT / "reports" / "gwatch_changes.jsonl"


def now():
    return datetime.now(JST)


def log(msg):
    line = f"{now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


# ── 取得 ──
_last_hit = {}


def fetch(url, method="GET", tries=2):
    """(status, headers, body, final_url)。同じサイトには 1.5 秒あける。404/410 はやり直さない"""
    host = urlsplit(url).netloc
    last = None
    for i in range(tries):
        wait = 1.5 - (time.time() - _last_hit.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        _last_hit[host] = time.time()
        try:
            req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept-Language": "ja,en;q=0.5"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.status, r.headers, (r.read() if method == "GET" else b""), r.geturl()
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code in (404, 410) or (method == "HEAD" and e.code in (403, 405, 501)):
                break
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
        if i + 1 < tries:
            time.sleep(5)
    raise RuntimeError(last or "fetch failed")


def decode(body, headers):
    enc = None
    ct = headers.get("Content-Type", "") if headers else ""
    m = re.search(r"charset=([\w-]+)", ct, re.I)
    if m:
        enc = m.group(1)
    else:
        m = re.search(rb"""(?:charset|encoding)\s*=\s*["']?([\w-]+)""", body[:4096], re.I)
        if m:
            enc = m.group(1).decode("ascii", "ignore")
    enc = (enc or "utf-8").lower()
    enc = {"shift_jis": "cp932", "shift-jis": "cp932", "sjis": "cp932", "x-sjis": "cp932", "windows-31j": "cp932",
           "euc-jp": "euc_jp"}.get(enc, enc)
    try:
        return body.decode(enc, "replace")
    except LookupError:
        return body.decode("utf-8", "replace")


# ── 取り出し ──
def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", s or ""))).strip()


def norm_url(base, href):
    href = html.unescape((href or "").strip())
    if not href or href.startswith(("javascript:", "mailto:", "tel:")):
        return None
    p = urlsplit(urljoin(base, href))
    if p.scheme not in ("http", "https"):
        return None
    q = urlencode([(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k not in DROP_QUERY])
    return urlunsplit((p.scheme, p.netloc.lower(), p.path or "/", q, ""))


def crop(text, start=None, end=None):
    """start があればその最後の出現から、end があればそこまで（見つからなければそのまま）"""
    if start:
        i = text.rfind(start)
        if i >= 0:
            text = text[i:]
    if end:
        j = text.find(end, 1)
        if j > 0:
            text = text[:j]
    return text


def kw_list(tg, cfg):
    kw = tg.get("keywords")
    if kw == "@exam":
        return cfg.get("keywords_exam") or []
    return kw or []


def ex_links(t, url, tg, cfg):
    area = crop(t, tg.get("start"), tg.get("end"))
    inc = re.compile(tg["include"]) if tg.get("include") else None
    exc = re.compile(tg["exclude"]) if tg.get("exclude") else None
    kws = kw_list(tg, cfg)
    self_u = norm_url(url, url)
    items = {}
    for href, inner in re.findall(r"""(?is)<a\b[^>]*?href\s*=\s*["']([^"']+)["'][^>]*>(.*?)</a>""", area):
        u = norm_url(url, href)
        if not u or u == self_u or (inc and not inc.search(u)) or (exc and exc.search(u)):
            continue
        x = clean(inner)
        if not x or (kws and not any(k in x for k in kws)):
            continue
        if u in items and len(items[u]) >= len(x):
            continue
        items[u] = x[:200]
    return items


def ex_rss(t, url, tg, cfg):
    kws = kw_list(tg, cfg)
    items = {}
    for it in re.findall(r"(?is)<item\b[^>]*>(.*?)</item>", t):
        g = lambda tag: (re.search(rf"(?is)<{tag}[^>]*>(.*?)</{tag}>", it) or [None, ""])[1]  # noqa: E731
        title = clean(re.sub(r"(?s)<!\[CDATA\[(.*?)\]\]>", r"\1", g("title")))
        u = norm_url(url, clean(g("link")))
        if not u or not title or (kws and not any(k in title for k in kws)):
            continue
        d = clean(g("dc:date") or g("pubDate"))[:10]
        items[u] = f"{title}（{d}）" if d else title
    return items


def ex_text(t, url, tg, cfg):
    body = re.sub(r"(?is)<(script|style|noscript)\b[^>]*>.*?</\1>", "", t)
    txt = html.unescape(re.sub(r"(?s)<[^>]+>", "\n", body))
    lines = [re.sub(r"\s+", " ", x).strip() for x in txt.split("\n")]
    txt = crop("\n".join(x for x in lines if x), tg.get("start"), tg.get("end"))
    return [x for x in txt.split("\n") if x]


def snap_file(url, old=None):
    """ETag・Last-Modified・サイズを HEAD で見て、前と違う（か初めての）ときだけ中身を取ってハッシュを付ける"""
    meta = {}
    try:
        _, hd, _, _ = fetch(url, "HEAD")
        meta = {k: hd.get(k) for k in ("ETag", "Last-Modified", "Content-Length") if hd.get(k)}
    except RuntimeError:
        pass
    if old and meta and all(old.get(k) == v for k, v in meta.items()) and old.get("sha256"):
        return {**meta, "sha256": old["sha256"]}
    _, hd, body, _ = fetch(url)
    meta = {k: hd.get(k) for k in ("ETag", "Last-Modified") if hd.get(k)}
    meta["Content-Length"] = str(len(body))
    meta["sha256"] = hashlib.sha256(body).hexdigest()
    return meta


def snapshot(tg, cfg, old):
    """対象の今の状態。links/rss は {url: 文字}、text は [行]、file は {meta}"""
    kind = tg.get("kind", "links")
    if kind == "file":
        return snap_file(tg["url"], (old or {}).get("file"))
    _, hd, body, final = fetch(tg["url"])
    t = decode(body, hd)
    if kind == "rss":
        return ex_rss(t, final, tg, cfg)
    if kind == "text":
        return ex_text(t, final, tg, cfg)
    return ex_links(t, final, tg, cfg)


def title_of(url):
    try:
        _, hd, body, _ = fetch(url, tries=1)
    except RuntimeError:
        return None
    if "html" not in (hd.get("Content-Type") or "").lower():
        return None
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", decode(body, hd))
    if not m:
        return None
    t = clean(m.group(1))
    t = re.sub(r"\s*[：:｜|]\s*(文部科学省|林野庁|公益社団法人\s*日本技術士会|日本技術士会)\s*$", "", t)
    return t or None


# ── 比べる ──
def compare(tg, old, new, budget):
    """知らせる変化（無ければ None）。budget はリンク先の <title> を読む残り回数（list で渡す）"""
    kind = tg.get("kind", "links")
    if kind in ("links", "rss"):
        added = [[u, x] for u, x in new.items() if u not in old]
        changed = [[u, old[u], x] for u, x in new.items() if u in old and old[u] != x]
        removed = [[u, x] for u, x in old.items() if u not in new]
        for a in added:
            if (len(a[1]) < 12 or a[1] in GENERIC) and budget[0] > 0:
                budget[0] -= 1
                t = title_of(a[0])
                if t and t != a[1]:
                    a[1] = f"{t}（{a[1]}）"
        if not added and not changed:
            return None, removed
        return {"added": added, "changed": changed, "removed": removed}, removed
    if kind == "text":
        sm = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
        plus, minus = [], []
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op in ("replace", "delete"):
                minus += old[i1:i2]
            if op in ("replace", "insert"):
                plus += new[j1:j2]
        if not plus and not minus:
            return None, []
        return {"plus": plus, "minus": minus}, []
    # file
    if old.get("sha256") == new.get("sha256"):
        return None, []
    return {"old": old, "new": new}, []


def shrunk(tg, old, new):
    if tg.get("kind", "links") not in ("links", "rss") or not isinstance(old, dict):
        return False
    return len(old) >= 5 and len(new) < len(old) * SHRINK


# ── 知らせ ──
def esc(s):
    return html.escape(s or "", quote=True)


def a(url, text):
    return f'<a href="{esc(url)}">{esc(text)}</a>'


def kb(n):
    try:
        return f"{round(int(n) / 1024):,}KB"
    except (TypeError, ValueError):
        return "?"


def fmt_change(tg, ch):
    head = f"■ {esc(tg.get('site', ''))}「{a(tg['url'], tg['name'])}」"
    kind = tg.get("kind", "links")
    out = [head]
    if kind in ("links", "rss"):
        for u, x in ch["added"][:8]:
            out.append(f"＋ {a(u, x)}")
        if len(ch["added"]) > 8:
            out.append(f"ほか {len(ch['added']) - 8} 件")
        for u, x0, x1 in ch["changed"][:4]:
            out.append(f"↻ {a(u, x1)}（前は「{esc(x0[:60])}」）")
        if len(ch["changed"]) > 4:
            out.append(f"ほか {len(ch['changed']) - 4} 件の書き換え")
    elif kind == "text":
        out[0] += "の本文が変わりました"
        for x in ch["plus"][:5]:
            out.append(f"＋ {esc(x[:90])}{'…' if len(x) > 90 else ''}")
        if len(ch["plus"]) > 5:
            out.append(f"ほか {len(ch['plus']) - 5} 行増えた")
        for x in ch["minus"][:3]:
            out.append(f"－ {esc(x[:90])}{'…' if len(x) > 90 else ''}")
        if len(ch["minus"]) > 3:
            out.append(f"ほか {len(ch['minus']) - 3} 行消えた")
    else:
        o, n = ch["old"], ch["new"]
        out[0] += "が差し替えられました"
        out.append(f"サイズ {kb(o.get('Content-Length'))} → {kb(n.get('Content-Length'))}"
                   + (f"、更新日 {esc(n.get('Last-Modified'))}" if n.get("Last-Modified") else ""))
    return "\n".join(out)


def build_messages(blocks, title):
    """Telegram 1通に収まるように分ける"""
    msgs, cur = [], title
    for b in blocks:
        if len(cur) + len(b) + 2 > MSG_LIMIT and cur != title:
            msgs.append(cur)
            cur = title + "（つづき）"
        cur += "\n\n" + b
    msgs.append(cur)
    return msgs


def send(text, dry):
    if dry:
        print("──── Telegram（--dry なので送らない）────\n" + text + "\n────")
        return True
    try:
        sys.path.insert(0, str(TRADING_AGENT))
        from trading.telegram_notify import send_message
        return bool(send_message(text, parse_mode="HTML", disable_web_page_preview=True))
    except Exception as e:  # noqa: BLE001
        log(f"WARN: Telegram に送れませんでした: {e}")
        return False


# ── 本体 ──
def load_json(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save_json(p, data):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def main():
    global STATE, LOG, CHANGES
    ap = argparse.ArgumentParser(description="技術士試験に関わる公式ページの更新を見張る")
    ap.add_argument("--dry", action="store_true", help="送らずに表示する（状態も保存しない）")
    ap.add_argument("--list", action="store_true", help="各対象から取れたものを表示するだけ")
    ap.add_argument("--only", help="この id の対象だけ")
    ap.add_argument("--config", default=str(ROOT / "gwatch.json"))
    ap.add_argument("--state", default=str(STATE), help="状態ファイル（検証用に差し替える）")
    args = ap.parse_args()
    if args.state != str(STATE):
        STATE = Path(args.state)
        LOG = STATE.with_name("gwatch.log")
        CHANGES = STATE.with_name("gwatch_changes.jsonl")

    cfg = load_json(args.config, None)
    if not cfg:
        log(f"ERROR: 設定を読めません: {args.config}")
        return 2
    targets = [t for t in cfg["targets"] if not t.get("off") and (not args.only or t["id"] == args.only)]
    if args.only and not targets:
        log(f"ERROR: id が見つかりません: {args.only}")
        return 2

    if args.list:
        for tg in targets:
            try:
                s = snapshot(tg, cfg, None)
            except RuntimeError as e:
                print(f"[{tg['id']}] 取れない: {e}")
                continue
            if isinstance(s, dict) and tg.get("kind", "links") != "file":
                print(f"[{tg['id']}] {tg['name']}: リンク {len(s)} 件")
                for u, x in list(s.items())[:6]:
                    print(f"    {x[:50]} | {u}")
            elif isinstance(s, list):
                print(f"[{tg['id']}] {tg['name']}: 本文 {len(s)} 行  先頭「{(s[0] if s else '')[:50]}」 最後「{(s[-1] if s else '')[:50]}」")
            else:
                print(f"[{tg['id']}] {tg['name']}: {s}")
        return 0

    state = load_json(STATE, {})
    first_ever = not state.get("targets")
    st_all = state.setdefault("targets", {})
    blocks, alerts, records, fresh = [], [], [], []
    budget = [TITLE_LOOKUPS]
    ts = now().isoformat(timespec="seconds")
    for tg in targets:
        tid = tg["id"]
        st = st_all.get(tid) or {}
        key = {"links": "items", "rss": "items", "text": "lines", "file": "file"}[tg.get("kind", "links")]
        old = st.get(key)
        try:
            new = snapshot(tg, cfg, st)
            if old is not None and shrunk(tg, old, new):
                raise RuntimeError(f"リンクが {len(old)} → {len(new)} 件に減った（ページの作り替えかエラーページ）")
        except RuntimeError as e:
            st["fail"] = st.get("fail", 0) + 1
            st["fail_msg"] = str(e)[:200]
            log(f"{tid}: 取れない（{st['fail']}回目）: {e}")
            if st["fail"] >= FAIL_ALERT and not st.get("alerted"):
                alerts.append(f"⚠️ {esc(tg.get('site', ''))}「{a(tg['url'], tg['name'])}」を{st['fail']}回続けて確かめられません（{esc(st['fail_msg'])}）。ページが移ったかもしれません")
                st["alerted"] = True
            st_all[tid] = st
            continue
        if st.get("alerted"):
            log(f"{tid}: また取れるようになった")
        st.update({"fail": 0, "alerted": False, "ok_at": ts})
        st.pop("fail_msg", None)
        if old is None:
            fresh.append(tg["name"])
            log(f"{tid}: 初めてなので今の状態を覚えた（{len(new)}）")
        else:
            ch, removed = compare(tg, old, new, budget)
            if removed and not ch:
                log(f"{tid}: リンクが消えただけ（知らせない）: " + " / ".join(x for _, x in removed[:5]))
            if ch:
                blocks.append(fmt_change(tg, ch))
                records.append({"at": ts, "id": tid, "name": tg["name"], "url": tg["url"], "kind": tg.get("kind", "links"), "change": ch})
                st["changed_at"] = ts
                log(f"{tid}: 変化あり " + json.dumps({k: len(v) if isinstance(v, list) else 1 for k, v in ch.items()}, ensure_ascii=False))
        st[key] = new
        st_all[tid] = st

    msgs = list(state.get("pending") or [])
    if blocks:
        msgs += build_messages(blocks, f"📘 技術士の試験情報に更新があります（{len(blocks)}か所）")
    if alerts:
        msgs += build_messages(alerts, "📘 技術士の試験情報の見張り")
    if first_ever and fresh and not blocks:
        msgs.append(f"📘 技術士の試験情報の見張りを始めました（{len(fresh)}か所）。日本技術士会・文部科学省（技術士分科会）・林野庁のページを毎日 19:30（日本時間）＝ブラジル 7:30 に確かめて、新しいお知らせ・資料や書き換えがあればここに送ります。")

    pending = []
    for m in msgs:
        if not send(m, args.dry):
            pending.append(m)
    if args.dry:
        log(f"--dry: 変化 {len(blocks)}か所・警告 {len(alerts)}件・初めて {len(fresh)}か所（保存しない）")
        return 0
    state["pending"] = pending
    state["run_at"] = ts
    save_json(STATE, state)
    if records:
        with CHANGES.open("a", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    log(f"終わり: 変化 {len(blocks)}か所・警告 {len(alerts)}件・初めて {len(fresh)}か所・送れなかった {len(pending)}通")
    return 0


if __name__ == "__main__":
    sys.exit(main())
