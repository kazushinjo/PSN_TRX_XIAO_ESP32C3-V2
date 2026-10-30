# -*- coding: utf-8 -*-
"""購入用部品表 bom_purchase.csv から、同じ部品の個数のまとめを作る。

  python3 make_bom_summary.py

同じ部品 = 同じ購入先・購入先の型番（型番がない部品は同じ品名・値/型番）。
部品表では値やフットプリント（足のピッチ）ごとに行が分かれていても、買う品が同じなら 1 行にまとめる。
出力:
  bom_summary.csv     まとめ（UTF-8 BOM 付き、Excel でそのまま開ける）
  部品個数まとめ.md   区分ごとの表と合計

買う数 = 合計個数 ÷ 入数 の切り上げ。ピンヘッダ（40P の 1 本）はフットプリントのピン数から計算する。
「各 1」のように数で書いていない行は、合計に入れずそのまま載せる。
bom_purchase.csv を作り直したら、これも実行し直す（何度実行しても同じ結果になる）。
"""
import collections
import csv
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = next(p for p in (os.path.join(HERE, 'bom_purchase.csv'),
                       os.path.join(HERE, '..', 'kicad', 'bom_purchase.csv'))
           if os.path.exists(p))
OUT_DIR = os.path.dirname(SRC)
OUT_CSV = os.path.join(OUT_DIR, 'bom_summary.csv')
OUT_MD = os.path.join(OUT_DIR, '部品個数まとめ.md')


def ref_key(ref):
    m = re.match(r'([A-Za-z]+)(\d+)', ref)
    return (m.group(1), int(m.group(2))) if m else (ref, 0)


def num(s):
    s = s.strip()
    return int(s) if s.isdigit() else None


def pins(footprint):
    m = re.search(r'(\d+)x(\d+)', footprint)
    return int(m.group(1)) * int(m.group(2)) if m else None


