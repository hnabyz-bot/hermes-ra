#!/usr/bin/env bash
# Hermes RA — 신규 PC 셋업 스크립트 (T3610 / abyz-lab)
# Usage: sudo ./setup_new_pc.sh [--restore-snapshot BACKUP_DIR] [--reindex]

set -euo pipefail

HERMES_DIR="/opt/hermes"
HERMES_USER="${SUDO_USER:-abyz-lab}"
RESTORE_DIR=""
REINDEX=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --restore-snapshot) RESTORE_DIR="$2"; shift 2 ;;
        --reindex) REINDEX=true; shift ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

echo "=== Hermes RA 신규 PC 셋업 ==="
echo "User: $HERMES_USER | Hermes: $HERMES_DIR"

# 1. 시스템 패키지
echo "[1/7] 시스템 패키지 설치..."
apt-get update -q
apt-get install -y -q python3 python3-pip python3-venv poppler-utils cifs-utils curl flask

# 2. Python 패키지
echo "[2/7] Python 패키지 설치..."
pip3 install -q flask requests python-docx python-pptx openpyxl

# 3. /opt/hermes 디렉토리 및 스크립트 (T3610 활성 스크립트 배포)
echo "[3/7] Hermes 스크립트 배포..."
mkdir -p "$HERMES_DIR"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cp "$REPO_ROOT/scripts/hermes-api-server.py" "$HERMES_DIR/"
cp "$REPO_ROOT/scripts/nas_indexer.py" "$HERMES_DIR/"
cp "$REPO_ROOT/scripts/nas_indexer_v2.py" "$HERMES_DIR/"
cp "$REPO_ROOT/scripts/nas_scanner.py" "$HERMES_DIR/"
cp "$REPO_ROOT/scripts/meta_extractor.py" "$HERMES_DIR/"
cp "$REPO_ROOT/scripts/extract_mail_qa.py" "$HERMES_DIR/"
cp "$REPO_ROOT/scripts/ra_analyze.py" "$HERMES_DIR/"
cp "$REPO_ROOT/scripts/index_ra_knowledge.py" "$HERMES_DIR/"
cp "$REPO_ROOT/scripts/index_github_repos.py" "$HERMES_DIR/"
chown -R "$HERMES_USER:$HERMES_USER" "$HERMES_DIR"
echo "   → $HERMES_DIR 배포 완료"

# 4. .env 설정 (없는 경우 템플릿 복사)
if [ ! -f "$HERMES_DIR/.env" ]; then
    cp "$REPO_ROOT/config/dotenv/hermes.env.example" "$HERMES_DIR/.env"
    chown "$HERMES_USER:$HERMES_USER" "$HERMES_DIR/.env"
    chmod 600 "$HERMES_DIR/.env"
    echo "[4/7] .env 템플릿 복사됨 → $HERMES_DIR/.env 편집 필요"
    echo "   필수 항목: GLM_API_KEY, OPENPROJECT_API_KEY, OPENPROJECT_BASE_URL, API_SERVER_KEY"
else
    echo "[4/7] .env 이미 존재, 건너뜀"
fi

# 5. NAS 마운트 설정
echo "[5/7] NAS 마운트 설정..."
NAS_MOUNT="/mnt/nas-ra"
NAS_CREDS="/etc/samba/nas-ra.creds"
mkdir -p "$NAS_MOUNT"

if [ ! -f "$NAS_CREDS" ]; then
    cp "$REPO_ROOT/config/nas/nas-ra.creds.example" "$NAS_CREDS"
    chmod 600 "$NAS_CREDS"
    echo "   → $NAS_CREDS 생성됨 (username/password 입력 필요)"
fi

FSTAB_ENTRY="//100.126.59.10/DR_Dev /mnt/nas-ra cifs credentials=/etc/samba/nas-ra.creds,uid=$HERMES_USER,gid=$HERMES_USER,iocharset=utf8,vers=3.0,_netdev 0 0"
if ! grep -q "DR_Dev" /etc/fstab 2>/dev/null; then
    echo "$FSTAB_ENTRY" >> /etc/fstab
    echo "   → fstab 항목 추가됨"
    echo "   → 자격증명 입력 후: mount /mnt/nas-ra"
else
    echo "   → fstab 항목 이미 존재"
fi

# 6. systemd 서비스 설치 (T3610 서비스만)
echo "[6/7] systemd 서비스 설치..."
for SVC in hermes-gateway hermes-api-server hermes-indexer hermes-nas-scanner; do
    SVC_FILE="$REPO_ROOT/config/systemd/$SVC.service"
    if [ -f "$SVC_FILE" ]; then
        cp "$SVC_FILE" /etc/systemd/system/
        echo "   → $SVC.service 설치됨"
    fi
done
systemctl daemon-reload

# 7. Qdrant 데이터 복원
echo "[7/7] Qdrant 데이터 복원..."
if [ -n "$RESTORE_DIR" ] && [ -d "$RESTORE_DIR" ]; then
    echo "   스냅샷 복원: $RESTORE_DIR"
    sudo -u "$HERMES_USER" bash "$REPO_ROOT/ops/scripts/qdrant_restore.sh" "$RESTORE_DIR"
elif [ "$REINDEX" = true ]; then
    echo "   NAS 재인덱싱 (NAS 마운트 후 수 시간 소요)..."
    sudo -u "$HERMES_USER" python3 "$HERMES_DIR/nas_indexer.py" --force-reindex
else
    echo "   SKIP: --restore-snapshot 또는 --reindex 옵션 필요"
    echo "   나중에 수동으로 실행:"
    echo "     옵션A: bash ops/scripts/qdrant_restore.sh ~/.hermes/snapshots/restore/"
    echo "     옵션B: python3 /opt/hermes/nas_indexer.py --force-reindex"
fi

echo ""
echo "=== 셋업 완료 ==="
echo "다음 단계:"
echo "  1. $HERMES_DIR/.env 편집 (GLM_API_KEY, OPENPROJECT_API_KEY, API_SERVER_KEY 등)"
echo "  2. $NAS_CREDS 편집 (username, password)"
echo "  3. mount $NAS_MOUNT"
echo "  4. systemctl enable --now hermes-gateway hermes-api-server"
echo "  5. curl http://localhost:8643/health"
