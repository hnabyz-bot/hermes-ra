# CE MDR 2017/745 Annex I (GSPR) + Annex XIV (Clinical Evaluation) 요약

> 기준: Regulation (EU) 2017/745 — Medical Devices Regulation (MDR)
> 전환 완료일: 2024-05-26 (기존 AIMDD/MDD 완전 폐지)
> MDCG 가이던스 및 EUDAMED 연동 포함

---

## 1. MDR 구조 개요

| 파트 | 내용 |
|------|------|
| Articles 1-100 | 규정 조항 (범위, 의무, 절차, 규제기관) |
| Annex I | 일반 안전·성능 요건 (GSPR) |
| Annex II | 기술문서 (Technical Documentation) |
| Annex III | 기술문서 (시판후 안전성 관련) |
| Annex IV | EU 적합성 선언 |
| Annex V-VII | 각종 시험 인증서 유형 |
| Annex VIII | 기기 분류 규칙 |
| Annex IX | QMS + Technical Documentation 심사 |
| Annex X | EU 형식검사 |
| Annex XI | 제조 품질 보증 |
| Annex XIV | 임상평가 + PMCF |
| Annex XV | 임상조사 |
| Annex XVI | 비의료 목적 기기 (미용 등) |

---

## 2. Annex I — GSPR (General Safety and Performance Requirements)

### Chapter I — General Requirements

**GSPR 1**: 안전하고 의도된 성능을 발휘해야 하며, 위험-이익 균형이 허용 가능해야 함

**GSPR 2**: 설계·제조는 최신 기술 수준(SOTA) 반영

**GSPR 3**: 제조업자가 제공하는 정보를 준수하는 조건에서 안전·성능 유지

**GSPR 4**: 이익 대비 잔류 위험이 허용 가능한 수준

**GSPR 5**: 안전 설계 원칙 우선순위:
1. 위험 원인 제거 또는 최소화 (설계·제조로)
2. 제거 불가 위험은 적절한 보호 조치
3. 남은 위험에 대한 정보 제공

**GSPR 6**: 알려진 부작용·금기사항 정보 제공

**GSPR 7**: 임상평가로 GSPR 적합성 증명

**GSPR 8**: 기기 간 통신 기능이 있는 경우 인터페이스 안전성 고려

### Chapter II — Design and Manufacture Requirements (선택 항목)

**GSPR 10**: 화학적·물리적·생물학적 특성
- 10.4: 부형제·시약 선택 기준
- 10.6: 나노물질 특별 고려

**GSPR 11**: 감염 및 오염 예방

**GSPR 12**: 물질 및 환경 상호작용

**GSPR 13**: 의도치 않은 노출로부터 보호 (방사선 포함)

**GSPR 14**: 전기적 안전 및 전자기적 적합성
- IEC 60601-1 (전기·기계 안전)
- IEC 60601-1-2 (EMC)
- IEC 60601-1-6 (사용편의성)

**GSPR 15**: 기계적 위험 보호

**GSPR 16**: 미생물 위험 보호

**GSPR 17**: 소프트웨어가 내장된 기기 및 독립형 소프트웨어
```
"Software which drives a device or influences the use of a device shall be designed 
and manufactured in accordance with the state of the art taking into account the 
principles of development life cycle, risk management, including information security, 
verification and validation."
```
- IEC 62304: 소프트웨어 생명주기 (Medical device software)
- IEC 82304: 독립형 소프트웨어 의료기기 안전성
- MDCG 2019-16: 의료기기 소프트웨어 적용 가이던스

**GSPR 18**: 능동 기기의 에너지 조건

**GSPR 19**: 광 기기 안전

**GSPR 20**: 이온화 방사선 기기

**GSPR 21**: 체외진단의료기기 특별 요건

**GSPR 22**: 능동형 이식 기기

### Chapter III — Information Supplied with the Device

**GSPR 23**: 라벨 및 사용설명서(IFU)
- 23.4(u): 사용설명서 상세 요건 (40개 이상 항목)
- 주요: 의도된 사용, 금기사항, 부작용, 잔류 위험, 보관 조건

---

## 3. 기기 분류 규칙 (Annex VIII)

### 분류 규칙 요약

| 규칙 | 대상 | 분류 결과 |
|------|------|---------|
| Rule 1 | 비능동, 비침습 기기 | 일반 Class I |
| Rule 11 | 소프트웨어 의료기기 진단/치료 | Class IIa–III |
| Rule 12 | 기타 모든 능동 기기 | Class IIa 이상 |
| Rule 16 | 직접 인체 접촉 특수 재료 | 상황별 |

