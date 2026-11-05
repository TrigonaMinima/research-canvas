#!/usr/bin/env bash
# Copied unchanged from TrigonaMinima/discord-notify scripts/build-payload.sh at v2 (a83bc39).
# Build a Discord webhook payload (one embed) from env vars.
# Inputs: STATUS (required), TITLE, URL, DESCRIPTION.
# Optional fields: BRANCH, COMMIT, COMMIT_URL, AUTHOR, TRIGGER, ATTEMPT,
# STARTED_AT + COMPLETED_AT (ISO 8601, gives Duration), FOOTER.
# The timestamp is COMPLETED_AT, else now.
# Empty fields, and fields set to "-", are left out of the embed.
# Bash 3.2 compatible: no ${x,,}, no associative arrays.
set -euo pipefail

# Unset STATUS is a caller bug; empty STATUS is a valid "unknown" (red).
if [ -z "${STATUS+x}" ]; then
  echo "build-payload: STATUS is required (success, failure, cancelled, skipped, ...)" >&2
  exit 1
fi

case "$STATUS" in
  success)           icon="✅"; color=3066993 ;;
  cancelled|skipped) icon="⚪"; color=9807270 ;;
  *)                 icon="❌"; color=15158332 ;;
esac

# jq does all quoting and the duration math, so any text is safe and the
# script stays portable across BSD and GNU date.
jq -n \
  --arg title "$icon ${TITLE:-}" \
  --arg url "${URL:-}" \
  --arg description "${DESCRIPTION:-}" \
  --argjson color "$color" \
  --arg branch "${BRANCH:-}" \
  --arg commit "${COMMIT:-}" \
  --arg commit_url "${COMMIT_URL:-}" \
  --arg author "${AUTHOR:-}" \
  --arg trigger "${TRIGGER:-}" \
  --arg attempt "${ATTEMPT:-}" \
  --arg started "${STARTED_AT:-}" \
  --arg completed "${COMPLETED_AT:-}" \
  --arg footer "${FOOTER:-}" \
  '
  def nonempty(k; v): if v == "" or v == [] then {} else {(k): v} end;
  def short_sha: .[0:7];
  def duration:
    if $started == "" or $completed == "" then ""
    else (($completed | fromdateiso8601) - ($started | fromdateiso8601)) as $s
      | if $s >= 60 then "\($s / 60 | floor)m \($s % 60)s" else "\($s)s" end
    end;

  ([ ["Branch",   $branch],
     ["Commit",   (if $commit == "" then ""
                   elif $commit_url == "" then ($commit | short_sha)
                   else "[\($commit | short_sha)](\($commit_url))" end)],
     ["Author",   $author],
     ["Trigger",  $trigger],
     ["Duration", duration],
     # Attempt 1 is the normal case; only re-runs are worth a field.
     ["Attempt",  (if $attempt == "1" then "" else $attempt end)]
   ] | map(select(.[1] != "" and .[1] != "-") | {name: .[0], value: .[1], inline: true})) as $fields

  | {embeds: [
      {title: $title, color: $color}
      + nonempty("description"; $description)
      + nonempty("url"; $url)
      + nonempty("fields"; $fields)
      + nonempty("footer"; if $footer == "" then "" else {text: $footer} end)
      + {timestamp: (if $completed == "" then now | todate else $completed end)}
    ]}'
