# OCR の行位置から問題の区切りを見つけ、ページ画像から問題ごとに切り出す
# 使い方: python3 -P -E segment.py <dl_pq> <out_dir> <set>...   （Pillow がユーザーの site-packages にあるので -I は使えない）
import json, sys, re, os, unicodedata, statistics, io, base64
from PIL import Image
P, OUT = sys.argv[1], sys.argv[2]
EXPECT = {'kiso': 30, 'tekisei': 15, 'shinrin': 35}
CH = '①②③④⑤'
def load(k):
    pages = [json.loads(l) for l in open(f'{P}/ocr_{k}.jsonl')]
    pages.sort(key=lambda p: p['file'])
    return pages
def is_footer(r):
    t = unicodedata.normalize('NFKC', r['t'])
    return r['y'] > 0.88 and (re.search(r'\d+\s*/\s*\d+', t) or re.search(r'\(R\s*\d|\(令和|\(H\d', t))
ROMAN = 'IilL|ⅠⅡⅢ1'          # Ⅰ〜Ⅲ の読み違い（数字の1として数える）
JUNK = '目日皿田口エ工H'        # Ⅲ・Ⅱ がこう読まれることがある（数えない）
DASHES = '-ー－−―‐~・.'
DC = r'\-ー－−―‐~・.'      # 文字クラス用（ハイフンをエスケープ）
def parse_label(t, subj):
    # 行頭の「記号・区切り・数字」だけを取り出し、数字列（ローマ数字の読み違いは1）と、最後の区切りのあとの数字を返す
    t = unicodedata.normalize('NFKC', t).strip()
    t = re.sub(rf'\s*([{DC}])\s*', r'\1', t)            # 「II -12」→「II-12」
    t = re.sub(rf'^([{JUNK}]?[{ROMAN}]{{1,3}})\s+(?=\d[{DC}])', r'\1-', t)   # 「1 4-1」→「1-4-1」（区切りが空白に読まれた）
    m = re.match(rf'^([{JUNK}]?[{ROMAN}{DC}0-9]{{1,8}})', t)
    if not m: return None
    tok = m.group(1)
    if re.search(r'\d', tok): tok = re.sub(rf'[{ROMAN}]+$', lambda x: '' if not x.group(0).isdigit() else x.group(0), tok)   # 「I-5-4IEA」の後ろの I は本文
    if not any(c in DASHES for c in tok):
        m2 = re.match(rf'^([{JUNK}]?[{ROMAN}]*)(\d*)\s+(\d{{1,2}})(?!\d)', t)   # 「I 8」「1I 13」
        if m2 and m2.group(1): tok = m2.group(1) + m2.group(2) + m2.group(3)
        elif not re.match(rf'^[{JUNK}]?[{ROMAN}]+\d', tok): return None   # 「2 前条の…」のような段落番号
    digits = ''.join('1' if (c in ROMAN and not c.isdigit()) else c for c in tok if c.isdigit() or c in ROMAN)
    parts = re.split(rf'[{DC}]', tok)
    after = re.sub(r'\D', '', parts[-1])
    prev = re.sub(r'\D', '', parts[-2]) if len(parts) > 1 else ''
    return (digits, after, prev)
def label_ok(lab, want, subj):
    digits, after, prev = lab
    if subj == 'kiso':
        # 「I-3-23次元…」のように番号のすぐ後ろに本文の数字が続くことがある
        return digits.endswith(f'{want[0]}{want[1]}') or (prev.endswith(str(want[0])) and after.startswith(str(want[1])) and len(after) <= 4)
    w = str(want)
    return digits.endswith(w) or (after.startswith(w) and len(after) > len(w) + 2)
def expected_labels(subj):
    if subj == 'kiso': return [(g, q) for g in range(1, 6) for q in range(1, 7)]
    return list(range(1, EXPECT[subj] + 1))
def align(cands, exp, subj):
    # 候補（読む順）と期待する番号の並びを、一致数が最大になるように対応づける（LCS）
    n, m = len(cands), len(exp)
    ok = [[cands[i][3] is not None and label_ok(cands[i][3], exp[j], subj) for j in range(m)] for i in range(n)]
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            dp[i][j] = max(dp[i + 1][j], dp[i][j + 1], (1 + dp[i + 1][j + 1]) if ok[i][j] else 0)
    match, i, j = {}, 0, 0
    while i < n and j < m:
        if ok[i][j] and dp[i][j] == 1 + dp[i + 1][j + 1]: match[j] = i; i += 1; j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]: i += 1
        else: j += 1
    return match
