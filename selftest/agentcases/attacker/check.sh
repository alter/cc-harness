grep -q '^attack:failed' tasks/30-notify/01-push/labels.txt || { echo "the push task was not marked attack:failed"; exit 1; }
test -f tasks/30-notify/01-push/ATTACK.md || { echo "no ATTACK.md"; exit 1; }
where=$(awk '/^CONFIRMED/{c=1;next} /^PLAUSIBLE/{c=0} c&&/^WHERE:/{print;c=0}' "$AGENT_OUT" tasks/30-notify/01-push/ATTACK.md)
printf '%s\n' "$where" | grep -q 'push\.py' || { echo "the unescaped html/link sink in push.py was not CONFIRMED: $where"; exit 1; }
printf '%s\n' "$where" | grep -qiE "user_id" && { echo "user_id is validated at the input (exact int, int64 range) and must not be CONFIRMED: $where"; exit 1; }
exit 0
