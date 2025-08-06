#!/bin/bash

# Yjs + pycrdt-websocket 협업 시스템 시작 스크립트

echo "🚀 Starting Yjs + pycrdt-websocket collaboration system..."

# Python 환경 확인
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# 가상환경 확인
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run ./setup.sh first."
    exit 1
fi

# 가상환경 활성화
source venv/bin/activate

# .env 파일이 있으면 환경 변수 로드
if [ -f ".env" ]; then
    echo "📋 Loading environment variables from .env file..."
    export $(grep -v '^#' .env | xargs)
fi

# 서버 시작
echo "🏃 Starting server..."
echo "📄 HTTP Port: ${PORT:-8000}"
echo "🔌 WebSocket Port: ${WEBSOCKET_PORT:-8765}"
python server.py