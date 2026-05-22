#!/usr/bin/env bash
# Hermes Qdrant Backup — nas_ra_docs + hermes-ra-knowledge 스냅샷 생성 및 저장
# Usage: ./qdrant_backup.sh [BACKUP_DIR]
# Default: ~/.hermes/snapshots/YYYYMMDD_HHMMSS/

set -euo pipefail

QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
BACKUP_DIR="${1:-$HOME/.hermes/snapshots/$(date +%Y%m%d_%H%M%S)}"
COLLECTIONS=("nas_ra_docs" "hermes-ra-knowledge")

mkdir -p "$BACKUP_DIR"
echo "[backup] 저장 경로: $BACKUP_DIR"
echo "[backup] Qdrant: $QDRANT_URL"

for COL in "${COLLECTIONS[@]}"; do
    echo "[backup] $COL 스냅샷 생성 중..."
    SNAP_RESP=$(python3 -c "
import urllib.request, json, sys
req = urllib.request.Request(
    '$QDRANT_URL/collections/$COL/snapshots',
    method='POST',
    headers={'Content-Type': 'application/json'}
)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
print(data['result']['name'])
")
    echo "[backup] 스냅샷명: $SNAP_RESP"

    echo "[backup] $COL 다운로드 중..."
    python3 -c "
import urllib.request
url = '$QDRANT_URL/collections/$COL/snapshots/$SNAP_RESP'
out = '$BACKUP_DIR/$COL.snapshot'
urllib.request.urlretrieve(url, out)
print(f'[backup] 저장: {out}')
"
    echo "[backup] $COL 완료: $BACKUP_DIR/$COL.snapshot"
done

# indexer_state.db도 함께 복사 (STATE_DB 환경변수 또는 기본값 사용)
DB_SRC="${STATE_DB:-/opt/hermes-ra/indexer_state.db}"
if [ -f "$DB_SRC" ]; then
    cp "$DB_SRC" "$BACKUP_DIR/indexer_state.db"
    echo "[backup] indexer_state.db 복사 완료"
fi

echo ""
echo "=== 백업 완료 ==="
ls -lh "$BACKUP_DIR"
echo ""
echo "이전 시: rsync -avz $BACKUP_DIR/ NEW_PC:~/.hermes/snapshots/restore/"
echo "복원 시: ./qdrant_restore.sh $BACKUP_DIR"
