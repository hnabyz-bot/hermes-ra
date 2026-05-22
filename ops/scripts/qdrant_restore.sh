#!/usr/bin/env bash
# Hermes Qdrant Restore — 스냅샷으로부터 컬렉션 복원
# Usage: ./qdrant_restore.sh BACKUP_DIR [--reindex]
# --reindex: 스냅샷 없이 NAS에서 처음부터 재인덱싱 (수 시간 소요)

set -euo pipefail

QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
BACKUP_DIR="${1:-}"
REINDEX="${2:-}"
COLLECTIONS=("nas_ra_docs" "hermes-ra-knowledge")
STATE_DB="${STATE_DB_PATH:-/opt/hermes/indexer_state.db}"

# Qdrant 응답 대기
wait_qdrant() {
    echo "[restore] Qdrant 연결 대기..."
    for i in {1..30}; do
        python3 -c "
import urllib.request
try:
    urllib.request.urlopen('$QDRANT_URL/healthz', timeout=2)
    print('ok')
except: pass
" | grep -q ok && break
        sleep 2
    done
    echo "[restore] Qdrant 준비됨"
}

if [ "$REINDEX" = "--reindex" ] || [ -z "$BACKUP_DIR" ]; then
    echo "[restore] === NAS 재인덱싱 모드 (수 시간 소요) ==="
    echo "[restore] indexer_state.db 초기화 중..."
    python3 -c "
import sqlite3
conn = sqlite3.connect('$STATE_DB')
conn.execute('DELETE FROM indexed_files')
conn.commit()
conn.close()
print('[restore] DB 초기화 완료')
"
    echo "[restore] nas_indexer.py 실행..."
    python3 /opt/hermes/nas_indexer.py
    exit 0
fi

if [ ! -d "$BACKUP_DIR" ]; then
    echo "ERROR: 백업 디렉토리 없음: $BACKUP_DIR"
    echo "Usage: $0 BACKUP_DIR [--reindex]"
    exit 1
fi

wait_qdrant

for COL in "${COLLECTIONS[@]}"; do
    SNAP_FILE="$BACKUP_DIR/$COL.snapshot"
    if [ ! -f "$SNAP_FILE" ]; then
        echo "[restore] WARNING: $SNAP_FILE 없음, 건너뜀"
        continue
    fi

    echo "[restore] $COL 복원 중 ($SNAP_FILE)..."

    # 기존 컬렉션 삭제 (있으면)
    python3 -c "
import urllib.request, json
try:
    req = urllib.request.Request('$QDRANT_URL/collections/$COL', method='DELETE')
    urllib.request.urlopen(req)
    print('[restore] 기존 컬렉션 삭제됨')
except: pass
"

    # 스냅샷 업로드 및 복원
    python3 -c "
import urllib.request, json, os

snap_path = '$SNAP_FILE'
col = '$COL'
qdrant_url = '$QDRANT_URL'

with open(snap_path, 'rb') as f:
    data = f.read()

boundary = 'hermesrestore'
body = (
    f'--{boundary}\r\n'
    f'Content-Disposition: form-data; name=\"snapshot\"; filename=\"{os.path.basename(snap_path)}\"\r\n'
    f'Content-Type: application/octet-stream\r\n\r\n'
).encode() + data + f'\r\n--{boundary}--\r\n'.encode()

req = urllib.request.Request(
    f'{qdrant_url}/collections/{col}/snapshots/upload?priority=snapshot',
    data=body,
    method='POST',
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
)
resp = json.loads(urllib.request.urlopen(req).read())
print(f'[restore] {col}: {resp}')
"
    echo "[restore] $COL 복원 완료"
done

# indexer_state.db 복원
DB_BAK="$BACKUP_DIR/indexer_state.db"
if [ -f "$DB_BAK" ]; then
    cp "$DB_BAK" "$STATE_DB"
    echo "[restore] indexer_state.db 복원 완료"
fi

echo ""
echo "=== 복원 완료 ==="
python3 -c "
import urllib.request, json
resp = json.loads(urllib.request.urlopen('$QDRANT_URL/collections').read())
for c in resp['result']['collections']:
    info = json.loads(urllib.request.urlopen(f'$QDRANT_URL/collections/{c[\"name\"]}').read())
    pts = info['result'].get('points_count', '?')
    print(f'  {c[\"name\"]}: {pts} points')
"
