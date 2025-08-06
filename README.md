# Azure Container Web Application

이 프로젝트는 Azure 컨테이너에서 실행되는 웹 애플리케이션입니다.

## 구성 요소

1. **Python FastAPI 웹서버** - 메인 웹 애플리케이션
2. **YJS Node.js 서버** - 실시간 협업 기능
3. **GitHub Actions** - Azure 컨테이너 자동 배포

## 프로젝트 구조

```
├── web-app/              # FastAPI 웹 애플리케이션
│   ├── app/
│   ├── requirements.txt
│   └── Dockerfile
├── yjs-server/           # YJS Node.js 서버
│   ├── src/
│   ├── package.json
│   └── Dockerfile
├── .github/
│   └── workflows/        # GitHub Actions
├── docker-compose.yml    # 로컬 개발용
└── README.md
```

## 로컬 실행

```bash
# 의존성 설치
cd web-app && pip install -r requirements.txt
cd ../yjs-server && npm install

# 로컬 실행
docker-compose up
```

## 배포

GitHub Actions를 통해 Azure 컨테이너에 자동 배포됩니다.

## 접속 URL

- 웹 애플리케이션: `http://localhost:8000`
- YJS 서버: `http://localhost:1234`