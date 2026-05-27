# [운영 이력] GX10 GPU 가속 복구 및 Hermes 엔진 정상화

**날짜**: 2026-05-27  
**영향 범위**: Hermes TUI 완전 불통 → 정상화  
**처리 시간**: 약 2시간 (진단 + GX10 재부팅 + 검증 포함)

---

## 증상

Hermes TUI(`hermes` 명령어) 실행 시 모든 질의에서 다음 오류 반복:

```
⚠️  API call failed (attempt 1/3): TypeError
   🔌 Provider: openai-codex  Model: gpt-5.3-codex
   🌐 Endpoint: https://chatgpt.com/backend-api/codex
   📝 Error: 'NoneType' object is not iterable
❌ Non-retryable client error (HTTP None). Aborting.
```

---

## 원인 분석

### 1차 원인: config.yaml 잘못된 모델 설정

`~/.hermes/config.yaml`의 model 섹션이 동작하지 않는 비공식 엔드포인트를 가리키고 있었음:

```yaml
# 잘못된 설정 (수정 전)
model:
  default: gpt-5.3-codex
  provider: openai-codex
  base_url: https://chatgpt.com/backend-api/codex
```

`chatgpt.com/backend-api/codex`는 ChatGPT 웹 인터페이스의 내부 API로, 공식 지원 엔드포인트가 아님. 언제부터 이 설정이 들어갔는지는 불명확 (Hermes 자동 업데이트 또는 이전 실험적 설정 추정).

### 2차 원인: GX10 구 커널 — NVIDIA 드라이버 모듈 미탑재

GX10을 `qwen3:30b` + Ollama로 전환하니 응답은 됐지만 속도가 **5분 39초/20토큰** (CPU 전용 추론):

- 실행 중인 커널: `6.17.0-1014-nvidia`
- 해당 커널에 NVIDIA 드라이버 모듈(`nvidia.ko`) 없음
- `linux-modules-nvidia-580-open` 패키지가 `6.17.0-1018-nvidia` 커널 대상으로만 설치됨

```bash
# 확인 명령
uname -r                           # → 6.17.0-1014-nvidia (구 커널)
nvidia-smi                         # → NVIDIA-SMI has failed...
modprobe --dry-run nvidia          # → Module nvidia not found
dpkg -l | grep linux-modules-nvidia-580-open
# → 6.17.0-1018-nvidia 버전만 설치됨
```

### 3차 원인: 컨텍스트 윈도우 부족

Ollama 기본 num_ctx(4,096)로는 RA 스킬(25KB, 560줄) 로딩 불가. 32,768으로 수정해도 Hermes가 최소 64,000 토큰 요구.

---

## 해결 과정

### Step 1: config.yaml 모델 설정 수정

```yaml
# ~/.hermes/config.yaml — model 섹션 수정
model:
  default: qwen3:30b
  provider: custom          # Hermes 내 ollama/local 프로바이더
  base_url: http://192.168.100.1:11434/v1   # GX10 Ollama
  ollama_num_ctx: 65536     # RA 스킬 전체 + 응답 수용
```

`custom` 프로바이더는 `~/.hermes/hermes-agent/plugins/model-providers/custom/__init__.py`에 정의된 Ollama 로컬/커스텀 엔드포인트용 프로파일.

### Step 2: GX10 커널 업그레이드 재부팅

```bash
# 설치된 커널 및 모듈 확인
ssh gx10 "ls /boot/vmlinuz* | sort"
# → 6.17.0-1014-nvidia, 6.17.0-1018-nvidia 모두 존재

ssh gx10 "dpkg -l | grep linux-modules-nvidia-580-open"
# → 1018 버전만 설치 확인

# 재부팅 (1018 커널로 자동 전환됨 — GRUB 기본값 최신 커널)
ssh gx10 "sudo reboot"
```

재부팅 완료 후 확인:

```bash
ssh gx10 "uname -r"         # → 6.17.0-1018-nvidia
ssh gx10 "nvidia-smi --query-gpu=name --format=csv,noheader"
# → NVIDIA GB10
```

### Step 3: 컨텍스트 윈도우 32K → 65536 조정

Hermes가 tool use 활성화 시 최소 64,000 토큰 요구:

```yaml
model:
  ollama_num_ctx: 65536  # 32768에서 변경
```

---

## 복구 후 상태

| 항목 | 수치 |
|------|------|
| 응답 속도 (CPU) | 0.06 tokens/sec (5분 39초/20토큰) |
| 응답 속도 (GPU) | ~24 tokens/sec (2초/50토큰) |
| GPU | NVIDIA GB10 (Grace Blackwell Superchip) |
| GX10 VRAM (qwen3:30b) | 68.4GB |
| GX10 VRAM (embedding) | 14.7GB |
| 전체 메모리 (통합) | ~83GB / 128GB |
| RA 스킬 질의 | 정상 응답 (MFDS/CE MDR/FDA 분류 기준 등) |

---

## 재발 방지

1. **config.yaml 버전 관리**: `~/.hermes/config.yaml`의 model 섹션을 이 저장소 `docs/ops/` 에 참조 기록 유지
2. **GX10 커널 업데이트 정책**: 커널 업데이트 후 `nvidia-smi` 동작 확인 필수 (모듈 미탑재 위험)
3. **체크리스트 추가**: `PROJECT_GUIDE.md` 4번 항목에 `hermes -z` + GPU 사용률 확인 추가 권장

---

## 정상 config.yaml 참조 (model 섹션)

```yaml
model:
  default: qwen3:30b
  provider: custom
  base_url: http://192.168.100.1:11434/v1
  ollama_num_ctx: 65536
```

> Hermes v0.14.0 + GX10 NVIDIA GB10 기준 검증 완료 (2026-05-27)
