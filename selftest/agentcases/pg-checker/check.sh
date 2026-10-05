out=$(cat "$AGENT_OUT")
printf '%s\n' "$out" | grep -qE 'orders\.py:(9|1[01])' || { echo "the API call inside the open transaction in orders.py was not reported"; exit 1; }
printf '%s\n' "$out" | grep -qiE 'BLOCK' || { echo "the held transaction was not marked BLOCK"; exit 1; }
printf '%s\n' "$out" | grep -qiE 'orders[^a-z]*\(?user_id|user_id.*index|index.*user_id' || { echo "the foreign key orders.user_id without an index was not reported"; exit 1; }
awk '/^(Q1|Q2)/{h=$0} /^WHERE:/{print h" "$0}' "$AGENT_OUT" | grep -E 'CONFIRMED' | grep -q 'rates\.py' && { echo "rates.py fetches before the transaction and must not be CONFIRMED"; exit 1; }
exit 0