def segment(k):
    subj = k.split('_')[1]
    pages = load(k)
    exp = expected_labels(subj)
    lines = []
    for pi, pg in enumerate(pages):
        for r in sorted(pg['lines'], key=lambda r: r['y']):
            if is_footer(r) or r['y'] > 0.9 or r['x'] > 0.2: continue
            t = unicodedata.normalize('NFKC', r['t']).strip()
            if r['t'][:1] in CH or '群' in t[:4] or t[:1] in '【(' or re.match(r'^第\d+条', t): continue
            lines.append((pi, r['y'], r, parse_label(r['t'], subj)))
    # 見出しの x は書類の中でほぼ一定。番号として読めた行の x の中央値のまわりを窓にする
    xs = [c[2]['x'] for c in lines if c[3] and any(label_ok(c[3], w, subj) for w in exp)]
    med = statistics.median(xs)
    kept = [x for x in xs if abs(x - med) < 0.012]
    lo, hi = min(kept) - 0.003, max(kept) + 0.003
    tight = [c for c in lines if lo <= c[2]['x'] <= hi]
    heads = {j: tight[i] for j, i in align(tight, exp, subj).items()}
    pos = lambda c: (c[0], c[1])
    filled = []
    for j, w in enumerate(exp):
        if j in heads: continue
        prev = max([heads[x] for x in heads if x < j], key=pos, default=None)
        nxt = min([heads[x] for x in heads if x > j], key=pos, default=None)
        between = [c for c in lines if (prev is None or pos(c) > pos(prev)) and (nxt is None or pos(c) < pos(nxt))]
        # 1) 窓の外（少し左）でも番号として読める行  2) 窓の中で、記号が落ちて「30木材…」のように番号から始まる行
        pick = [c for c in between if c[3] and label_ok(c[3], w, subj) and c[2]['x'] <= hi]
        if not pick and subj != 'kiso':
            pick = [c for c in between if lo <= c[2]['x'] <= hi and re.match(rf'^\D{{0,3}}{w}(?!\d)', unicodedata.normalize('NFKC', c[2]['t']))]
        if pick:
            heads[j] = min(pick, key=lambda c: abs(c[2]['x'] - med)); filled.append(w)
    missing = [w for j, w in enumerate(exp) if j not in heads]
    seq = [heads[j] for j in range(len(exp)) if j in heads]
    if any(pos(seq[i]) >= pos(seq[i + 1]) for i in range(len(seq) - 1)): print(f'   ?? {k}: 見出しの順番が前後している')
    if filled: print(f'   .. {k}: 番号の記号が読めなかった見出しを補った {filled}')
    if missing: print(f'   ?? {k}: 見つからない見出し {missing}')
    return pages, [(c[0], c[1], c[2]) for c in seq], (lo, hi)
_imgs = {}
def page_img(pg):
    f = os.path.join(P, pg['file'])
    if f not in _imgs: _imgs[f] = Image.open(f).convert('L')
    return _imgs[f]
def ink_row(px, yy, x0, x1):
    return sum(1 for x in range(x0, x1, 2) if px[x, yy] < 140) >= 5
