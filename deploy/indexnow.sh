#!/usr/bin/env bash
# Tell IndexNow search engines (Bing, which feeds ChatGPT search and Copilot, plus Yandex,
# Seznam, Naver) that the public pages changed. Run after a deploy:
#   deploy/indexnow.sh                      # every URL in the live sitemap
#   deploy/indexnow.sh /pricing /compare    # just these paths
# The key is public by design: IndexNow checks it at https://<host>/<key>.txt
# (web/public/<key>.txt; Wasila ships without one). Operators should make their own key file and set INDEXNOW_KEY.
set -euo pipefail

SITE_URL="${SITE_URL:-https://wasila.app}"
KEY="${INDEXNOW_KEY:?set INDEXNOW_KEY and publish web/public/$INDEXNOW_KEY.txt}"
HOST="${SITE_URL#https://}"
HOST="${HOST%%/*}"

if [ "$#" -gt 0 ]; then
  urls=$(for p in "$@"; do printf '%s%s\n' "$SITE_URL" "$p"; done)
else
  urls=$(curl -fsS "$SITE_URL/sitemap.xml" | grep -o '<loc>[^<]*</loc>' | sed -e 's/<loc>//' -e 's#</loc>##')
fi

json_urls=$(printf '%s\n' "$urls" | sed -e 's/.*/"&"/' | paste -sd, -)
body="{\"host\":\"$HOST\",\"key\":\"$KEY\",\"keyLocation\":\"$SITE_URL/$KEY.txt\",\"urlList\":[$json_urls]}"

code=$(curl -sS -o /dev/null -w '%{http_code}' -X POST https://api.indexnow.org/indexnow \
  -H 'Content-Type: application/json; charset=utf-8' --data "$body")
echo "IndexNow: $(printf '%s\n' "$urls" | wc -l | tr -d ' ') URLs, HTTP $code (200 or 202 means accepted)"
