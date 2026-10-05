where=$(awk '/^CONFIRMED/{c=1;next} /^PLAUSIBLE/{c=0} c&&/^WHERE:/{print;c=0}' "$AGENT_OUT")
printf '%s\n' "$where" | grep -qE 'pricing\.py:(8|9)\b|api\.py:1[0-6]\b' && { echo "the ratio helper is guarded by its caller (whole <= 0 is rejected) and must not be CONFIRMED: $where"; exit 1; }
printf '%s\n' "$where" | grep -qE 'pricing\.py:[45]\b|api\.py:[678]\b' || { echo "the unbounded discount percent was not CONFIRMED: $where"; exit 1; }
