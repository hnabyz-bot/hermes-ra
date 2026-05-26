#!/usr/bin/env bash
# Hermes RA — T3610 신규 PC 셋업 (Nous Hermes Agent v0.13.0 기준)
# Usage: sudo ./setup_new_pc.sh [--restore-snapshot BACKUP_DIR] [--reindex]
#
# 인프라: /opt/hermes-ra/ (Python 인덱서, HTTP 브리지)
# 인텔리전스: ~/.hermes/skills/ra-expert/ (심링크 → /opt/hermes-ra/skills/ra-expert/)

set -euo pipefail

HERMES_RA_DIR="/opt/hermes-ra"
HERMES_USER="${SUDO_USER:-abyz-lab}"
HERMES_HOME="/home/$HERMES_USER"
RESTORE_DIR=""
REINDEX=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --restore-snapshot) RESTORE_DIR="$2"; shift 2 ;;
        --reindex) REINDEX=true; shift ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=== Hermes RA 신규 PC 셋업 (T3610 Nous Agent 기준) ==="
echo "User: $HERMES_USER | Infra: $HERMES_RA_DIR | Repo: $REPO_ROOT"

# 1. 시스템 패키지
echo "[1/8] 시스템 패키지 설치..."
apt-get update -q
apt-get install -y -q python3 python3-pip python3-venv poppler-utils cifs-utils curl

# 2. Python 패키지 (hermes venv 사용)
echo "[2/8] Python 패키지 설치..."
HERMES_PIP="$HERMES_HOME/.hermes/hermes-agent/venv/bin/pip3"
if [ -f "$HERMES_PIP" ]; then
    sudo -u "$HERMES_USER" "$HERMES_PIP" install -q flask requests python-docx python-pptx openpyxl psycopg2-binary
else
    pip3 install -q --break-system-packages flask requests python-docx python-pptx openpyxl psycopg2-binary
fi

# 3. /opt/hermes-ra/ 디렉터리 및 인프라 스크립트 배포
echo "[3/8] 인프라 스크립트 배포 ($HERMES_RA_DIR)..."
mkdir -p "$HERMES_RA_DIR"

INFRA_SCRIPTS=(
    "hermes-api-server.py"
    "nas_indexer.py"
    "nas_indexer_v2.py"
    "meta_extractor.py"
    "extract_mail_qa.py"
    "index_ra_knowledge.py"
    "index_github_repos.py"
)
for SCRIPT in "${INFRA_SCRIPTS[@]}"; do
    if [ -f "$REPO_ROOT/scripts/$SCRIPT" ]; then
        cp "$REPO_ROOT/scripts/$SCRIPT" "$HERMES_RA_DIR/"
    fi
done

# RA Expert Skill 배포 (인프라 경로에 복사)
if [ -d "$REPO_ROOT/skills/ra-expert" ]; then
    mkdir -p "$HERMES_RA_DIR/skills"
    cp -r "$REPO_ROOT/skills/ra-expert" "$HERMES_RA_DIR/skills/"
    echo "   → skills/ra-expert/ 배포 완료"
fi

chown -R "$HERMES_USER:$HERMES_USER" "$HERMES_RA_DIR"
echo "   → $HERMES_RA_DIR 배포 완료"

# 4. RA Expert Skill 심링크 (Hermes Agent 스킬 디렉터리로)
echo "[4/8] RA Expert Skill 심링크 설정..."
HERMES_SKILLS_DIR="$HERMES_HOME/.hermes/skills"
RA_SKILL_TARGET="$HERMES_RA_DIR/skills/ra-expert"
RA_SKILL_LINK="$HERMES_SKILLS_DIR/ra-expert"

if [ -d "$HERMES_SKILLS_DIR" ] && [ -d "$RA_SKILL_TARGET" ]; then
    # 기존 심링크 또는 디렉터리 제거
    if [ -L "$RA_SKILL_LINK" ] || [ -d "$RA_SKILL_LINK" ]; then
        rm -rf "$RA_SKILL_LINK"
    fi
    sudo -u "$HERMES_USER" ln -s "$RA_SKILL_TARGET" "$RA_SKILL_LINK"
    echo "   → 심링크 생성: $RA_SKILL_LINK → $RA_SKILL_TARGET"
else
    echo "   SKIP: $HERMES_SKILLS_DIR 또는 $RA_SKILL_TARGET 없음"
    echo "   hermes 설치 후 수동으로 실행:"
    echo "     ln -s $RA_SKILL_TARGET $RA_SKILL_LINK"
fi

# 5. .env 설정
if [ ! -f "$HERMES_RA_DIR/.env" ]; then
    if [ -f "$REPO_ROOT/config/dotenv/hermes.env.example" ]; then
        cp "$REPO_ROOT/config/dotenv/hermes.env.example" "$HERMES_RA_DIR/.env"
    else
        cat > "$HERMES_RA_DIR/.env" << 'ENVEOF'
