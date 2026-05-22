#!/usr/bin/env python3
"""Hermes Smart Metadata Extractor v1 — NAS RA 문서 메타데이터 자동 추출
온톨로지 기반 카테고리 분류, 파일명 패턴 매칭, Codex/Copilot 활용 메타데이터 추출
"""
import os
import json
import re
import urllib.request
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# =========================================================================
# 설정
# =========================================================================

ONTOLOGY_FILE = os.environ.get("ONTOLOGY_FILE", "/opt/hermes/ra_ontology.json")
CODEX_GATEWAY = os.environ.get("CODEX_GATEWAY_URL", "")
CODEX_AUTH = "Bearer " + os.environ.get("CODEX_GATEWAY_KEY", "sk-hermes-n8n")

# 온톨로지 로드
with open(ONTOLOGY_FILE, "r", encoding="utf-8") as f:
    ONTOLOGY = json.load(f)

# 카테고리 카탈로그 생성
CATEGORY_CATALOG = {cat["id"]: cat for cat in ONTOLOGY["document_categories"]}

# =========================================================================
# 파일명 패턴 기반 카테고리 매핑
# =========================================================================

FOLDER_TO_CATEGORY = {
    # Clinical
    "Clinical evaluation": "clinical_evaluation",
    "CER": "clinical_evaluation",
    "clinical_data": "clinical_evaluation",
    "clinical_evaluation_report": "clinical_evaluation",

    # Test Reports
    "Test": "verification_validation",
    "test": "verification_validation",
    "test_report": "verification_validation",
    "test_protocol": "verification_validation",

    # Design & Engineering
    "3D": "design_and_engineering",
    "CAD": "design_and_engineering",
    "drawing": "design_and_engineering",
    "design": "design_and_engineering",

    # Device Master File
    "DMF": "device_master_file",
    "DHF": "device_master_file",
    "Device Master": "device_master_file",
    "technical file": "device_master_file",

    # Regulatory
    "510(k)": "regulatory_submission",
    "submission": "regulatory_submission",
    "CE": "regulatory_submission",
    "regulatory": "regulatory_submission",

    # Literature
    "Literature": "literature_evidence",
    "literature": "literature_evidence",

    # Risk Management
    "risk": "risk_management",
    "FMEA": "risk_management",
    "hazard": "risk_management",

    # Labeling
    "Label": "labeling",
    "label": "labeling",
    "IFU": "labeling",
    "labeling": "labeling",

    # User Manual
    "User Manual": "user_manual",
    "manual": "user_manual",
    "instructions": "user_manual",

    # PMS & PMCF
    "PMS": "pms_pmcf",
    "PMCF": "pms_pmcf",
    "Post-market": "pms_pmcf",
    "vigilance": "pms_pmcf",

    # Quality Management
    "QMS": "quality_management",
    "SOP": "quality_management",
    "procedure": "quality_management",
    "quality": "quality_management",

    # Manufacturing
    "Manufacturing": "manufacturing_process",
    "process": "manufacturing_process",
    "validation": "verification_validation",

    # Biocompatibility
    "Biocompatibility": "biocompatibility_safety",
    "ISO 10993": "biocompatibility_safety",
    "toxicity": "biocompatibility_safety",

    # Standards
    "Standard": "standards_compliance",
    "GSPR": "standards_compliance",
    "Essential": "standards_compliance",
    "compliance": "standards_compliance",

    # Commercial
    "complaint": "commercial_postmarket",
    "field safety": "commercial_postmarket",
    "postmarket": "commercial_postmarket",
}

# =========================================================================
# 메타데이터 추출 함수들
# =========================================================================

