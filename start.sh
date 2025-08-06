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

# 서버 시작
echo "🏃 Starting server..."
python server.py