def main():
    with open(SRC, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    price_col = next(k for k in rows[0] if k.startswith('価格'))

    groups = collections.OrderedDict()
    loose = []                        # 「各 1」など数で書いていない行
    for r in rows:
        qty = num(r['数量'])
        if qty is None:
            loose.append(r)
            continue
        model = r['購入先の型番'].strip()
        key = (r['購入先'], model) if model else ('', r['品名'], r['値/型番'])
        g = groups.setdefault(key, {'row': r, 'qty': 0, 'refs': [], 'values': [], 'pins': 0, 'notes': []})
        g['qty'] += qty
        g['refs'] += [x for x in r['Reference'].split(',') if x]
        if r['値/型番'] not in g['values']:
            g['values'].append(r['値/型番'])
        p = pins(r['フットプリント'])
        g['pins'] += (p or 0) * qty
        note = r['購入メモ'].strip()
        if note and note not in g['notes']:
            g['notes'].append(note)

    out = []
    for g in groups.values():
        r = g['row']
        if len(g['notes']) > 1 or len(g['values']) > 1 or len(g['refs']) > len(r['Reference'].split(',')):
            # まとめた行では「〜と同じ品」は要らない
            g['notes'] = [n for n in ('。'.join(s for s in n.split('。') if 'と同じ品' not in s).strip()
                                      for n in g['notes']) if n]
        unit = r['入数']
        n = re.match(r'(\d+)', unit)
        price = num(r[price_col])
        if '(40P)' in unit and g['pins']:
            packs = math.ceil(g['pins'] / 40)
        elif n:
            packs = math.ceil(g['qty'] / int(n.group(1)))
        else:
            packs = None
        amount = packs * price if packs is not None and price is not None else None
        refs = sorted(g['refs'], key=ref_key)
        out.append({
            '区分': r['区分'], '品名': r['品名'], '値/型番': '・'.join(g['values']),
            '合計個数': g['qty'], 'Reference': ', '.join(refs),
            '購入先': r['購入先'], '購入先の型番': r['購入先の型番'], '販売コード': r['販売コード'],
            '入数': unit, '買う数': '' if packs is None else packs,
            '単価': r[price_col], '金額': '' if amount is None else amount,
            '購入メモ': ' ／ '.join(g['notes']),
            '_pins': g['pins'] if '(40P)' in unit else 0,
        })

    cols = ['区分', '品名', '値/型番', '合計個数', 'Reference', '購入先', '購入先の型番', '販売コード',
            '入数', '買う数', '単価', '金額', '購入メモ']
    with open(OUT_CSV, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(cols[:10] + [price_col.replace('価格', '単価'), '金額', '購入メモ'])
        for o in out:
            w.writerow([o[c] for c in cols])
        for r in loose:
            w.writerow([r['区分'], r['品名'], r['値/型番'], r['数量'], r['Reference'], r['購入先'],
                        r['購入先の型番'], r['販売コード'], r['入数'], '', r[price_col], '', r['購入メモ']])

    on_board = [o for o in out if o['区分'] != '回路図に載っていない部品']
    total_parts = sum(o['合計個数'] for o in on_board)
    priced = [o for o in out if o['金額'] != '']
    unpriced = [o for o in out if o['金額'] == '']
    total_yen = sum(o['金額'] for o in priced)
    date = re.search(r'\d{4}-\d{2}-\d{2}', price_col)

    md = ['# 部品個数まとめ', '',
          '`bom_purchase.csv` から `make_bom_summary.py` で作成。同じ品（同じ購入先の型番）を 1 行にまとめ、合計個数と買う数を出したもの。'
          '部品表で値・足のピッチごとに分かれている行も、買う品が同じならここでは 1 行になる。', '',
          '| 項目 | 数 |', '|---|---|',
          f'| 回路図の部品 | {len(on_board)} 種類・{total_parts} 個 |',
          f'| 回路図に載っていない部品（ケース・ねじ・パネル部品など） | {len(out) - len(on_board) + len(loose)} 種類 |',
          f'| 価格が分かっている品の合計（税込{"、" + date.group(0) + " 時点" if date else ""}） | {total_yen:,} 円（{len(priced)} 種類） |',
          f'| 価格が分かっていない品 | {len(unpriced) + len(loose)} 種類（購入先・型番を確かめてから注文） |',
          '', '買う数は「合計個数 ÷ 入数」の切り上げ（ピンヘッダは 40 ピンで 1 本として計算）。金額 = 買う数 × 単価。', '']
    by_cat = collections.OrderedDict()
    for o in out:
        by_cat.setdefault(o['区分'], []).append(o)
    for r in loose:
        by_cat.setdefault(r['区分'], [])
    for cat, items in by_cat.items():
        cat_qty = sum(o['合計個数'] for o in items)
        n_loose = sum(1 for r in loose if r['区分'] == cat)
        md += [f'## {cat}（{len(items) + n_loose} 種類・{cat_qty} 個' + ('＋「各」の行' if n_loose else '') + '）', '',
               '| 品名 | 値/型番 | 合計個数 | 部品番号 | 購入先 | 型番（販売コード） | 入数 | 買う数 | 金額 | メモ |',
               '|---|---|---:|---|---|---|---|---:|---:|---|']
        for o in items:
            code = o['購入先の型番'] + (f'（{o["販売コード"]}）' if o['販売コード'] else '')
            qty = f'{o["合計個数"]}' + (f'（{o["_pins"]} ピン）' if o['_pins'] else '')
            amount = f'{o["金額"]:,}' if o['金額'] != '' else ''
            md.append(f'| {o["品名"]} | {o["値/型番"]} | {qty} | {o["Reference"]} | {o["購入先"]} | {code} | '
                      f'{o["入数"]} | {o["買う数"]} | {amount} | {o["購入メモ"]} |')
        for r in loose:
            if r['区分'] == cat:
                code = r['購入先の型番'] + (f'（{r["販売コード"]}）' if r['販売コード'] else '')
                md.append(f'| {r["品名"]} | {r["値/型番"]} | {r["数量"]} | {r["Reference"]} | {r["購入先"]} | {code} | '
                          f'{r["入数"]} |  |  | {r["購入メモ"]} |')
        md.append('')
    with open(OUT_MD, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))
    print(f'{os.path.relpath(OUT_CSV)}: {len(out) + len(loose)} 行（回路図の部品 {len(on_board)} 種類・{total_parts} 個、{total_yen:,} 円）')


if __name__ == '__main__':
    main()
