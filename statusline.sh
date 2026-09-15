#!/usr/bin/env bash
# statusline.sh
set -uo pipefail

mapfile -t F < <(jq -r '
  (.model.display_name // "?"),
  (.effort.level // "-"),
  (.context_window.used_percentage // -1 | floor),
  (.rate_limits.five_hour.used_percentage // -1 | floor),
  (.rate_limits.seven_day.used_percentage // -1 | floor),
  (.rate_limits.five_hour.resets_at // 0 | floor),
  (if .prompt_cache == null then "na" elif .prompt_cache.warm then "warm" else "cold" end),
  (.prompt_cache.ttl // "-"),
  (if .prompt_cache.hit_ratio == null then -1 else (.prompt_cache.hit_ratio * 100 | floor) end),
  (.prompt_cache.last_miss_cause.causes[0] // "-"),
  (.prompt_cache.recache_tokens_if_cold // 0 | floor),
  (.workspace.current_dir // "?" | split("/") | last)
')

MODEL=${F[0]}; EFFORT=${F[1]}; CTX=${F[2]}; H5=${F[3]}; D7=${F[4]}
H5_RESET=${F[5]}; WARM=${F[6]}; TTL=${F[7]}; HIT=${F[8]}; MISS=${F[9]}
RECACHE=${F[10]}; DIR=${F[11]}

paint() { printf '\033[%sm%s\033[0m' "$1" "$2"; }
sev() { if [ "$1" -ge 85 ]; then echo 31; elif [ "$1" -ge 60 ]; then echo 33; else echo 32; fi; }

out="$(paint 36 "$DIR")  ${MODEL}/${EFFORT}"

[ "$CTX" -ge 0 ] && out="$out  ctx $(paint "$(sev "$CTX")" "${CTX}%")"

if [ "$H5" -ge 0 ]; then
  left=""
  if [ "$H5_RESET" -gt 0 ]; then
    mins=$(( (H5_RESET - $(date +%s)) / 60 ))
    [ "$mins" -gt 0 ] && [ "$mins" -le 300 ] && left="/${mins}m"
  fi
  out="$out  5h $(paint "$(sev "$H5")" "${H5}%${left}")"
fi

[ "$D7" -ge 0 ] && out="$out  7d $(paint "$(sev "$D7")" "${D7}%")"

if [ "$WARM" = warm ]; then
  out="$out  $(paint 32 "cache ${TTL}")"
elif [ "$WARM" = cold ]; then
  cold="cache cold"
  [ "$MISS" != "-" ] && cold="$cold:$MISS"
  [ "$RECACHE" -gt 0 ] && cold="$cold $(( RECACHE / 1000 ))k"
  out="$out  $(paint 31 "$cold")"
fi

[ "$HIT" -ge 0 ] && out="$out  $(paint 90 "hit ${HIT}%")"

printf '%s' "$out"
