#!/usr/bin/env python3
"""words.json の単語を品詞・性質ごとに分類して印刷用HTMLを出力する。"""
import json
import re
import html
from collections import OrderedDict

NOUN_SUFFIXES = (
    'ção', 'são', 'dade', 'agem', 'ura', 'eza', 'ismo',
    'mento', 'cia', 'gia', 'tude', 'ência', 'ância',
)
ADJ_SUFFIXES = (
    'oso', 'osa', 'ivo', 'iva', 'ico', 'ica',
    'ável', 'ível', 'al', 'ante', 'ente', 'ês', 'esa',
)
VERB_SUFFIXES = ('ar', 'er', 'ir', 'or')
NOUN_EXCEPTIONS = {
    'lugar', 'mar', 'mulher', 'par', 'ar', 'dor', 'cor', 'ator',
    'amor', 'autor', 'doutor', 'leitor', 'professor', 'motor',
    'setor', 'fator', 'valor', 'sabor', 'olor', 'humor', 'rumor',
    'favor', 'horror', 'terror', 'tumor', 'erro', 'reator',
    'computador', 'jogador', 'trabalhador', 'morador', 'consumidor',
    'produtor', 'condutor', 'redator', 'interior', 'superior',
    'exterior', 'inferior', 'anterior', 'posterior',
}
ADV_SUFFIX = 'mente'

CONJ_MARKERS = (
    '三人称', '一人称', '二人称', '過去', '現在分詞', '接続法',
    '命令形', '過去完了', '不定詞', '未来', '直説法',
)


