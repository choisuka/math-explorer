"""
Make.com 파이프라인 서버
흐름: Make.com (Sheets Watch) → POST /webhook → Claude API → GitHub 커밋

실행: python make-pipeline/pipeline_server.py
외부 노출: ngrok http 5001  (Make.com HTTP 모듈에서 해당 URL로 호출)

Sheets 컬럼 예시:
  단원명 | 매트릭스위치 | 한국레벨 | 핀란드레벨
  소인수분해 | ① | 하 | 중
"""

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

import requests

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

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

WEBHOOK_URL = "https://hook.eu1.make.com/6gppvki7mp0my1tbpvktcq7evkjh2qvc"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = 5001

MATRIX_TO_NUM = {
    "①": "001", "②": "002", "③": "003",
    "④": "004", "⑤": "005", "⑥": "006",
    "⑦": "007", "⑧": "008", "⑨": "009",
    "1": "001", "2": "002", "3": "003",
    "4": "004", "5": "005", "6": "006",
    "7": "007", "8": "008", "9": "009",
}

UNIT_CONFIG = {
    "소인수분해": {
        "intro_file": "prime_factorization_intro.json",
        "dir": "m1-prime",
        "id_prefix": "m1p",
    },
    "가분수대분수": {
        "intro_file": "e3_frac_intro.json",
        "dir": "e3-frac",
        "id_prefix": "e3f",
    },
}

KOREAN_LABELS = {"하": "한국 하 (계산 단순)", "중": "한국 중 (계산 보통)", "상": "한국 상 (계산 복잡)"}
FINLAND_LABELS = {"하": "핀란드 하 (사고 확인)", "중": "핀란드 중 (사고 적용)", "상": "핀란드 상 (사고 발견)"}


def load_intro(unit_name):
    cfg = UNIT_CONFIG[unit_name]
    path = os.path.join(PIPELINE_DIR, cfg["intro_file"])
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_prompt(intro, matrix_pos, korean_level, finland_level):
    return f"""당신은 math-explorer 프로젝트의 수학 문제 설계자입니다.

## 프로젝트 철학
- 핀란드식 동기(발견) + 칸아카데미 원리 설명 + 한국식 구조적 깊이를 결합
- 맥락은 장식이 아니라 수학적 본질과 연결되어야 함
- 학생이 탐색하다 스스로 막히는 구조로 설계

## 단계별 설계 (intro_stages)
{json.dumps(intro['intro_stages'], ensure_ascii=False, indent=2)}

## 품질 원칙
{json.dumps(intro['quality_principles']['principles'], ensure_ascii=False, indent=2)}

## 매트릭스 구조
{json.dumps(intro['matrix_structure'], ensure_ascii=False, indent=2)}

## 지시사항
아래 조건에 맞는 소인수분해 문제 1개를 생성하십시오.

- 매트릭스 위치: {matrix_pos}
- 한국 레벨: {korean_level} ({KOREAN_LABELS.get(korean_level, korean_level)})
- 핀란드 레벨: {finland_level} ({FINLAND_LABELS.get(finland_level, finland_level)})

요구사항:
1. intro_stages에서 학생이 발견한 개념을 기반으로 설계
2. 생성 후 6개 품질 원칙으로 자기검토 수행
3. 하나라도 실패하면 수정 후 재검토

**출력 형식 (JSON 객체 1개, 마크다운 없이):**
{{
  "matrix_position": "{matrix_pos}",
  "korean_level": "{korean_level}",
  "finland_level": "{finland_level}",
  "title": "문제 제목",
  "context": "문제 배경/상황",
  "question": "핵심 질문",
  "answer": "정답",
  "answer_explanation": "정답 설명",
  "hints": [
    {{"level": 1, "text": "가장 가벼운 힌트"}},
    {{"level": 2, "text": "중간 힌트"}},
    {{"level": 3, "text": "거의 답에 가까운 힌트"}}
  ],
  "misconception": "이 문제를 틀리는 학생의 오개념",
  "followup_questions": ["강사 후속 발문 1", "강사 후속 발문 2", "강사 후속 발문 3"],
  "next_question_bridge": "정답을 맞힌 학생에게 던질 다음 질문",
  "quality_check": {{
    "principle_1": {{"pass": true, "note": ""}},
    "principle_2": {{"pass": true, "note": ""}},
    "principle_3": {{"pass": true, "note": ""}},
    "principle_4": {{"pass": true, "note": ""}},
    "principle_5": {{"pass": true, "note": ""}},
    "principle_6": {{"pass": true, "note": ""}}
  }},
  "connects_to_stage": 1,
  "narrative_link": "다른 문제와의 학습 서사 연결"
}}

JSON만 출력하십시오."""


