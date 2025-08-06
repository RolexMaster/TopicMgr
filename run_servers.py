#!/usr/bin/env python3
"""
통합 서버 실행 스크립트
FastAPI 서버와 pycrdt-websocket 서버를 함께 실행합니다.
"""

import asyncio
import signal
import sys
from concurrent.futures import ProcessPoolExecutor
import subprocess
import os

def run_fastapi():
    """FastAPI 서버 실행"""
    subprocess.run([sys.executable, "main.py"])

def run_websocket():
    """WebSocket 서버 실행"""
    subprocess.run([sys.executable, "websocket_server.py"])

def signal_handler(sig, frame):
    """종료 시그널 처리"""
    print("\n서버를 종료합니다...")
    sys.exit(0)

def main():
    """메인 실행 함수"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("🚀 Yjs + pycrdt-websocket 협업 시스템 시작")
    print("=" * 50)
    print("FastAPI 서버: http://localhost:8000")
    print("WebSocket 서버: ws://localhost:8765")
    print("CRDT 편집기: http://localhost:8000/crdt")
    print("=" * 50)
    print("종료하려면 Ctrl+C를 누르세요.\n")
    
    # 프로세스 풀을 사용하여 두 서버 동시 실행
    with ProcessPoolExecutor(max_workers=2) as executor:
        # FastAPI 서버 실행
        fastapi_future = executor.submit(run_fastapi)
        
        # WebSocket 서버 실행
        websocket_future = executor.submit(run_websocket)
        
        try:
            # 두 프로세스가 완료될 때까지 대기
            fastapi_future.result()
            websocket_future.result()
        except KeyboardInterrupt:
            print("\n서버를 종료합니다...")
            executor.shutdown(wait=False)

if __name__ == "__main__":
    main()