"""E2E 파이프라인 시간 측정 및 답변 품질 확인 스크립트"""
import asyncio
import json
import sys
import time

import httpx

# Windows 콘솔 UTF-8
sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8000"
QUESTION = "장애인 감면 취득세 감면 요건과 감면율은?"


async def login() -> str:
    async with httpx.AsyncClient(base_url=BASE) as client:
        resp = await client.post(
            "/api/auth/gpki",
            json={"cert_id": "cert_001", "password": "test1234"},
        )
        data = resp.json()
        if not data.get("success"):
            print(f"[ERROR] 로그인 실패: {data}")
            sys.exit(1)
        print(f"[OK] 로그인 성공: {data['user_name']} (session={data['session_id'][:8]}...)")
        return data["session_id"]


async def stream_chat(session_id: str, question: str):
    """SSE 스트리밍으로 채팅 요청 후 시간/내용 분석"""
    stages = []
    notices = []
    tokens = []
    sources = []
    confidence = None
    errors = []
    stage_times = {}

    start = time.time()
    first_token_time = None

    async with httpx.AsyncClient(base_url=BASE, timeout=300) as client:
        async with client.stream(
            "POST",
            "/api/chat",
            json={"session_id": session_id, "question": question},
            headers={"Content-Type": "application/json"},
        ) as resp:
            if resp.status_code != 200:
                print(f"[ERROR] HTTP {resp.status_code}")
                return

            buffer = ""
            async for chunk in resp.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    raw_event, buffer = buffer.split("\n\n", 1)
                    event_type = ""
                    event_data = ""
                    for line in raw_event.strip().split("\n"):
                        if line.startswith("event: "):
                            event_type = line[7:]
                        elif line.startswith("data: "):
                            event_data = line[6:]

                    if not event_type or not event_data:
                        continue

                    try:
                        data = json.loads(event_data)
                    except json.JSONDecodeError:
                        continue

                    elapsed = round(time.time() - start, 1)

                    if event_type == "stage_change":
                        stage = data.get("stage", "")
                        stages.append(stage)
                        stage_times[stage] = elapsed
                        print(f"  [{elapsed:>6.1f}s] STAGE: {stage}")

                    elif event_type == "token":
                        token = data.get("token", "")
                        tokens.append(token)
                        if first_token_time is None:
                            first_token_time = elapsed

                    elif event_type == "notice":
                        msg = data.get("message", "")
                        notices.append(msg)
                        print(f"  [{elapsed:>6.1f}s] NOTICE: {msg}")

                    elif event_type == "sources":
                        sources = data.get("sources", [])
                        confidence = data.get("confidence")

                    elif event_type == "error":
                        errors.append(data.get("message", ""))
                        print(f"  [{elapsed:>6.1f}s] ERROR: {data.get('message')}")

                    elif event_type == "olta_login_required":
                        print(f"  [{elapsed:>6.1f}s] OLTA: {data.get('message')}")

    total = round(time.time() - start, 1)

    # ── 결과 출력 ──
    answer = "".join(tokens)
    print()
    print("=" * 70)
    print(f"질문: {question}")
    print("=" * 70)

    print(f"\n[시간 측정]")
    print(f"  총 소요 시간: {total}초")
    if first_token_time:
        print(f"  첫 토큰까지: {first_token_time}초")
    for stage_name, t in stage_times.items():
        print(f"  {stage_name}: {t}초 시점 진입")

    print(f"\n[답변 품질]")
    print(f"  답변 길이: {len(answer)}자")
    print(f"  출처 수: {len(sources)}건")
    if confidence:
        print(f"  신뢰도: {confidence.get('label')} ({confidence.get('score')})")
    print(f"  단계: {' → '.join(stages)}")
    print(f"  알림 수: {len(notices)}건")
    if errors:
        print(f"  에러: {errors}")

    print(f"\n[답변 미리보기 (앞 500자)]")
    print("-" * 50)
    print(answer[:500])
    print("-" * 50)

    if sources:
        print(f"\n[출처 목록 (상위 5건)]")
        for s in sources[:5]:
            print(f"  - [{s.get('type', '')}] {s.get('title', '')[:60]}")

    return {
        "total_seconds": total,
        "first_token": first_token_time,
        "answer_length": len(answer),
        "source_count": len(sources),
        "confidence": confidence,
        "stages": stages,
        "notice_count": len(notices),
    }


async def main():
    print("=" * 70)
    print("E2E 파이프라인 시간 측정 및 품질 확인")
    print("=" * 70)

    session_id = await login()
    print(f"\n질문: {QUESTION}\n")
    result = await stream_chat(session_id, QUESTION)

    if result:
        print(f"\n{'=' * 70}")
        print("최종 요약")
        print(f"{'=' * 70}")
        print(f"  총 소요: {result['total_seconds']}초")
        print(f"  첫 토큰: {result['first_token']}초")
        print(f"  답변 길이: {result['answer_length']}자")
        print(f"  출처: {result['source_count']}건")
        if result['confidence']:
            print(f"  신뢰도: {result['confidence']}")


if __name__ == "__main__":
    asyncio.run(main())
