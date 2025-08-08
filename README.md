# CRDT XML 협업 편집기

Yjs와 pycrdt-websocket을 기반으로 한 실시간 XML 문서 협업 편집 시스템입니다.

## 주요 기능

- **실시간 협업**: 여러 사용자가 동시에 XML 문서를 편집하고 실시간으로 동기화
- **CRDT 기반**: 충돌 없는 동시 편집 지원
- **XML 전용 기능**:
  - XML 구문 검증
  - 자동 포맷팅
  - 구문 하이라이팅 (준비 중)
  - 줄 번호 표시
- **파일 관리**:
  - XML 파일 업로드
  - 편집된 문서 다운로드
  - 자동 저장 (5초마다)
- **룸 기반 협업**: 각 룸별로 독립된 편집 공간 제공

## 📋 시스템 구성

| 구성 요소 | 역할 | 구현 기술 |
|----------|------|----------|
| 웹 UI (/crdt) | 사용자가 room 이름을 입력하고 문서 편집을 테스트하는 페이지 | HTML + JS (Yjs + y-websocket) |
| FastAPI 서버 | /index 및 /crdt HTTP 라우팅 제공 | Python (FastAPI) |
| WebSocket 서버 | 클라이언트와 실시간 CRDT 데이터 동기화 처리 | Python (pycrdt-websocket) |
| 문서 저장소 | room 별 .ys 파일로 문서 내용 저장 | 파일 기반 (`DATA_DIR` 또는 Azure: `/home/data`) |

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

### 방법 2: 수동 실행
```bash
source venv/bin/activate  # Windows: venv\Scripts\activate
python server.py
```


## 사용 방법

1. 서버 시작 후 브라우저에서 `http://localhost:8000` 접속
2. "XML 편집기 시작하기" 클릭
3. 룸 이름을 입력하여 협업 공간 생성 또는 참여
4. XML 문서 편집 시작:
   - 직접 XML 작성
   - 파일 업로드
   - 샘플 XML 사용
5. 실시간으로 다른 사용자와 동기화되는 것을 확인

### XML 편집기 기능

- **XML 정리**: 들여쓰기를 자동으로 정리
- **유효성 검사**: XML 구문 오류 확인
- **비우기**: 편집기 내용 전체 삭제
- **XML 업로드**: 로컬 XML 파일 불러오기
- **XML 다운로드**: 현재 편집 중인 문서 저장
- **샘플 XML**: 예제 XML 문서 삽입

## 🗂️ 프로젝트 구조

```
.
├── data/                  # Room 문서 저장 디렉토리 (.ys 파일)
├── templates/             # HTML 템플릿
│   └── crdt.html         # CRDT 편집기 페이지
├── static/               # 정적 파일 (현재 비어있음)
├── server.py             # 통합 서버 (FastAPI + WebSocket)
├── run_servers.py       # 서버 실행 도우미 (선택 사항, 통합 서버만 사용 시 불필요)
├── setup.sh             # 초기 설정 스크립트
├── start.sh             # 서버 시작 스크립트
├── startup.txt          # Azure App Service 시작 명령
├── .env.example         # 환경 변수 예시
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
  - pycrdt-websocket: CRDT WebSocket 서버 (통합: `server.py`)
  - pycrdt: Python CRDT 구현

## ⚙️ 환경 설정

### 로컬 환경
- FastAPI 서버: http://localhost:8000
- WebSocket 서버: ws://localhost:8765
- 문서 저장 위치: ./data/{room-name}.ys

### Azure 환경
환경 변수로 포트 설정:
- `PORT`: HTTP 서버 포트 (Azure에서 자동 설정)
- `WEBSOCKET_PORT`: WebSocket 서버 포트 (기본값: 8765)
- `DATA_DIR`: 문서 저장 디렉토리 경로 지정. Azure App Service(Linux)에서는 `/home/data`를 권장 (재시작/재배포 후에도 유지됨)

Azure App Service 시작 명령:
```
python server.py
```

## 📝 참고사항

- 서버 종료 시 모든 문서가 자동으로 저장됩니다
- 5초마다 자동 저장이 실행됩니다
- Room 이름은 파일명으로 사용되므로 파일 시스템에서 허용되는 문자만 사용하세요