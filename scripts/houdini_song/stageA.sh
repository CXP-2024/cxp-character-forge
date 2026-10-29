#!/bin/bash
# Local stage for the full-song extension: export (F0..F1) + Vellum solve.  usage: stageA.sh DIRNAME F0 F1
set -e
D=${SV_DIR:-$(pwd)}; N=$1; F=$D/$N; SRC=$F/src.blend
B="${BLENDER:-blender}"; H="${HYTHON:-hython}"
cd $D
echo "START $(date +%T)"
"$B" -b $SRC -P export.py -- $F $2 $3 2>&1 | grep -E "EXPORTED|Error"
"$B" -b $SRC -P export_acc.py -- $F $2 $3 2>&1 | grep -E "ACC|Error"
"$B" -b $SRC -P export_hair.py -- $F $2 $3 2>&1 | grep -E "HAIR|Error"
python patterns.py $N 96 34
echo "SOLVE_START $(date +%T)"
"$H" solve.py $F 45 '{"cloth":{"bendstiffness":0.015,"thickness":0.003,"density":0.18,"benddampingratio":0.08},"solver":{"substeps":5,"niter":80}}' 2>&1 | grep -E "SOLVE .*00 of|DONE|Error"
echo "STAGEA_DONE $(date +%T)"
