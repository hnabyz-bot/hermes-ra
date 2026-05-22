#!/usr/bin/env python3
import os, sys, json, re, urllib.request

def analyze(from_addr, subject, body, attachments=''):
    attach_section = ('\n\n[첨부파일]\n' + attachments) if attachments else ''
    prompt = "당신은 RA(인허가) 전문가입니다. 아래 공문을 분석하여 JSON만 출력하세요. 다른 텍스트 없이 JSON만.\n\n[발신자] " + from_addr + "\n[제목] " + subject + "\n[본문]\n" + body[:3000] + attach_section + '\n\n{"summary":"핵심요약 2-3줄","org":"발신기관명","deadline":"기한(없으면 null)","action":"RA담당자 필요조치","priority":"high/medium/low","attachments_note":"첨부파일 주요사항(없으면 null)"}'
    
    req_data = json.dumps({'model': 'gemma3:4b', 'prompt': prompt, 'stream': False, 'options': {'temperature': 0.1, 'num_predict': 400}}).encode('utf-8')
    try:
        ollama_url = os.environ.get("OLLAMA_URL", "http://192.168.100.1:11434")
        req = urllib.request.Request(f'{ollama_url}/api/generate', data=req_data, headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            raw = result.get('response', '').replace('```json', '').replace('```', '').strip()
            raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
            try:
                return json.loads(raw)
            except:
                m = re.search(r'\{[^{}]+\}', raw, re.DOTALL)
                if m:
                    try: return json.loads(m.group())
                    except: pass
                return {'summary': 'JSON파싱실패: ' + raw[:100], 'org': '', 'deadline': None, 'action': '', 'priority': 'medium', 'attachments_note': None}
    except Exception as e:
        return {'summary': '분석오류: ' + str(e), 'org': '', 'deadline': None, 'action': '', 'priority': 'medium', 'attachments_note': None}

if __name__ == '__main__':
    args = sys.argv[1:]
    if len(args) < 3:
        print(json.dumps({'error': 'args required: from subject body [attachments]'}))
        sys.exit(1)
    print(json.dumps(analyze(args[0], args[1], args[2], args[3] if len(args) > 3 else ''), ensure_ascii=False))
