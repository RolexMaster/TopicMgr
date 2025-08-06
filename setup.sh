#!/bin/bash

# Yjs + pycrdt-websocket 협업 시스템 설정 스크립트

echo "🔧 Setting up Yjs + pycrdt-websocket collaboration system..."

# Python 환경 확인
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# 가상환경 생성
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# 가상환경 활성화
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# 의존성 설치
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Setup complete!"
echo ""
echo "To start the server, run:"
echo "  source venv/bin/activate"
echo "  python server.py"
echo ""
echo "Or use the start script:"
echo "  ./start.sh"