def gap_above(pg, y, left, right, limit=0.07, run_min=18):
    # 見出し行の上にある、何も書かれていない帯（run_min 行以上）の真ん中を境目にする。
    # 行列や分数が見出しの文字より上にはみ出していても切らないため
    im = page_img(pg); W, H = im.size; px = im.load()
    x0, x1 = int(left * W), int(right * W)
    y0 = int(y * H) - 2; run = 0
    for yy in range(y0, max(0, y0 - int(limit * H)), -1):
        if ink_row(px, yy, x0, x1): run = 0
        else:
            run += 1
            if run >= run_min: return (yy + run // 2) / H
    return y - 0.009
def crop_regions(k, pages, heads):
    # 文字のある範囲（左右）は書類全体でそろえる
    xs0 = [r['x'] for pg in pages for r in pg['lines'] if not is_footer(r)]
    xs1 = [r['x'] + r['w'] for pg in pages for r in pg['lines'] if not is_footer(r)]
    left, right = max(0.0, min(xs0) - 0.015), min(1.0, max(xs1) + 0.015)
    def page_bottom(pi):
        fs = [r['y'] for r in pages[pi]['lines'] if is_footer(r)]
        return (min(fs) - 0.008) if fs else 0.94
    def group_cut(pi, y0, y1):
        # 基礎の「N群 …（全6問題から3問題を選択解答）」の見出しは前の問題に含めない（2行に分かれて読まれることがある）
        for r in pages[pi]['lines']:
            t = unicodedata.normalize('NFKC', r['t']).strip()
            if y0 < r['y'] < y1 and re.match(r'^\d\s*群', t): y1 = min(y1, gap_above(pages[pi], r['y'], left, right))
        return y1
    cuts = [(pi, gap_above(pages[pi], y, left, right)) for pi, y, r in heads]
    out = []
    for i, (pi, top) in enumerate(cuts):
        parts = []
        npi, ny = cuts[i + 1] if i + 1 < len(cuts) else (len(pages) - 1, None)
        cur = pi
        while True:
            bot = ny if (cur == npi and ny is not None) else page_bottom(cur)
            parts.append((cur, top, group_cut(cur, top, bot)))
            if cur >= npi: break
            cur += 1; top = 0.03
        out.append(parts)
    return left, right, out
def trim(im):
    # 余白の行を落とす。スキャンのごみ（点）で止まらないよう、濃い画素が5個以上ある行だけを「文字の行」とみなす
    W, H = im.size
    px = im.load()
    ink = [sum(1 for x in range(0, W, 2) if px[x, y] < 140) >= 5 for y in range(H)]
    rows = [y for y, v in enumerate(ink) if v]
    if not rows: return None
    t, b = max(0, rows[0] - 14), min(H, rows[-1] + 14)
    return im.crop((0, t, W, b))
def build(k):
    pages, heads, hx = segment(k)
    subj = k.split('_')[1]
    n = EXPECT[subj]
    if len(heads) != n:
        print(f'!! {k}: 見出し {len(heads)} 個（期待 {n}）')
        for pi, y, r in heads: print(f'   p{pi+1} y={y:.3f} x={r["x"]:.3f} {r["t"][:20]}')
        return None
    left, right, regs = crop_regions(k, pages, heads)
    os.makedirs(f'{OUT}/{k}', exist_ok=True)
    res = []
    for qi, parts in enumerate(regs):
        ims = []
        txt = []
        used = []
        for (pi, top, bot) in parts:
            pg = pages[pi]
            im = page_img(pg)
            W, H = im.size
            c = im.crop((int(left * W), int(max(0, top) * H), int(right * W), int(min(1, bot) * H)))
            c = trim(c)
            if c is not None and c.height > 20: ims.append(c); used.append(pi + 1)
            txt += [r['t'] for r in sorted(pg['lines'], key=lambda r: (round(r['y'], 3), r['x'])) if top <= r['y'] < bot and not is_footer(r)]
        gap = 28
        Hs = sum(i.height for i in ims) + gap * (len(ims) - 1)
        canvas = Image.new('L', (ims[0].width, Hs), 255)
        yy = 0
        for j, c in enumerate(ims):
            canvas.paste(c, (0, yy)); yy += c.height + gap
        res.append({'img': canvas, 'page': parts[0][0] + 1, 'pages': used, 'text': '\n'.join(txt)})
    return res
if __name__ == '__main__':
    for k in sys.argv[3:]:
        r = build(k)
        if r is None: continue
        meta = []
        for i, q in enumerate(r):
            q['img'].save(f'{OUT}/{k}/q{i+1:02d}.png', optimize=True)
            meta.append({'i': i + 1, 'page': q['page'], 'pages': q['pages'], 'h': q['img'].height, 'w': q['img'].width, 'text': q['text']})
        json.dump(meta, open(f'{OUT}/{k}/meta.json', 'w'), ensure_ascii=False)
        hs = [m['h'] for m in meta]
        print(f'{k}: {len(meta)}問 OK  高さ {min(hs)}〜{max(hs)}px  複数ページ {sum(1 for m in meta if len(m["pages"])>1)}問')
