# 切り出した問題画像（qimg/）と正答（answers.json）から、Firestore に入れる索引と問題データを作る
import sys, os, json, io, base64
from PIL import Image
P, O, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
ANS = json.load(open(f'{P}/answers.json'))
YEARS = [('R7', '令和7', '令和7年度'), ('R6', '令和6', '令和6年度'), ('R5', '令和5', '令和5年度'), ('R4', '令和4', '令和4年度'),
         ('R3', '令和3', '令和3年度'), ('R2', '令和2', '令和2年度'), ('R1b', '元年(再)', '令和元年度（再試験）'), ('R1', '令和元', '令和元年度')]
SUBJ = ['shinrin', 'kiso', 'tekisei']
PDF = {  # 日本技術士会の原本PDF（https://www.engineer.or.jp/c_categories/index02021.html）
 'R7_kiso': '011/attached/attach_11457_1', 'R6_kiso': '010/attached/attach_10606_1', 'R5_kiso': '009/attached/attach_9917_1', 'R4_kiso': '009/attached/attach_9126_1',
 'R3_kiso': '008/attached/attach_8183_1', 'R2_kiso': '007/attached/attach_7438_1', 'R1b_kiso': '007/attached/attach_7102_1', 'R1_kiso': '006/attached/attach_6834_1',
 'R7_tekisei': '011/attached/attach_11457_2', 'R6_tekisei': '010/attached/attach_10606_2', 'R5_tekisei': '009/attached/attach_9917_2', 'R4_tekisei': '009/attached/attach_9126_2',
 'R3_tekisei': '008/attached/attach_8183_2', 'R2_tekisei': '007/attached/attach_7438_2', 'R1b_tekisei': '007/attached/attach_7102_2', 'R1_tekisei': '006/attached/attach_6834_2',
 'R7_shinrin': '011/attached/attach_11458_4', 'R6_shinrin': '010/attached/attach_10607_4', 'R5_shinrin': '009/attached/attach_9918_4', 'R4_shinrin': '009/attached/attach_9127_4',
 'R3_shinrin': '008/attached/attach_8184_4', 'R2_shinrin': '007/attached/attach_7439_4', 'R1b_shinrin': '007/attached/attach_7103_4', 'R1_shinrin': '006/attached/attach_6835_4'}
os.makedirs(f'{OUT}/q', exist_ok=True)
sets, total, nbytes = [], 0, 0
for y, ys, yl in YEARS:
    for s in SUBJ:
        sid = f'{y}_{s}'
        meta = json.load(open(f'{O}/{sid}/meta.json'))
        ans = ANS[y][s]
        labels = [(g, q) for g in range(1, 6) for q in range(1, 7)] if s == 'kiso' else list(range(1, len(meta) + 1))
        assert len(meta) == len(labels) == len(ans), (sid, len(meta), len(ans))
        qs = []
        for m, lab in zip(meta, labels):
            key = f'{lab[0]}-{lab[1]}' if s == 'kiso' else str(lab)
            a = ans[key]
            k = f'{sid}_{m["i"]:02d}'
            no = f'Ⅰ-{lab[0]}-{lab[1]}' if s == 'kiso' else (f'Ⅱ-{lab}' if s == 'tekisei' else f'Ⅲ-{lab}')
            q = {'k': k, 'no': no, 'a': a, 'p': m['page']}
            if s == 'kiso': q['g'] = lab[0]
            qs.append(q)
            im = Image.open(f'{O}/{sid}/q{m["i"]:02d}.png').convert('L').point(lambda v: 255 if v >= 165 else 0).convert('1')
            b = io.BytesIO(); im.save(b, format='PNG', optimize=True)
            url = 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()
            json.dump({'img': url, 'w': im.width, 'h': im.height, 't': m['text']}, open(f'{OUT}/q/{k}.json', 'w'), ensure_ascii=False)
            total += 1; nbytes += len(url)
        sets.append({'id': sid, 'y': y, 'ys': ys, 'yl': yl, 's': s, 'n': len(qs),
                     'pdf': f'https://www.engineer.or.jp/c_topics/{PDF[sid]}.pdf', 'qs': qs})
idx = {'v': 1, 'upd': '2026-10-31', 'src': '日本技術士会 過去問題（第一次試験）・正答', 'sets': sets}
json.dump(idx, open(f'{OUT}/idx.json', 'w'), ensure_ascii=False)
print('sets', len(sets), 'questions', total, 'img base64 MB', round(nbytes / 1024 / 1024, 1), 'idx KB', round(len(json.dumps(idx, ensure_ascii=False).encode()) / 1024, 1))
bad = [(s['id'], q['no'], q['a']) for s in sets for q in s['qs'] if q['a'] == 0 or isinstance(q['a'], list)]
print('special answers', bad)
