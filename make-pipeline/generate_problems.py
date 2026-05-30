import json
import os
import sys

# stock_blog .env에서 API 키 로드
env_path = r"C:\Users\USER\stock_blog\.env"
with open(env_path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line.startswith("ANTHROPIC_API_KEY"):
            key = line.split("=", 1)[1].strip().strip('"')
            os.environ["ANTHROPIC_API_KEY"] = key
            break

import anthropic

client = anthropic.Anthropic()

# intro.json 로드
intro_path = os.path.join(os.path.dirname(__file__), "prime_factorization_intro.json")
with open(intro_path, encoding="utf-8") as f:
    intro = json.load(f)

PROMPT = f"""
당신은 math-explorer 프로젝트의 수학 문제 설계자입니다.

## 프로젝트 철학
- 핀란드식 동기(발견) + 칸아카데미 원리 설명 + 한국식 구조적 깊이를 결합
- 맥락은 장식이 아니라 수학적 본질과 연결되어야 함
- 학생이 탐색하다 스스로 막히는 구조로 설계

## 단계별 설계 (intro_stages)
학생들이 아래 3단계를 거쳐 소인수분해 개념에 도달했습니다.

{json.dumps(intro['intro_stages'], ensure_ascii=False, indent=2)}

## 품질 원칙 (quality_principles)
{json.dumps(intro['quality_principles']['principles'], ensure_ascii=False, indent=2)}

## 매트릭스 구조
{json.dumps(intro['matrix_structure'], ensure_ascii=False, indent=2)}

## 지시사항
위 단계별 설계를 바탕으로 소인수분해 9개 문제를 생성하십시오.

**매트릭스 위치:**
- ①②③ (개념 확인): 한국 하 × 핀란드 하/중/상
- ④⑤⑥ (실력 도전): 한국 중 × 핀란드 하/중/상
- ⑦⑧⑨ (깊이 탐구): 한국 상 × 핀란드 하/중/상

**요구사항:**
1. 각 문제는 intro_stages에서 학생이 발견한 개념을 기반으로 설계
2. 9개는 독립적이 아닌 학습 서사로 연결 (①을 이해해야 ②에서 의미있게 막힘)
3. 각 문제 생성 후 6개 품질 원칙으로 자기검토 수행
4. 하나라도 실패하면 해당 문제를 수정하고 재검토

**출력 형식 (JSON 배열):**
```json
[
  {{
    "problem_id": "m1p-001",
    "matrix_position": "①",
    "korean_level": "하",
    "finland_level": "하",
    "title": "문제 제목",
    "context": "문제 배경/상황 (맥락이 수학과 직접 연결되어야 함)",
    "question": "핵심 질문",
    "answer": "정답",
    "answer_explanation": "정답 설명",
    "hints": [
      {{"level": 1, "text": "가장 가벼운 힌트"}},
      {{"level": 2, "text": "중간 힌트"}},
      {{"level": 3, "text": "거의 답에 가까운 힌트"}}
    ],
    "misconception": "이 문제를 틀리는 학생의 오개념",
    "followup_questions": [
      "강사 후속 발문 1",
      "강사 후속 발문 2",
      "강사 후속 발문 3"
    ],
    "next_question_bridge": "정답을 맞힌 학생에게 던질 다음 질문",
    "quality_check": {{
      "principle_1": {{"pass": true, "note": "계산과 사고 분리 여부"}},
      "principle_2": {{"pass": true, "note": "오개념 명확성"}},
      "principle_3": {{"pass": true, "note": "맥락의 필수성"}},
      "principle_4": {{"pass": true, "note": "강사 확장 가능성"}},
      "principle_5": {{"pass": true, "note": "정답 이후 학습 연결"}},
      "principle_6": {{"pass": true, "note": "매트릭스 연결성"}}
    }},
    "connects_to_stage": 1,
    "narrative_link": "이전/다음 문제와의 학습 서사 연결 설명"
  }}
]
```

JSON만 출력하십시오. 설명이나 마크다운 없이 순수 JSON 배열만.
"""

print("Claude API 호출 중...")
response = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=16000,
    messages=[{"role": "user", "content": PROMPT}]
)

raw = response.content[0].text.strip()

# 디버그용 raw 저장
debug_path = os.path.join(os.path.dirname(__file__), "_raw_response.txt")
with open(debug_path, "w", encoding="utf-8") as f:
    f.write(raw)
print(f"stop_reason: {response.stop_reason}, 길이: {len(raw)}")

# JSON 파싱
if "```" in raw:
    parts = raw.split("```")
    for part in parts:
        part = part.strip()
        if part.startswith("json"):
            part = part[4:].strip()
        if part.startswith("["):
            raw = part
            break
raw = raw.strip()

problems = json.loads(raw)

# 저장
output_path = os.path.join(os.path.dirname(__file__), "prime_factorization_problems.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(problems, f, ensure_ascii=False, indent=2)

print(f"완료: {len(problems)}개 문제 저장 → {output_path}")
for p in problems:
    qc = p.get("quality_check", {})
    fails = [k for k, v in qc.items() if not v.get("pass", True)]
    status = "✓" if not fails else f"✗ {fails}"
    print(f"  {p['matrix_position']} {p['problem_id']} [{p['korean_level']}×{p['finland_level']}] {status}")
