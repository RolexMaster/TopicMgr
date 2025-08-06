#!/bin/bash

# Azure Container Registry 설정 스크립트
# 사용법: ./setup-azure.sh <resource-group-name> <registry-name> <location>

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 함수 정의
print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 매개변수 확인
if [ $# -ne 3 ]; then
    echo "사용법: $0 <resource-group-name> <registry-name> <location>"
    echo "예시: $0 myResourceGroup myContainerRegistry eastus"
    exit 1
fi

RESOURCE_GROUP=$1
REGISTRY_NAME=$2
LOCATION=$3

print_step "Azure Container Registry 설정을 시작합니다..."

# 1. Azure CLI 로그인 확인
print_step "Azure CLI 로그인 상태 확인..."
if ! az account show &> /dev/null; then
    print_warning "Azure CLI에 로그인되지 않았습니다. 로그인을 진행합니다..."
    az login
else
    print_success "Azure CLI에 이미 로그인되어 있습니다."
fi

# 2. 리소스 그룹 생성
print_step "리소스 그룹 생성: $RESOURCE_GROUP"
if az group show --name $RESOURCE_GROUP &> /dev/null; then
    print_warning "리소스 그룹 '$RESOURCE_GROUP'이 이미 존재합니다."
else
    az group create --name $RESOURCE_GROUP --location $LOCATION
    print_success "리소스 그룹 '$RESOURCE_GROUP'이 생성되었습니다."
fi

# 3. Container Registry 생성
print_step "Container Registry 생성: $REGISTRY_NAME"
if az acr show --name $REGISTRY_NAME --resource-group $RESOURCE_GROUP &> /dev/null; then
    print_warning "Container Registry '$REGISTRY_NAME'이 이미 존재합니다."
else
    az acr create \
        --resource-group $RESOURCE_GROUP \
        --name $REGISTRY_NAME \
        --sku Basic \
        --admin-enabled true
    print_success "Container Registry '$REGISTRY_NAME'이 생성되었습니다."
fi

# 4. Container Registry 정보 가져오기
print_step "Container Registry 정보 확인..."
LOGIN_SERVER=$(az acr show --name $REGISTRY_NAME --resource-group $RESOURCE_GROUP --query loginServer --output tsv)
CREDENTIALS=$(az acr credential show --name $REGISTRY_NAME --resource-group $RESOURCE_GROUP)

USERNAME=$(echo $CREDENTIALS | jq -r '.username')
PASSWORD=$(echo $CREDENTIALS | jq -r '.passwords[0].value')

print_success "Container Registry 정보:"
echo "  로그인 서버: $LOGIN_SERVER"
echo "  사용자명: $USERNAME"
echo "  비밀번호: $PASSWORD"

# 5. Container Apps 환경 생성
print_step "Container Apps 환경 생성..."
ENV_NAME="${RESOURCE_GROUP}Env"
if az containerapp env show --name $ENV_NAME --resource-group $RESOURCE_GROUP &> /dev/null; then
    print_warning "Container Apps 환경 '$ENV_NAME'이 이미 존재합니다."
else
    az containerapp env create \
        --name $ENV_NAME \
        --resource-group $RESOURCE_GROUP \
        --location $LOCATION
    print_success "Container Apps 환경 '$ENV_NAME'이 생성되었습니다."
fi

# 6. GitHub Secrets 정보 출력
print_step "GitHub Secrets 설정 정보:"
echo ""
echo "=== GitHub Secrets 설정 ==="
echo "GitHub 저장소의 Settings > Secrets and variables > Actions에서 다음 시크릿들을 추가하세요:"
echo ""
echo "AZURE_CONTAINER_REGISTRY: $LOGIN_SERVER"
echo "AZURE_REGISTRY_USERNAME: $USERNAME"
echo "AZURE_REGISTRY_PASSWORD: $PASSWORD"
echo "AZURE_RESOURCE_GROUP: $RESOURCE_GROUP"
echo "AZURE_CONTAINER_INSTANCE_NAME: my-web-app"
echo ""

# 7. 로컬 테스트 명령어 출력
print_step "로컬 테스트 명령어:"
echo ""
echo "=== 로컬 테스트 ==="
echo "# Container Registry에 로그인"
echo "az acr login --name $REGISTRY_NAME"
echo ""
echo "# 웹 애플리케이션 빌드 및 푸시"
echo "cd web-app"
echo "docker build -t $LOGIN_SERVER/web-app:latest ."
echo "docker push $LOGIN_SERVER/web-app:latest"
echo ""
echo "# YJS 서버 빌드 및 푸시"
echo "cd ../yjs-server"
echo "docker build -t $LOGIN_SERVER/yjs-server:latest ."
echo "docker push $LOGIN_SERVER/yjs-server:latest"
echo ""

# 8. 배포 확인 명령어 출력
print_step "배포 확인 명령어:"
echo ""
echo "=== 배포 확인 ==="
echo "# Container Apps 목록 확인"
echo "az containerapp list --resource-group $RESOURCE_GROUP"
echo ""
echo "# 로그 확인"
echo "az containerapp logs show --name web-app --resource-group $RESOURCE_GROUP"
echo "az containerapp logs show --name yjs-server --resource-group $RESOURCE_GROUP"
echo ""

print_success "Azure Container Registry 설정이 완료되었습니다!"
echo ""
echo "다음 단계:"
echo "1. GitHub Secrets 설정"
echo "2. 코드를 GitHub에 푸시"
echo "3. GitHub Actions를 통한 자동 배포"
echo ""