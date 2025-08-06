# Yjs + pycrdt-websocket 기반 실시간 협업 시스템

브라우저 클라이언트에서 Yjs를 이용한 CRDT 문서 편집을 수행하고, Python 서버(pycrdt-websocket)를 통해 실시간 동기화 및 자동 저장 기능을 구현한 시스템입니다.

## 🚀 주요 기능

- **실시간 협업**: 여러 사용자가 동시에 같은 문서를 편집 가능
- **자동 저장**: 문서 변경사항이 서버에 자동으로 저장됨
- **Room 기반 분리**: 각 room별로 독립적인 문서 관리
- **할 일 목록 관리**: Y.Array 기반의 할 일 추가/삭제/완료 기능

## 📋 시스템 구성

| 구성 요소 | 역할 | 구현 기술 |
|----------|------|----------|
| 웹 UI (/crdt) | 사용자가 room 이름을 입력하고 문서 편집을 테스트하는 페이지 | HTML + JS (Yjs + y-websocket) |
| FastAPI 서버 | /index 및 /crdt HTTP 라우팅 제공 | Python (FastAPI) |
| WebSocket 서버 | 클라이언트와 실시간 CRDT 데이터 동기화 처리 | Python (pycrdt-websocket) |
| 문서 저장소 | room 별 .ys 파일로 문서 내용 저장 | 파일 기반 (./data/room-name.ys) |

## 🛠️ 설치 방법

1. Python 3.8 이상이 설치되어 있는지 확인하세요.

2. 설정 스크립트를 실행하여 가상환경을 생성하고 의존성을 설치합니다:
```bash
./setup.sh
```

또는 수동으로 설치:
```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 🏃‍♂️ 실행 방법

### 방법 1: 시작 스크립트 사용 (권장)
```bash
./start.sh
```

### 방법 2: 통합 서버 실행
```bash
source venv/bin/activate  # Windows: venv\Scripts\activate
python server.py
```

### 방법 3: 개별 서버 실행
```bash
# 터미널 1: FastAPI 서버
source venv/bin/activate
python main.py

# 터미널 2: WebSocket 서버
source venv/bin/activate
python websocket_server.py
```

### 방법 4: 프로세스 관리자 사용
```bash
source venv/bin/activate
python run_servers.py
```

## 📖 사용 방법

1. 서버 실행 후 브라우저에서 http://localhost:8000/crdt 접속

2. Room 이름을 입력하고 "입장하기" 클릭

3. 할 일 목록을 추가하고 실시간으로 동기화되는 것을 확인

4. 다른 브라우저나 탭에서 같은 room에 접속하면 실시간 협업 가능

5. URL 파라미터로 직접 room 접속도 가능: http://localhost:8000/crdt?room=myroom

## 🗂️ 프로젝트 구조

```
.
├── data/                  # Room 문서 저장 디렉토리 (.ys 파일)
├── templates/             # HTML 템플릿
│   └── crdt.html         # CRDT 편집기 페이지
├── static/               # 정적 파일 (현재 비어있음)
├── server.py             # 통합 서버 (FastAPI + WebSocket)
├── main.py              # FastAPI 서버
├── websocket_server.py   # pycrdt-websocket 서버
├── run_servers.py       # 서버 실행 도우미
├── setup.sh             # 초기 설정 스크립트
├── start.sh             # 서버 시작 스크립트
├── requirements.txt     # Python 패키지 의존성
└── README.md           # 프로젝트 문서
```

## 🔧 기술 스택

- **Frontend**: 
  - Yjs: CRDT 구현
  - y-websocket: WebSocket 통신
  - Vanilla JavaScript

- **Backend**:
  - FastAPI: HTTP 서버
  - pycrdt-websocket: CRDT WebSocket 서버
  - pycrdt: Python CRDT 구현

## ⚙️ 환경 설정

- FastAPI 서버: http://localhost:8000
- WebSocket 서버: ws://localhost:8765
- 문서 저장 위치: ./data/{room-name}.ys

## 📝 참고사항

- 서버 종료 시 모든 문서가 자동으로 저장됩니다
- 5초마다 자동 저장이 실행됩니다
- Room 이름은 파일명으로 사용되므로 파일 시스템에서 허용되는 문자만 사용하세요