**Rule 11 — 소프트웨어 분류 핵심:**
- 진단·치료 결정에 직접적인 영향 → **Class IIa** 이상
- 생명에 위험한 상황 감지 → **Class III**
- 혈당 모니터링 소프트웨어 → **Class IIb**
- 단순 정보 집계 (개인 건강 기록) → **Class I**

---

## 4. Annex XIV — Clinical Evaluation

### Part A: Clinical Evaluation

**임상평가 목적 (Article 61)**:
의도된 사용에 따른 안전·성능 기준을 충족함을 임상 데이터로 증명

**임상평가 방법 (MEDDEV 2.7/1 Rev. 4 기반):**
1. 임상평가 계획 수립 (Clinical Evaluation Plan, CEP)
2. 임상 데이터 식별·수집
   - 자체 임상조사 데이터
   - 동등 기기(Equivalent Device) 문헌 데이터
   - 시판 후 감시 데이터
3. 임상 데이터 평가
4. 임상평가보고서(CER) 작성

**동등 기기(Equivalent Device) 요건 (Article 61(4)):**
세 가지 특성이 모두 동등해야 함:
- 기술적 특성 (Technical characteristics)
- 생물학적 특성 (Biological characteristics)
- 임상적 특성 (Clinical characteristics)

**클래스별 임상 요건:**
| 분류 | 임상 요건 |
|------|---------|
| Class I | 임상 데이터 일부 요구 (단, 동등 기기 데이터로 충분한 경우 많음) |
| Class IIa | CER 필수, 동등 기기 활용 가능 |
| Class IIb | CER + 임상조사 또는 강력한 동등 기기 근거 |
| Class III | CER + 임상조사 (원칙적) + 전문가 패널 의견 |

### Part B: Post-Market Clinical Follow-up (PMCF)

**PMCF 의무 대상:**
- Class III 기기
- Class IIb 이식형 기기
- 임상평가에서 불확실성이 남은 기기

**PMCF 방법:**
- 연구자 주도 연구(IIS)
- PMCF 임상조사
- 레지스트리 데이터
- EUDAMED 기기 감시 데이터

---

## 5. Technical Documentation (Annex II)

필수 포함 항목:

1. **기기 설명 및 사양**
   - 의도된 사용, 적응증, 금기사항
   - 기기 명칭, UDI-DI, HS code
   - 기기 세대 목록

2. **설계·제조 정보**
   - 원자재, 제조 공정
   - 멸균/청결 처리 방법 (해당 시)

3. **GSPR 적합성 증명**
   - 적용 GSPR 목록
   - 각 GSPR별 증거 (시험, 표준, 분석)

4. **이익-위험 분석 및 리스크 관리**
   - ISO 14971 기반 리스크 관리 파일
   - 위험 원인 분석 (FMEA 또는 동등)
   - 잔류 위험 수용 가능성 평가

5. **제품 검증·유효성 확인**
   - V&V 프로토콜 및 결과 보고서
   - 성능 시험 데이터

6. **임상평가보고서 (CER)**

7. **시판 후 감시 계획 (PMSP)**

---

## 6. Notified Body 관여

| 분류 | 적용 Annex | NB 역할 |
|------|----------|--------|
| Class I (standard) | Annex IV | NB 불필요, 자체 선언 |
| Class I (sterile/measuring) | Annex IV + IX or XI | NB 심사 일부 |
| Class IIa | Annex IX or X+XI | QMS 감사 또는 형식검사 |
| Class IIb | Annex IX or X+XI | 위와 동일 (더 엄격) |
| Class III | Annex IX + Annex IX(5) | 설계심사 + QMS 전체 |

---

## 7. 주요 MDCG 가이던스 목록

| 번호 | 제목 |
|------|------|
| MDCG 2019-11 | 기기 분류 Q&A |
| MDCG 2019-16 | 소프트웨어 의료기기 분류·적용 |
| MDCG 2020-1 | 임상평가 — 동등 기기 관련 |
| MDCG 2020-5 | UDI 적용 가이던스 |
| MDCG 2021-6 | 사이버보안 |
| MDCG 2022-2 | 시판 후 임상 추적조사 (PMCF) |
| MDCG 2023-3 | 기술문서 요건 해설 |

---

## 8. EUDAMED 의무

2024년 이후 단계적 의무화:
- 기기 등록(UDI)
- 제조업자·인증기관 등록
- 적합성 인증서 등록
- 임상조사 등록
- 시판 후 감시 결과 게시
