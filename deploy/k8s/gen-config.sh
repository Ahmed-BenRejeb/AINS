#!/usr/bin/env bash
# Generate the (gitignored) configmap.yaml + secret.yaml from the repo-root .env.
#
#   bash deploy/k8s/gen-config.sh [path/to/.env]
#
# The four in-cluster service URLs are forced to the Kubernetes Service DNS names
# (overriding any localhost values in .env), so the same .env drives both the VM
# deployment and the cluster. The outputs are gitignored (see .gitignore).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env}"
NS="sentinel"

if [ ! -f "$ENV_FILE" ]; then
  echo "error: no .env found at '$ENV_FILE' (pass a path as the first argument)" >&2
  exit 1
fi

# Read KEY=value from the env file: take the first match, drop an inline '# comment',
# trim surrounding whitespace.
val() {
  grep -E "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

SECRET_KEYS="CLOUDFLARE_ACCOUNT_ID CLOUDFLARE_API_TOKEN CF_AI_ACCOUNT_ID CF_AI_API_TOKEN \
CF_D1_DATABASE_ID BLOB_STORAGE_SECRET_KEY ATLASSIAN_API_TOKEN LANGFUSE_PUBLIC_KEY \
LANGFUSE_SECRET_KEY AUDIT_HMAC_KEY FORGE_REMOTE_SECRET"

# Config keys pulled from .env as-is (only when present + non-empty).
CONFIG_KEYS="CF_AI_MODEL_MAIN CF_AI_MODEL_SAFETY CF_AI_MODEL_EMBED CF_VECTORIZE_INDEX \
BLOB_STORAGE_BUCKET BLOB_STORAGE_ACCESS_KEY XQDRANT_INCIDENTS_COLLECTION \
XQDRANT_RUNBOOKS_COLLECTION ATLASSIAN_SITE ATLASSIAN_EMAIL ATLASSIAN_JSM_SERVICE_DESK_ID \
ATLASSIAN_JIRA_PROJECT_KEY ATLASSIAN_DUPLICATE_LINK_TYPE EVAL_CONFIDENCE_THRESHOLD \
VECTOR_SIMILARITY_THRESHOLD RUNBOOK_SIMILARITY_THRESHOLD FLIGHT_MODE LANGFUSE_HOST \
LANGFUSE_HOST_INTERNAL FORGE_REMOTE_URL DASHBOARD_URL OTEL_SEMCONV_STABILITY_OPT_IN LOG_LEVEL"

tmp_secret="$(mktemp)"
tmp_config="$(mktemp)"
trap 'rm -f "$tmp_secret" "$tmp_config"' EXIT

for k in $SECRET_KEYS; do
  printf '%s=%s\n' "$k" "$(val "$k")" >> "$tmp_secret"
done

for k in $CONFIG_KEYS; do
  v="$(val "$k")"
  [ -n "$v" ] && printf '%s=%s\n' "$k" "$v" >> "$tmp_config"
done

# In-cluster Service DNS (always override whatever .env had).
cat >> "$tmp_config" <<'EOF'
XQDRANT_URL=http://xqdrant:6333
EVAL_ENGINE_URL=http://eval-engine:8000
FLIGHT_RECORDER_URL=http://flight-recorder:8001
BLOB_STORAGE_ENDPOINT=http://minio:9000
EVAL_ENGINE_INTERNAL_URL=http://eval-engine:8000
FLIGHT_RECORDER_INTERNAL_URL=http://flight-recorder:8001
BLOB_STORAGE_USE_SSL=false
EOF

kubectl create configmap sentinel-config -n "$NS" \
  --from-env-file="$tmp_config" --dry-run=client -o yaml > "$SCRIPT_DIR/configmap.yaml"
kubectl create secret generic sentinel-secrets -n "$NS" \
  --from-env-file="$tmp_secret" --dry-run=client -o yaml > "$SCRIPT_DIR/secret.yaml"

echo "✓ wrote $SCRIPT_DIR/configmap.yaml and $SCRIPT_DIR/secret.yaml (gitignored)"