def generate_problem(intro, matrix_pos, korean_level, finland_level):
    client = anthropic.Anthropic()
    prompt = build_prompt(intro, matrix_pos, korean_level, finland_level)

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    # 마크다운 코드블록 제거
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                raw = part
                break

    return json.loads(raw.strip())


def save_and_commit(problem, unit_name):
    cfg = UNIT_CONFIG[unit_name]
    problem_id = problem["problem_id"]

    problems_dir = os.path.join(BASE_DIR, "data", "units", cfg["dir"], "problems")
    os.makedirs(problems_dir, exist_ok=True)

    filepath = os.path.join(problems_dir, f"{problem_id}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(problem, f, ensure_ascii=False, indent=2)

    subprocess.run(["git", "-C", BASE_DIR, "add", filepath], check=True)
    subprocess.run(
        ["git", "-C", BASE_DIR, "commit", "-m",
         f"feat: generate {problem_id} {problem['matrix_position']} [{problem['korean_level']}x{problem['finland_level']}]"],
        check=True,
    )
    subprocess.run(["git", "-C", BASE_DIR, "push", "origin", "main"], check=True)

    return filepath


def notify_make(payload):
    try:
        requests.post(WEBHOOK_URL, json=payload, timeout=10)
    except Exception as e:
        print(f"[webhook notify 실패] {e}")


def process_request(data):
    unit_name    = data.get("unit_name", "소인수분해")
    matrix_pos   = data.get("matrix_position", "").strip()
    korean_level = data.get("korean_level", "").strip()
    finland_level = data.get("finland_level", "").strip()

    missing = [k for k, v in {
        "unit_name": unit_name,
        "matrix_position": matrix_pos,
        "korean_level": korean_level,
        "finland_level": finland_level,
    }.items() if not v]
    if missing:
        return 400, {"error": f"필드 누락: {missing}"}

    if unit_name not in UNIT_CONFIG:
        return 400, {"error": f"지원하지 않는 단원: {unit_name}"}

    num = MATRIX_TO_NUM.get(matrix_pos)
    if not num:
        return 400, {"error": f"알 수 없는 매트릭스 위치: {matrix_pos}"}

    cfg = UNIT_CONFIG[unit_name]
    problem_id = f"{cfg['id_prefix']}-{num}"

    print(f"[시작] {problem_id} {matrix_pos} [{korean_level}×{finland_level}]", flush=True)
    notify_make({"status": "started", "problem_id": problem_id,
                 "matrix_position": matrix_pos, "korean_level": korean_level,
                 "finland_level": finland_level})

    try:
        intro = load_intro(unit_name)
        problem = generate_problem(intro, matrix_pos, korean_level, finland_level)
        problem["problem_id"] = problem_id

        qc = problem.get("quality_check", {})
        fails = [k for k, v in qc.items() if not v.get("pass", True)]
        if fails:
            print(f"[경고] 품질 미통과: {fails}", flush=True)

        filepath = save_and_commit(problem, unit_name)
        print(f"[완료] {filepath}", flush=True)

        notify_make({"status": "done", "problem_id": problem_id, "fails": fails})
        return 200, {"status": "ok", "problem_id": problem_id, "quality_fails": fails}

    except Exception as e:
        print(f"[오류] {e}", flush=True)
        notify_make({"status": "error", "problem_id": problem_id, "message": str(e)})
        return 500, {"error": str(e)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {format % args}", flush=True)

    def do_GET(self):
        if urlparse(self.path).path == "/health":
            self._respond(200, {"status": "ok"})
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/webhook":
            self._respond(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        print(f"[RAW BODY] {body}", flush=True)

        try:
            data = json.loads(body)
        except Exception:
            self._respond(400, {"error": "invalid JSON"})
            return

        print(f"[PARSED] {data}", flush=True)
        self._respond(202, {"status": "accepted"})
        threading.Thread(target=process_request, args=(data,), daemon=True).start()

    def _respond(self, status, body):
        payload = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(payload))
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    print(f"pipeline server start: http://0.0.0.0:{PORT}")
    print(f"Make.com HTTP module -> POST /webhook")
    print(f"health check -> GET /health")
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()
