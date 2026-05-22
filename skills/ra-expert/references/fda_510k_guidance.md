# FDA 510(k) Substantial Equivalence + SaMD Guidance 요약

> 기준: Federal Food, Drug, and Cosmetic Act (FD&C Act), 21 CFR Part 807
> 참조: FDA Guidance Documents, IMDRF SaMD Framework
> 현재(2026): QMSR (21 CFR Part 820 revision, ISO 13485 harmonized) 시행 중

---

## 1. FDA 의료기기 규제 체계

### 기기 분류 (21 CFR Parts 862-892)

| 클래스 | 위험도 | 규제 수단 | 비율 |
|--------|--------|---------|------|
| Class I | 낮음 | General Controls + Exempt | ~47% |
| Class II | 중간 | General + Special Controls + 510(k) | ~43% |
| Class III | 높음 | PMA (Premarket Approval) | ~10% |

### 규제 경로 선택

```
신제품 → Class 조회 (FDA 기기 패널 + 21 CFR)
    ↓
Class I → Exempt (대부분) 또는 510(k)
Class II → 510(k) (원칙) 또는 De Novo (새 유형)
Class III → PMA (원칙) 또는 Down-classify (De Novo → Class II)
```

---

## 2. 510(k) — Premarket Notification

### 실질적 동등성(Substantial Equivalence) 판단 (Section 513(i))

**Step 1**: Intended Use 동일한가?
- 예 → Step 2로
- 아니오 → Not SE (새 의도된 사용 → PMA 또는 De Novo)

**Step 2**: 기술적 특성이 다른가?
- 다르지 않음 → **SE 결정 가능**
- 다름 → Step 3으로

**Step 3**: 다른 기술적 특성이 새로운 안전성/유효성 문제를 야기하는가?
- 아니오 + 성능 데이터로 입증 → **SE 결정**
- 예 → **Not SE** → PMA 또는 De Novo

### Predicate Device 선택 기준

- **공식 방법**: FDA 510(k) 데이터베이스 (www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/)
- 가장 최신 cleared predicate 권장
- 다중 predicate 조합(split predicates) 가능 — 단, 모든 intended use를 커버해야 함
- **피해야 할 predicates**: 1976년 이전 기기(preamendment device)는 설명이 필요

### 510(k) 제출 유형

| 유형 | 적용 기준 | 특징 |
|------|---------|------|
| Traditional 510(k) | 기본 | 전통적 제출 방식 |
| Abbreviated 510(k) | FDA guidance/special control 있는 경우 | 핵심 데이터만 제출 |
| Special 510(k) | 자사 기존 cleared device 변경 | 설계 관리(Design Controls) 데이터 활용 |

---

## 3. 510(k) 제출 필수 항목 (21 CFR 807.87)

### 기본 섹션

1. **Device Description**
   - 명칭, 모델, 의도된 사용, 적응증
   - 동작 원리, 구성 요소, 재질
   - 사용 환경 및 사용자

2. **Indications for Use Statement**
   - 정확한 의도된 사용 기재
   - 적용 환자 집단, 적용 부위, 사용 조건

3. **Substantial Equivalence Discussion**
   - Predicate device 선택 근거
   - Intended use 비교
   - Technological characteristics 비교표
   - 차이점이 있는 경우 성능 데이터

4. **Performance Testing**
   - 벤치 시험 (Bench testing): 전기안전, EMC, 기계적 강도 등
   - 동물 실험 (Preclinical): 생체적합성 등
   - 임상 데이터 (Clinical): Class II 일부, Class III에서 주로

5. **Labeling**
   - 표시(Label): 기기 명칭, UDI, 제조업자 정보, 사용 기간
   - IFU: 의도된 사용, 적응증·금기사항, 사용 방법, 경고·주의사항

6. **510(k) Summary or Statement** (21 CFR 807.92 또는 807.93)

### 추가 고려 요소

- **Biocompatibility (생체적합성)**: ISO 10993 기반 평가 (피부 접촉 이상 기기)
- **Sterility**: 멸균 방법 및 검증 데이터
- **Software**: 소프트웨어 포함 기기 → FDA Guidance 적용 (아래 참조)
- **Cybersecurity**: 네트워크 연결 기기 → 2023 Cybersecurity Guidance

---

## 4. SaMD — Software as a Medical Device

### FDA SaMD 적용 범위 (FDARA Section 520(o))

**의료기기 소프트웨어 해당 (규제 대상):**
- 질병 진단·예방·치료·경감·관리 목적
- 구조·기능에 영향을 미치는 목적
- AI/ML 기반 진단 알고리즘