def classify_by_folder_and_filename(filepath: str) -> Tuple[str, float]:
    """
    폴더명과 파일명으로부터 카테고리 자동 분류
    returns: (category_id, confidence_score)
    """
    path = Path(filepath)
    folder_path = str(path.parent)
    filename = path.name

    # 폴더 경로에서 카테고리 매칭
    best_match = None
    best_confidence = 0

    for pattern, category_id in FOLDER_TO_CATEGORY.items():
        if pattern.lower() in folder_path.lower() or pattern.lower() in filename.lower():
            # 매칭 신뢰도 계산 (정확도 기반)
            confidence = len(pattern) / (len(folder_path) + len(filename)) * 100
            if confidence > best_confidence:
                best_match = category_id
                best_confidence = min(confidence, 0.95)  # 최대 95%

    return best_match or "commercial_postmarket", best_confidence

def extract_version_from_filename(filename: str) -> Optional[str]:
    """파일명에서 버전 정보 추출 (v1.0, Rev2, V0.6 등)"""
    patterns = [
        r'[vV](\d+\.?\d*)',
        r'[rR]ev(?:ision)?\.?(\d+)',
        r'[vV]\s*(\d+\.?\d*)',
        r'_(v\d+[a-zA-Z0-9._]*)',
    ]
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            return match.group(0)
    return None

