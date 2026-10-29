# Claim real-skirt solve segments in order (mkdir lock) and solve them; DIR index = song frame - BASE.
# usage: bash seg_queue.sh HYTHON DIR BASE "start1 start2 ..." LEN TAG OVJSON
HY=$1; D=$2; BASE=$3; STARTS=$4; LEN=$5; TAG=$6; OV=$7
for s in $STARTS; do
  mkdir "$D/seg_${TAG}_$s.lock" 2>/dev/null || continue
  a=$((s - BASE)); b=$((a + LEN - 1)); mx=$(( $(cat "$D/.nframes") - 1 )); [ $b -gt $mx ] && b=$mx
  "$HY" solve_real2.py "$D" 60 $a $b "$D/seg_${TAG}_$s.npy" "$OV" > "$D/seg_${TAG}_$s.log" 2>&1 && echo "SEGDONE $s" || echo "SEGFAIL $s"
done