OPENPROJECT_API_KEY=
OPENPROJECT_BASE_URL=https://plm.abyz-lab.work
QDRANT_URL=http://localhost:6333
OLLAMA_URL=http://192.168.100.1:11434
EMBED_MODEL=qwen3-embedding:latest
NAS_RA_PATH=/mnt/nas-ra/공통자료/RA
API_SERVER_KEY=
HERMES_BIN=/home/abyz-lab/.local/bin/hermes
API_SERVER_PORT=8643
HERMES_RA_DIR=/opt/hermes-ra
ENVEOF
    fi
    chown "$HERMES_USER:$HERMES_USER" "$HERMES_RA_DIR/.env"
    chmod 600 "$HERMES_RA_DIR/.env"
    echo "[5/8] .env 템플릿 생성 → $HERMES_RA_DIR/.env 편집 필요"
    echo "   필수: OPENPROJECT_API_KEY, API_SERVER_KEY"
    echo "   OLLAMA_URL=http://192.168.100.1:11434 (GX10 2.5G 직결)"
else
    echo "[5/8] .env 이미 존재, 건너뜀"
fi

# 6. NAS 마운트 설정
echo "[6/8] NAS 마운트 설정..."
NAS_MOUNT="/mnt/nas-ra"
NAS_CREDS="/etc/samba/nas-ra.creds"
mkdir -p "$NAS_MOUNT"
mkdir -p /etc/samba

if [ ! -f "$NAS_CREDS" ]; then
    if [ -f "$REPO_ROOT/config/nas/nas-ra.creds.example" ]; then
        cp "$REPO_ROOT/config/nas/nas-ra.creds.example" "$NAS_CREDS"
    else
        cat > "$NAS_CREDS" << 'CREDSEOF'
username=
password=
CREDSEOF
    fi
    chmod 600 "$NAS_CREDS"
    echo "   → $NAS_CREDS 생성됨 (username/password 입력 필요)"
fi

FSTAB_ENTRY="//100.126.59.10/DR_Dev /mnt/nas-ra cifs credentials=/etc/samba/nas-ra.creds,uid=$HERMES_USER,gid=$HERMES_USER,iocharset=utf8,vers=3.0,_netdev 0 0"
if ! grep -q "DR_Dev" /etc/fstab 2>/dev/null; then
    echo "$FSTAB_ENTRY" >> /etc/fstab
    echo "   → fstab 항목 추가됨 (자격증명 입력 후: mount $NAS_MOUNT)"
else
    echo "   → fstab 항목 이미 존재"
fi

# 7. systemd 서비스 설치
echo "[7/8] systemd 서비스 설치..."
for SVC in hermes-gateway hermes-api-server hermes-indexer; do
    SVC_FILE="$REPO_ROOT/config/systemd/$SVC.service"
    if [ -f "$SVC_FILE" ]; then
        cp "$SVC_FILE" /etc/systemd/system/
        echo "   → $SVC.service 설치됨"
    fi
done
systemctl daemon-reload

# 8. Qdrant 스냅샷 복원 또는 재인덱싱
echo "[8/8] Qdrant 데이터 복원..."
if [ -n "$RESTORE_DIR" ] && [ -d "$RESTORE_DIR" ]; then
    echo "   스냅샷 복원: $RESTORE_DIR"
    sudo -u "$HERMES_USER" bash "$REPO_ROOT/ops/scripts/qdrant_restore.sh" "$RESTORE_DIR"
elif [ "$REINDEX" = true ]; then
    echo "   NAS 재인덱싱 (NAS 마운트 후 수 시간 소요)..."
    sudo -u "$HERMES_USER" HERMES_RA_DIR="$HERMES_RA_DIR" \
        python3 "$HERMES_RA_DIR/nas_indexer.py" --force-reindex
else
    echo "   SKIP: --restore-snapshot 또는 --reindex 옵션 필요"
    echo "   나중에 수동 실행:"
    echo "     옵션A (권장): bash ops/scripts/qdrant_restore.sh ~/.hermes/snapshots/restore/"
    echo "     옵션B: python3 $HERMES_RA_DIR/nas_indexer.py --force-reindex"
fi

echo ""
echo "=== 셋업 완료 ==="
echo ""
echo "다음 단계:"
echo "  1. $HERMES_RA_DIR/.env 편집 (OPENPROJECT_API_KEY, API_SERVER_KEY)"
echo "  2. $NAS_CREDS 편집 (username, password)"
echo "  3. mount $NAS_MOUNT"
echo "  4. systemctl enable --now hermes-gateway hermes-api-server"
echo "  5. hermes -z 'MFDS 의료기기 소프트웨어 허가 요건'  # RA Expert Skill 검증"
echo "  6. curl http://localhost:8643/health"
echo ""
echo "RA Expert Skill 심링크 확인:"
echo "  ls -la $HERMES_HOME/.hermes/skills/ra-expert"
