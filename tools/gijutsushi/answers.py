# 正答PDF（pdftotext -layout 済み）から 基礎30・適性15・森林35 の正答を取り出す
import re, sys, json, unicodedata
YEARS = ['R7','R6','R5','R4','R3','R2','R1b','R1']
def parse(path):
    t = unicodedata.normalize('NFKC', open(path, encoding='utf-8').read())
    # 見出し「試験問題の正答」ごとに区切る
    parts = re.split(r'(?=技術士第一次試験\s*(?:\(再試験\))?\s*【)', t)
    out = {'kiso': {}, 'tekisei': {}, 'shinrin': {}}
    notes = []
    for p in parts:
        m = re.match(r'技術士第一次試験\s*(?:\(再試験\))?\s*【\s*(III|II|I)\s*(基礎|適性|専門)科目\s*】', p)
        if not m: continue
        subj = {'基礎': 'kiso', '適性': 'tekisei', '専門': 'shinrin'}[m.group(2)]
        if subj == 'shinrin':
            head = p[:400]
            if not re.search(r'13\s*\.\s*森林部門', head): continue
        for a, b, c, ans, alt1, alt2 in re.findall(r'(III|II|I)\s*-\s*(\d+)(?:\s*-\s*(\d+))?\s+(※\s*([1-5])\s*又は\s*([1-5])|[1-5※])', p):
            key = f'{b}-{c}' if c else b
            # 「※ 4 又は 3」= どちらも正解。「※」だけ = 問題不成立（0）
            out[subj][key] = [int(alt1), int(alt2)] if alt1 else (0 if ans == '※' else int(ans))
        for n in re.findall(r'※[^\n]*(?:\n(?!\s*(?:III|II|I)\s*-)[^\n]*){0,6}', p):
            if '当初' in n or '全員' in n or '成立' in n: notes.append((subj, re.sub(r'\s+', '', n)[:200]))
    return out, notes
res = {}
for y in YEARS:
    o, notes = parse(f'{sys.argv[1]}/ans_{y}.txt')
    res[y] = o
    print(y, {k: len(v) for k, v in o.items()}, 'invalid:', {k: [q for q, a in v.items() if a == 0] for k, v in o.items() if any(a == 0 for a in v.values())})
    for s, n in notes: print('   note', s, n[:150])
json.dump(res, open(f'{sys.argv[1]}/answers.json', 'w'), ensure_ascii=False)
