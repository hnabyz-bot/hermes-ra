#!/usr/bin/env python3
"""
weekly_review.py — Hermes RA 주간 품질 리뷰 & SKILL.md 개선 제안 생성기

사용법:
  python3 ops/scripts/weekly_review.py [--days N] [--output report.md]

동작:
  1. hermes-api-server 로그에서 최근 N일 wp_comment JSON 응답 수집
  2. OpenProject API가 설정되어 있으면 WP 댓글에서 추가 수집 (선택)
  3. confidence 분포, 실패 패턴, WP 미매칭 케이스 분석
  4. SKILL.md 개선 제안을 마크다운 리포트로 출력

Hermes 성장 전략:
  이 스크립트의 리포트를 읽고 SKILL.md를 개선하는 것이 주간 성장 루틴의 핵심이다.
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.parse
from collections import Counter, defaultdict
from datetime import datetime, timedelta

DAYS = int(os.environ.get("REVIEW_DAYS", "7"))
OP_BASE_URL = os.environ.get("OPENPROJECT_BASE_URL", "")
OP_API_KEY = os.environ.get("OP_API_KEY", os.environ.get("OPENPROJECT_API_KEY", ""))
RESPONSE_LOG = os.environ.get("RESPONSE_LOG", "/var/log/hermes-responses.jsonl")
OUTPUT_FILE = None


def parse_args():
    global DAYS, OUTPUT_FILE
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--days" and i + 1 < len(args):
            DAYS = int(args[i + 1])
            i += 2
        elif args[i] == "--output" and i + 1 < len(args):
            OUTPUT_FILE = args[i + 1]
            i += 2
        else:
            i += 1


def collect_from_logs() -> list[dict]:
    """JSONL 응답 로그에서 wp_comment 수집 (hermes-api-server.py가 기록)."""
    since = datetime.now() - timedelta(days=DAYS)
    records = []

    if not os.path.exists(RESPONSE_LOG):
        return records

    try:
        with open(RESPONSE_LOG) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts_str = entry.get("ts", "")
                    if ts_str:
                        ts = datetime.fromisoformat(ts_str)
                        if ts < since:
                            continue
                    wpc = entry.get("wp_comment", {})
                    if wpc:
                        records.append(wpc)
                except (json.JSONDecodeError, ValueError):
                    pass
    except Exception as e:
        print(f"[경고] 로그 수집 실패: {e}", file=sys.stderr)

    return records


def collect_from_op() -> list[dict]:
    """OpenProject API에서 Hermes가 작성한 WP 댓글 수집 (선택)."""
    if not OP_BASE_URL or not OP_API_KEY:
        return []

    import base64
    token = base64.b64encode(f"apikey:{OP_API_KEY}".encode()).decode()
    headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

    records = []
    since = (datetime.now() - timedelta(days=DAYS)).isoformat()
    url = f"{OP_BASE_URL}/api/v3/activities?filter=[{{\"updatedAt\":{{\"operator\":\">=\",\"values\":[\"{since}\"]}}}}]&pageSize=100"

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            activities = data.get("_embedded", {}).get("elements", [])
            for act in activities:
                comment = act.get("comment", {}).get("raw", "")
                if '"wp_comment"' in comment:
                    try:
                        parsed = json.loads(comment)
                        wpc = parsed.get("wp_comment", {})
                        if wpc:
                            records.append(wpc)
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        print(f"[정보] OP API 수집 건너뜀: {e}", file=sys.stderr)

    return records


def analyze(records: list[dict]) -> dict:
    """수집된 wp_comment 레코드 분석."""
    if not records:
        return {}

    confidence_counts = Counter(r.get("confidence", "unknown") for r in records)
    email_type_counts = Counter(r.get("email_type", "unknown") for r in records)
    unmatched = [r for r in records if r.get("matched_wp_id") is None]
    low_conf = [r for r in records if r.get("confidence") == "low"]
    flagged = [r for r in records if r.get("flags")]

    # 플래그 집계
    all_flags: list[str] = []
    for r in records:
        all_flags.extend(r.get("flags") or [])
    flag_counts = Counter(all_flags)

    # 시장 분석 null 비율
    market_nulls: dict[str, int] = defaultdict(int)
    for r in records:
        ma = r.get("market_analysis", {}) or {}
        for market in ("mfds", "ce_mdr", "fda"):
            if ma.get(market) is None:
                market_nulls[market] += 1

    return {
        "total": len(records),
        "confidence": dict(confidence_counts),
        "email_type": dict(email_type_counts),
        "unmatched_count": len(unmatched),
        "unmatched_samples": unmatched[:5],
        "low_conf_count": len(low_conf),
        "low_conf_samples": low_conf[:5],
        "flagged_count": len(flagged),
        "flag_counts": dict(flag_counts),
        "market_nulls": dict(market_nulls),
    }


def generate_skill_proposals(analysis: dict) -> list[str]:
    """분석 결과를 바탕으로 SKILL.md 개선 제안 생성."""
    proposals = []
    total = analysis.get("total", 0)
    if total == 0:
        return ["분석할 케이스가 없습니다."]

    conf = analysis.get("confidence", {})
    low_pct = conf.get("low", 0) / total * 100 if total else 0
    med_pct = conf.get("medium", 0) / total * 100 if total else 0

    if low_pct > 20:
        proposals.append(
            f"**[우선순위 높음] 출처 없는 응답 {low_pct:.0f}%** — "
            "NAS RAG가 관련 문서를 찾지 못하거나 references/ 내용이 부족합니다. "
            "조치: 해당 케이스 주제의 references/ 문서를 강화하세요."
        )

    if low_pct + med_pct > 50:
        proposals.append(
            f"**[우선순위 높음] 중간 이하 신뢰도 {low_pct + med_pct:.0f}%** — "
            "SKILL.md의 규정 근거가 충분하지 않습니다. "
            "조치: 반복 등장하는 주제에 대한 법령 조항을 SKILL.md에 명시하세요."
        )

    unmatched_pct = analysis.get("unmatched_count", 0) / total * 100
    if unmatched_pct > 40:
        proposals.append(
            f"**[우선순위 중간] WP 미매칭 {unmatched_pct:.0f}%** — "
            "기존 WP와 이메일 매칭이 자주 실패합니다. "
            "조치: SKILL.md의 'Step 3: Existing WP Matching' 섹션에 더 구체적인 매칭 기준을 추가하세요."
        )

    flag_counts = analysis.get("flag_counts", {})
    if flag_counts.get("출처없음", 0) > 3:
        proposals.append(
            f"**[우선순위 중간] '출처없음' 플래그 {flag_counts['출처없음']}건** — "
            "RAG가 관련 문서를 찾지 못하는 케이스가 반복됩니다. "
            "조치: 해당 케이스 유형의 NAS 문서가 인덱싱되어 있는지 확인하고, "
            "RAG 검색 쿼리 전략(SKILL.md 'Query angles' 섹션)을 개선하세요."
        )

    if flag_counts.get("법령확인필요", 0) > 2:
        proposals.append(
            f"**[우선순위 중간] '법령확인필요' 플래그 {flag_counts['법령확인필요']}건** — "
            "Hermes가 규정 근거를 확신하지 못하는 영역이 있습니다. "
            "조치: 해당 주제의 MFDS/CE MDR/FDA 법령 조항을 references/에 추가하세요."
        )

    market_nulls = analysis.get("market_nulls", {})
    for market, count in market_nulls.items():
        null_pct = count / total * 100
        if null_pct > 60:
            market_name = {"mfds": "MFDS(한국)", "ce_mdr": "CE MDR(EU)", "fda": "FDA(미국)"}[market]
            proposals.append(
                f"**[정보] {market_name} 분석 null {null_pct:.0f}%** — "
                f"수신 이메일 중 {market_name} 관련 내용이 적거나, "
                f"SKILL.md의 {market_name} 섹션이 충분하지 않을 수 있습니다."
            )

    if not proposals:
        proposals.append("이번 주 처리 케이스에서 구조적 개선 포인트가 발견되지 않았습니다. 품질이 양호합니다.")

    return proposals


def format_report(analysis: dict, proposals: list[str]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = analysis.get("total", 0)

    lines = [
        f"# Hermes RA 주간 품질 리뷰 — {now}",
        f"분석 기간: 최근 {DAYS}일 | 처리 케이스: {total}건",
        "",
    ]

    if total == 0:
        lines += [
            "## 분석 결과",
            "처리된 케이스가 없습니다. 파이프라인 동작 여부를 확인하세요.",
            "",
            "```bash",
            "# 확인 명령어",
            "sudo journalctl -u hermes-api-server --since='7 days ago' | grep wp_comment | wc -l",
            "sudo journalctl -u hermes-gateway -f",
            "```",
        ]
        return "\n".join(lines)

    conf = analysis.get("confidence", {})
    lines += [
        "## 1. 신뢰도 분포",
        f"- high: {conf.get('high', 0)}건 ({conf.get('high', 0)/total*100:.0f}%)",
        f"- medium: {conf.get('medium', 0)}건 ({conf.get('medium', 0)/total*100:.0f}%)",
        f"- low: {conf.get('low', 0)}건 ({conf.get('low', 0)/total*100:.0f}%)",
        "",
    ]

    et = analysis.get("email_type", {})
    lines += [
        "## 2. 이메일 유형 분류",
        f"- 완료통보: {et.get('완료통보', 0)}건",
        f"- 액션필요: {et.get('액션필요', 0)}건",
        f"- 정보수신: {et.get('정보수신', 0)}건",
        "",
    ]

    fc = analysis.get("flag_counts", {})
    if fc:
        lines.append("## 3. 플래그 현황")
        for flag, cnt in sorted(fc.items(), key=lambda x: -x[1]):
            lines.append(f"- {flag}: {cnt}건")
        lines.append("")

    lines += [
        f"## 4. WP 매칭 실패: {analysis.get('unmatched_count', 0)}건 ({analysis.get('unmatched_count', 0)/total*100:.0f}%)",
        "",
    ]

    if analysis.get("low_conf_samples"):
        lines.append("## 5. 저신뢰도 케이스 샘플")
        for i, r in enumerate(analysis["low_conf_samples"], 1):
            lines.append(f"**케이스 {i}**: {r.get('wp_title', '제목 없음')}")
            lines.append(f"  - 이메일 유형: {r.get('email_type', '?')} | 기관: {r.get('org', '?')}")
            rec = r.get('recommendation', '')
            if rec:
                lines.append(f"  - 권고: {rec[:100]}...")
            lines.append("")

    lines += [
        "## 6. SKILL.md 개선 제안",
        "",
    ]
    for i, proposal in enumerate(proposals, 1):
        lines.append(f"{i}. {proposal}")
        lines.append("")

    lines += [
        "---",
        "",
        "## 개선 작업 방법",
        "",
        "```bash",
        "# SKILL.md 직접 수정",
        "vim /opt/hermes-ra/skills/ra-expert/SKILL.md",
        "",
        "# 또는 저장소에서 수정 후 배포",
        "# vim skills/ra-expert/SKILL.md",
        "# sudo cp skills/ra-expert/SKILL.md /opt/hermes-ra/skills/ra-expert/SKILL.md",
        "",
        "# references/ 문서 보강",
        "# vim skills/ra-expert/references/mfds_sw_guidelines.md",
        "```",
        "",
        "> 이 리포트를 기반으로 SKILL.md를 개선하면 다음 주 Hermes의 응답 품질이 향상됩니다.",
    ]

    return "\n".join(lines)


def main():
    parse_args()
    print(f"[weekly_review] 최근 {DAYS}일 케이스 수집 중...", file=sys.stderr)

    records = collect_from_logs()
    op_records = collect_from_op()

    seen = set()
    all_records = []
    for r in records + op_records:
        key = r.get("wp_title", "") + str(r.get("confidence", ""))
        if key not in seen:
            seen.add(key)
            all_records.append(r)

    print(f"[weekly_review] 총 {len(all_records)}건 수집 (로그: {len(records)}, OP: {len(op_records)})", file=sys.stderr)

    analysis = analyze(all_records)
    proposals = generate_skill_proposals(analysis)
    report = format_report(analysis, proposals)

    if OUTPUT_FILE:
        with open(OUTPUT_FILE, "w") as f:
            f.write(report)
        print(f"[weekly_review] 리포트 저장: {OUTPUT_FILE}", file=sys.stderr)
    else:
        print(report)


if __name__ == "__main__":
    main()
