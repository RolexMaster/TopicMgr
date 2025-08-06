# Azure Container 배포 가이드

## 사전 요구사항

1. **Azure 계정 및 구독**
   - Azure 계정이 필요합니다
   - 활성화된 Azure 구독이 필요합니다

2. **Azure CLI 설치**
   ```bash
   # Windows
   winget install Microsoft.AzureCLI
   
   # macOS
   brew install azure-cli
   
   # Linux
   curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
   ```

3. **Docker 설치**
   - Docker Desktop 또는 Docker Engine이 설치되어 있어야 합니다

## Azure 리소스 설정

### 1. Azure Container Registry 생성

```bash
# 리소스 그룹 생성
az group create --name myResourceGroup --location eastus

# Container Registry 생성
az acr create --resource-group myResourceGroup \
    --name myContainerRegistry \
    --sku Basic \
    --admin-enabled true

# 로그인 서버 확인
az acr show --name myContainerRegistry --query loginServer --output tsv
```

### 2. Azure Container Apps 환경 생성

```bash
# Container Apps 환경 생성
az containerapp env create \
    --name myContainerAppEnv \
    --resource-group myResourceGroup \
    --location eastus
```

### 3. GitHub Secrets 설정

GitHub 저장소의 Settings > Secrets and variables > Actions에서 다음 시크릿을 설정하세요:

- `AZURE_CONTAINER_REGISTRY`: `myContainerRegistry.azurecr.io`
- `AZURE_REGISTRY_USERNAME`: Azure Container Registry 사용자명
- `AZURE_REGISTRY_PASSWORD`: Azure Container Registry 비밀번호
- `AZURE_RESOURCE_GROUP`: `myResourceGroup`
- `AZURE_CONTAINER_INSTANCE_NAME`: `my-web-app`

### 4. Azure Container Registry 자격 증명 가져오기

```bash
# 사용자명과 비밀번호 가져오기
az acr credential show --name myContainerRegistry
```

## 로컬 테스트

### 1. 의존성 설치

```bash
# Python 의존성 설치
cd web-app
pip install -r requirements.txt

# Node.js 의존성 설치
cd ../yjs-server
npm install
```

### 2. Docker Compose로 로컬 실행

```bash
# 프로젝트 루트에서 실행
docker-compose up --build
```

### 3. 접속 확인

- 웹 애플리케이션: http://localhost:8000
- YJS 서버: http://localhost:1234

## 배포

### 1. GitHub Actions를 통한 자동 배포

1. 코드를 GitHub 저장소에 푸시
2. GitHub Actions가 자동으로 실행됨
3. Azure Container Apps에 배포됨

### 2. 수동 배포

```bash
# Azure에 로그인
az login

# Container Registry에 로그인
az acr login --name myContainerRegistry

# 이미지 빌드 및 푸시
docker build -t myContainerRegistry.azurecr.io/web-app:latest ./web-app
docker push myContainerRegistry.azurecr.io/web-app:latest

docker build -t myContainerRegistry.azurecr.io/yjs-server:latest ./yjs-server
docker push myContainerRegistry.azurecr.io/yjs-server:latest

# Container Apps 배포
az containerapp create \
    --name web-app \
    --resource-group myResourceGroup \
    --environment myContainerAppEnv \
    --image myContainerRegistry.azurecr.io/web-app:latest \
    --target-port 8000 \
    --ingress external \
    --registry-server myContainerRegistry.azurecr.io \
    --registry-username <username> \
    --registry-password <password>

az containerapp create \
    --name yjs-server \
    --resource-group myResourceGroup \
    --environment myContainerAppEnv \
    --image myContainerRegistry.azurecr.io/yjs-server:latest \
    --target-port 1234 \
    --ingress external \
    --registry-server myContainerRegistry.azurecr.io \
    --registry-username <username> \
    --registry-password <password>
```

## 모니터링 및 로그

### 1. Container Apps 로그 확인

```bash
# 웹 애플리케이션 로그
az containerapp logs show --name web-app --resource-group myResourceGroup

# YJS 서버 로그
az containerapp logs show --name yjs-server --resource-group myResourceGroup
```

### 2. 메트릭 확인

```bash
# Container Apps 메트릭
az monitor metrics list \
    --resource <container-app-resource-id> \
    --metric CPUUtilization,MemoryUtilization \
    --interval PT1M
```

## 문제 해결

### 1. 일반적인 문제들

- **이미지 빌드 실패**: Dockerfile 경로와 컨텍스트 확인
- **배포 실패**: Azure 자격 증명 및 권한 확인
- **연결 문제**: 포트 및 네트워크 설정 확인

### 2. 로그 확인

```bash
# Container Apps 로그 스트리밍
az containerapp logs show --name web-app --resource-group myResourceGroup --follow
```

### 3. 리소스 정리

```bash
# 리소스 그룹 삭제 (모든 리소스 포함)
az group delete --name myResourceGroup --yes --no-wait
```

## 비용 최적화

1. **개발 환경**: Basic SKU Container Registry 사용
2. **프로덕션 환경**: Standard 또는 Premium SKU 고려
3. **자동 스케일링**: 트래픽에 따른 자동 스케일링 설정
4. **리소스 모니터링**: Azure Monitor를 통한 비용 추적

## 보안 고려사항

1. **네트워크 보안**: Private Endpoint 사용 고려
2. **인증**: Azure AD 통합
3. **시크릿 관리**: Azure Key Vault 사용
4. **SSL/TLS**: HTTPS 강제 적용