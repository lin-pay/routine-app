#!/bin/zsh
# 1セット分: ラスタライズ（未完なら作り直し）→ OCR
P=$1; T=$2; k=$3
cd $P || exit 1
n=$(pdfinfo $k.pdf | awk '/^Pages:/{print $2}')
have=$(ls img_$k 2>/dev/null | wc -l | tr -d ' ')
if [ "$have" != "$n" ]; then rm -rf img_$k; mkdir -p img_$k; pdftoppm -r 200 -png -gray $k.pdf img_$k/p; fi
[ -s ocr_$k.jsonl ] || { $T/ocr img_$k/*.png > ocr_$k.jsonl.tmp && mv ocr_$k.jsonl.tmp ocr_$k.jsonl; }
echo "done $k pages=$n ocr=$(wc -l < ocr_$k.jsonl)"