def extract_date_from_filename(filename: str) -> Optional[str]:
    """파일명에서 날짜 추출 (YYYYMMDD, YYYY-MM-DD 등)"""
    patterns = [
        r'(\d{4})-?(\d{2})-?(\d{2})',
        r'(\d{2})/(\d{2})/(\d{4})',
        r'(\d{4})(\d{2})(\d{2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            return match.group(0)
    return None

def extract_product_code(filename: str, folder_path: str) -> Optional[str]:
    """파일명/폴더명에서 제품 코드 추출 (A1417MCW, HAD1717MC 등)"""
    # 의료기기 제품 코드 패턴
    patterns = [
        r'([A-Z]\d{4}[A-Z]{2,3})',  # A1417MCW, HAD1717MC
        r'(CYAN|ADD|Blue|Portable)',  # 제품명
    ]

    combined = f"{folder_path} {filename}".upper()
    for pattern in patterns:
        match = re.search(pattern, combined)
        if match:
            return match.group(1)
    return None

def extract_standard_references(filename: str) -> List[str]:
    """파일명에서 표준 참조 추출 (ISO 13485, IEC 60601 등)"""
    standards = []
    patterns = [
        r'ISO\s*\d{5}-\d+',
        r'IEC\s*\d{5}-\d+',
        r'FDA|CE|USFDA',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, filename, re.IGNORECASE)
        standards.extend(matches)

    return list(set(standards))

def extract_file_metadata(filepath: str) -> Dict:
    """
    파일 경로와 파일시스템 정보로부터 메타데이터 추출
    """
    path = Path(filepath)
    stat = path.stat()

    category_id, category_confidence = classify_by_folder_and_filename(filepath)
    category = CATEGORY_CATALOG.get(category_id, {})

    # 파일 체크섬
    checksum = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                checksum.update(chunk)
        file_hash = checksum.hexdigest()
    except:
        file_hash = None

    # 메타데이터 구성
    metadata = {
        # 코어 필드
        "file_path": filepath,
        "file_name": path.name,
        "file_extension": path.suffix.lower(),
        "file_size": stat.st_size,
        "created_date": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "modified_date": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "checksum": file_hash,

        # 카테고리
        "document_category": category_id,
        "category_name": category.get("name", "Unknown"),
        "category_confidence": category_confidence,

        # 추출된 메타데이터
        "version": extract_version_from_filename(path.name),
        "date_in_filename": extract_date_from_filename(path.name),
        "product_code": extract_product_code(path.name, str(path.parent)),
        "standard_references": extract_standard_references(path.name),

        # 추출 품질 표시
        "extraction_timestamp": datetime.now().isoformat(),
        "extraction_confidence": {
            "category": category_confidence,
            "version": 0.7 if extract_version_from_filename(path.name) else 0,
            "date": 0.8 if extract_date_from_filename(path.name) else 0,
            "product": 0.7 if extract_product_code(path.name, str(path.parent)) else 0,
        }
    }

    return metadata

def call_codex_for_sample_analysis(filepath: str, category_id: str, sample_text: str) -> Optional[Dict]:
    """
    주요 문서 샘플을 Codex로 분석하여 메타데이터 추출
    (선택: CODEX_GATEWAY_URL 환경변수 미설정 시 skip)
    """
    if not CODEX_GATEWAY:
        return None
    category = CATEGORY_CATALOG.get(category_id, {})
    category_name = category.get("name", "Document")

    prompt = f"""
이 문서는 "{category_name}" 카테고리에 속합니다.
파일명: {Path(filepath).name}

아래 문서 샘플(처음 2000자)을 분석하고, 다음 정보만 JSON으로 추출하세요:
1. 문서의 정확한 제목
2. 문서 버전 (명시적으로 기재된 경우)
3. 승인 상태 (Draft, Released, Approved 등)
4. 적용 제품명/모델명 (해당하는 경우)
5. 핵심 주제 또는 클레임 (3-5개 키워드)

JSON만 출력하세요. 다른 텍스트는 없이.

---
{sample_text[:2000]}
---
"""

    try:
        payload = json.dumps({
            "model": "gpt-4",
            "messages": [
                {
                    "role": "system",
                    "content": "의료기기 규제/인허가 전문가. JSON만 출력."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": 500
        }).encode()

        req = urllib.request.Request(
            CODEX_GATEWAY,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": CODEX_AUTH
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
            if data and "choices" in data:
                response = data["choices"][0]["message"]["content"]

                # JSON 파싱
                import re
                response = re.sub(r"```json\s*", "", response)
                response = re.sub(r"```\s*", "", response)

                return json.loads(response)
    except Exception as e:
        print(f"[warn] Codex analysis failed for {Path(filepath).name}: {e}", flush=True)

    return None

def merge_metadata(file_metadata: Dict, codex_metadata: Optional[Dict]) -> Dict:
    """파일 시스템 메타데이터와 Codex 추출 메타데이터 병합"""
    if not codex_metadata:
        return file_metadata

    # Codex 결과를 기존 메타데이터에 병합
    for key, value in codex_metadata.items():
        if key.startswith("codex_"):
            continue
        if value and key not in file_metadata:
            file_metadata[f"codex_{key}"] = value

    return file_metadata

# =========================================================================
# 메인: 메타데이터 추출 실행
# =========================================================================

if __name__ == "__main__":
    # 테스트용: 샘플 파일들로 메타데이터 추출 테스트
    test_files = [
        "/mnt/nas-ra/공통자료/RA/06. Clinical evaluation report/A-CER-01_Clinical Evaluation Report 250901.pdf",
        "/mnt/nas-ra/공통자료/RA/A-TCF-5-156 Test Reports/1. [A1417MCW, A1717MCW, F1417MCW] IEC 60601-1 CB C.pdf",
        "/mnt/nas-ra/공통자료/RA/★Label/CYAN/Label_CYAN_rev2_EN.pdf",
    ]

    print("=== Smart Metadata Extraction Test ===\n")

    for fpath in test_files:
        if not os.path.exists(fpath):
            print(f"⚠️  파일 없음: {fpath}")
            continue

        print(f"📄 {Path(fpath).name}")
        try:
            metadata = extract_file_metadata(fpath)
            print(f"  ✓ Category: {metadata['category_name']} (confidence: {metadata['category_confidence']:.1f}%)")
            print(f"  ✓ Version: {metadata['version']}")
            print(f"  ✓ Product: {metadata['product_code']}")
            print(f"  ✓ Standards: {metadata['standard_references']}")
            print()
        except Exception as e:
            print(f"  ✗ Error: {e}\n")

    print("✓ 메타데이터 추출 엔진 준비 완료")
    print(f"  온톨로지: {len(ONTOLOGY['document_categories'])} 카테고리")
    print(f"  메타데이터 필드: {len(ONTOLOGY['metadata_schema']['core_fields'])} + 추가 필드들")
