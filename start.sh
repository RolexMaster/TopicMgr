#!/bin/bash

# Yjs + pycrdt-websocket 협업 시스템 시작 스크립트

echo "🚀 Starting Yjs + pycrdt-websocket collaboration system..."

# Python 환경 확인
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# 가상환경이 있으면 활성화
if [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
    echo "🔌 Activating virtual environment..."
    source venv/bin/activate
else
    echo "⚠️  Virtual environment not found. Checking system packages..."
    
    # 필수 패키지가 설치되어 있는지 확인
    if ! python3 -c "import fastapi" 2>/dev/null; then
        echo "❌ Required packages not found. Please install packages with:"
        echo "   pip3 install --break-system-packages -r requirements.txt"
        echo "   Or create a virtual environment first with:"
        echo "   python3 -m venv venv"
        exit 1
    fi
    echo "✅ Using system Python packages"
fi

# .env 파일이 있으면 환경 변수 로드
if [ -f ".env" ]; then
    echo "📋 Loading environment variables from .env file..."
    export $(grep -v '^#' .env | xargs)
fi

mkdir -p /home/data/rooms || true

# 서버 시작
echo "🏃 Starting server..."
echo "📄 HTTP Port: ${PORT:-8000}"
python3 simpleServer.py