**의료기기 소프트웨어 비해당 (비규제):**
- 행정·금융·청구 기능
- 일반 건강증진 기능 (체중 관리, 수면 추적 등)
- 의사의 임상 판단을 대체하지 않는 임상 의사결정 지원 (CDS)
- CLIA-exempt 검사

### FDA SaMD Risk Categorization (IMDRF 프레임워크 채택)

**의료 상황의 중요성:**
| 레벨 | 설명 |
|------|------|
| Critical | 즉각적 조치 없으면 생명·건강에 심각한 결과 |
| Serious | 즉각적 조치 없어도 중장기적으로 건강에 심각한 결과 |
| Non-serious | 특별한 결과 없음 |

**SaMD의 의료 상황 기여 유형:**
| 유형 | 설명 |
|------|------|
| Treat or diagnose | 직접적 치료·진단 결정 |
| Drive clinical management | 임상 결정에 드라이브 |
| Inform clinical management | 임상 정보 제공 |

**위험 등급:**
| 기여 유형 | Critical | Serious | Non-serious |
|---------|---------|---------|------------|
| Treat/Diagnose | IV | III | II |
| Drive | III | II | I |
| Inform | II | I | I |

### AI/ML 기반 SaMD 특별 사항

- **Pre-determined Change Control Plan (PCCP)**: 지속 학습 AI의 변경 사전 계획
- **Predetermined Performance Criteria**: 알고리즘 성능 기준 사전 정의
- **Real-World Performance Monitoring**: 배포 후 실제 성능 모니터링 계획
- 2021 AI/ML SaMD Action Plan 참조

---

## 5. QSR → QMSR 전환 (2024-02-02 시행)

### 변경 사항

| 항목 | 기존 QSR (21 CFR 820) | 신규 QMSR |
|------|---------------------|---------|
| 기반 | 독자적 FDA 요건 | ISO 13485:2016 harmonized |
| 시행일 | 1996년 | 2024-02-02 |
| 설계 관리 | 820.30 (Design Controls) | ISO 13485 Section 7.3 동등 |
| CAPA | 820.100 | ISO 13485 Section 8.5.2/8.5.3 |
| 기록 요건 | FDA 고유 형식 | ISO 13485 형식 허용 |

### 전환 기간

- 기존 QSR 준수: 2024-02-02 이후에도 QMSR 이행 전까지 허용
- QMSR 완전 전환 권고: 2026년까지

### 핵심 QMSR 섹션

- **4. Quality Management System**: QMS 범위, 절차, 문서 관리
- **6. Resource Management**: 인적자원, 인프라, 작업 환경
- **7. Product Realization**: 설계 개발, 구매, 생산, 서비스
  - 7.3: Design and Development (Design Controls)
  - 7.5: Production and Service Provision
- **8. Measurement, Analysis, Improvement**: 모니터링, CAPA, 내부 감사

---

## 6. 주요 FDA Guidance Documents

| 제목 | 년도 | 내용 |
|------|------|------|
| Software as a Medical Device: Clinical Evaluation | 2017 | SaMD 임상평가 |
| Deciding When to Submit a 510(k) for a Change | 2017 | 변경 시 510(k) 재신청 기준 |
| Cybersecurity in Medical Devices | 2023 | 네트워크 보안 요건 |
| AI/ML-Based SaMD | 2019 | AI 기반 SaMD 규제 |
| Content of Premarket Submissions | 2023 | 소프트웨어 기기 510(k) 내용 |
| Use of International Standard ISO 10993-1 | 2020 | 생체적합성 평가 |

---

## 7. De Novo 절차

기존 cleared predicate가 없는 신규 저·중위험 기기를 위한 경로:

1. 510(k) 제출 → FDA: Not SE 판정 (또는 De Novo 직접 요청)
2. De Novo request 제출 (30일 내 FDA 검토)
3. FDA가 Risk-based controls 결정 → Class I 또는 II로 분류
4. 이후 동일 유형 기기의 predicate 역할 수행

**소요 기간**: 약 12-18개월 (FDA 내부 목표 기준)

---

## 8. 510(k) 심사 기준 (FDA의 주요 지적 사항)

1. **Intended Use 불명확**: 적응증과 금기사항 경계가 불분명
2. **Predicate 선택 근거 부족**: 왜 이 predicate가 적합한지 설명 미흡
3. **성능 시험 미흡**: 주장(claim)에 대한 데이터 부재
4. **Labeling 불일치**: IFU와 제출 내용 간 적응증 불일치
5. **소프트웨어 문서 불충분**: IEC 62304 레벨 및 SOUP 관리 미흡
6. **사이버보안 계획 누락**: 네트워크 연결 기기에서 보안 계획 없음