def load_words(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def classify(entry):
    pt = entry[0].strip()
    ja = entry[1] if len(entry) > 1 else ''
    note = entry[2] if len(entry) > 2 else ''
    pt_low = pt.lower()

    # 1. note ベースの判定（最優先）
    if note:
        if note == '女性複数形':
            return '形容詞・分詞 — 女性複数形'
        if note == '女性形':
            return '形容詞・分詞 — 女性形'
        if note == '複数形':
            return '形容詞・分詞 — 複数形'
        if note == '口語':
            return '口語表現'
        for marker in CONJ_MARKERS:
            if marker in note:
                return '動詞 — 活用形・分詞'

    # 2. 複数語フレーズ
    if ' ' in pt_low or '-' in pt_low:
        return '慣用句・複数語フレーズ'

    # 3. 副詞
    if pt_low.endswith(ADV_SUFFIX) and len(pt_low) > 6:
        return '副詞'

    # 4. 名詞語尾
    for suf in NOUN_SUFFIXES:
        if pt_low.endswith(suf):
            return '名詞'

    # 5. 動詞不定詞 (-ar / -er / -ir / -or)
    if pt_low not in NOUN_EXCEPTIONS:
        for suf in VERB_SUFFIXES:
            if pt_low.endswith(suf) and len(pt_low) > 2:
                # -or は曖昧（doutor 等）。日本語が「〜する」なら動詞、そうでなければ名詞
                if suf == 'or':
                    if 'する' in ja:
                        return '動詞 — 不定詞'
                    return '名詞'
                # -ar/-er/-ir は基本動詞だが、例: lugar はすでに弾いている
                return '動詞 — 不定詞'

    # 6. 過去分詞（男性単数）-ado/-ido
    if re.search(r'(ado|ido)$', pt_low):
        return '形容詞・分詞 — 男性単数（過去分詞）'

    # 7. 形容詞語尾
    for suf in ADJ_SUFFIXES:
        if pt_low.endswith(suf):
            return '形容詞'

    # 8. 日本語が「〜する」なら動詞、それ以外は名詞にフォールバック
    #    （「い」「な」末尾での形容詞推定は「間違い」「洗い」等の名詞を誤分類するため不採用）
    ja_clean = re.sub(r'[・，、（）()\s].*$', '', ja)
    if ja_clean.endswith('する'):
        return '動詞 — その他'

    # 9. 残り → 名詞
    return '名詞'


# 表示順
CATEGORY_ORDER = [
    '動詞 — 不定詞',
    '動詞 — 活用形・分詞',
    '動詞 — その他',
    '名詞',
    '形容詞',
    '形容詞・分詞 — 男性単数（過去分詞）',
    '形容詞・分詞 — 女性形',
    '形容詞・分詞 — 複数形',
    '形容詞・分詞 — 女性複数形',
    '副詞',
    '口語表現',
    '慣用句・複数語フレーズ',
]


def build_html(grouped):
    total = sum(len(v) for v in grouped.values())
    parts = []
    parts.append('''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>Palavras 印刷用 単語リスト（品詞別）</title>
<style>
  *{box-sizing:border-box}
  html,body{margin:0;padding:0}
  body{
    font-family:"Hiragino Sans","Yu Gothic","Noto Sans JP",sans-serif;
    color:#111;background:#fff;font-size:9pt;line-height:1.35;
    padding:14mm 12mm;
  }
  header{margin-bottom:10mm}
  header h1{font-size:16pt;margin:0 0 2mm 0;color:#1a7a3a}
  header .meta{font-size:9pt;color:#555}
  .toc{
    margin:4mm 0 8mm 0;padding:3mm 4mm;
    background:#f4faf6;border:1px solid #cfe7d6;border-radius:3px;
    columns:2;column-gap:8mm;font-size:9pt;
  }
  .toc ol{margin:0;padding-left:18px}
  .toc li{margin-bottom:1mm;break-inside:avoid}
  .toc .cnt{color:#1a7a3a;font-weight:700}
  section{break-inside:auto;margin-bottom:6mm}
  section h2{
    font-size:11pt;background:#1a7a3a;color:#fff;
    padding:1.5mm 3mm;margin:0 0 2mm 0;border-radius:2px;
    break-after:avoid;
  }
  .grid{
    columns:3;column-gap:5mm;column-rule:1px solid #e5e5e5;
  }
  .item{
    break-inside:avoid;padding:0.6mm 0;
    border-bottom:1px dotted #e5e5e5;
    display:grid;grid-template-columns:1fr;gap:0;
  }
  .pt{font-weight:700;color:#0d4a23}
  .ja{color:#222}
  .note{color:#888;font-size:7.5pt;margin-left:4px}
  .ex{color:#666;font-size:7.5pt;font-style:italic;display:block;margin-top:0.3mm}
  @media print{
    body{padding:10mm 8mm;font-size:8.5pt}
    section{page-break-inside:auto}
    section h2{page-break-after:avoid}
    .item{page-break-inside:avoid}
    .toc{columns:3}
  }
  @page{size:A4;margin:10mm}
</style>
</head>
<body>
<header>
  <h1>🇧🇷 Palavras — 印刷用 単語リスト（品詞別）</h1>
  <div class="meta">総数 ''' + str(total) + ''' 語 ／ ''' + str(len(grouped)) + ''' カテゴリ</div>
</header>
''')

    # 目次
    parts.append('<nav class="toc"><strong>目次</strong><ol>')
    for cat, items in grouped.items():
        anchor = 'cat-' + str(abs(hash(cat)) % 100000)
        parts.append(
            f'<li><a href="#{anchor}">{html.escape(cat)}</a> '
            f'<span class="cnt">{len(items)}</span></li>'
        )
    parts.append('</ol></nav>')

    # セクション
    for cat, items in grouped.items():
        anchor = 'cat-' + str(abs(hash(cat)) % 100000)
        parts.append(f'<section id="{anchor}">')
        parts.append(f'<h2>{html.escape(cat)}（{len(items)}語）</h2>')
        parts.append('<div class="grid">')
        for w in items:
            pt = html.escape(w[0])
            ja = html.escape(w[1] if len(w) > 1 else '')
            note = html.escape(w[2] if len(w) > 2 else '')
            note_html = f' <span class="note">[{note}]</span>' if note else ''
            parts.append(
                f'<div class="item"><span class="pt">{pt}</span>'
                f'<span class="ja">{ja}{note_html}</span></div>'
            )
        parts.append('</div></section>')

    parts.append('</body></html>')
    return '\n'.join(parts)


def main():
    words = load_words('words.json')
    buckets = {}
    for w in words:
        cat = classify(w)
        buckets.setdefault(cat, []).append(w)

    # 各カテゴリ内で PT 昇順
    for k in buckets:
        buckets[k].sort(key=lambda x: x[0].lower())

    # CATEGORY_ORDER 通りに並べ、漏れはあとで追加
    grouped = OrderedDict()
    for cat in CATEGORY_ORDER:
        if cat in buckets:
            grouped[cat] = buckets[cat]
    for cat, items in buckets.items():
        if cat not in grouped:
            grouped[cat] = items

    html_doc = build_html(grouped)
    out = 'docs/palavras_print.html'
    import os
    os.makedirs('docs', exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html_doc)

    # サマリー出力
    print(f'wrote {out}')
    total = 0
    for cat, items in grouped.items():
        print(f'  {len(items):4d}  {cat}')
        total += len(items)
    print(f'  ----')
    print(f'  {total:4d}  total')


if __name__ == '__main__':
    main()
