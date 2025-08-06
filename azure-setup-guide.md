# Azure Container Registry 설정 후 단계별 가이드

## 1. Container Registry 자격 증명 확인

```bash
# Container Registry 사용자명과 비밀번호 확인
az acr credential show --name <your-registry-name>

# 예시:
az acr credential show --name myContainerRegistry
```

출력 예시:
```json
{
  "passwords": [
    {
      "name": "password",
      "value": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    },
    {
      "name": "password2", 
      "value": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    }
  ],
  "username": "myContainerRegistry"
}
```

## 2. Container Registry 로그인 서버 확인

```bash
# 로그인 서버 URL 확인
az acr show --name <your-registry-name> --query loginServer --output tsv

# 예시:
az acr show --name myContainerRegistry --query loginServer --output tsv
# 출력: myContainerRegistry.azurecr.io
```

## 3. Azure Container Apps 환경 생성

```bash
# Container Apps 환경 생성
az containerapp env create \
    --name myContainerAppEnv \
    --resource-group myResourceGroup \
    --location eastus
```

## 4. GitHub Secrets 설정

GitHub 저장소에서 **Settings > Secrets and variables > Actions**로 이동하여 다음 시크릿들을 추가:

### 필수 Secrets:
- `AZURE_CONTAINER_REGISTRY`: `myContainerRegistry.azurecr.io`
- `AZURE_REGISTRY_USERNAME`: `myContainerRegistry` (또는 확인된 사용자명)
- `AZURE_REGISTRY_PASSWORD`: 확인된 비밀번호
- `AZURE_RESOURCE_GROUP`: `myResourceGroup`
- `AZURE_CONTAINER_INSTANCE_NAME`: `my-web-app`

### GitHub Secrets 추가 방법:
1. GitHub 저장소 페이지에서 **Settings** 클릭
2. 왼쪽 메뉴에서 **Secrets and variables** > **Actions** 클릭
3. **New repository secret** 버튼 클릭
4. 각 시크릿 추가:
   - Name: `AZURE_CONTAINER_REGISTRY`
   - Value: `myContainerRegistry.azurecr.io`
   - 반복하여 모든 시크릿 추가

## 5. 로컬에서 Container Registry 테스트

```bash
# Azure CLI로 로그인
az login

# Container Registry에 로그인
az acr login --name <your-registry-name>

# 예시:
az acr login --name myContainerRegistry

# Docker 이미지 빌드 및 푸시 테스트
cd web-app
docker build -t myContainerRegistry.azurecr.io/web-app:test .
docker push myContainerRegistry.azurecr.io/web-app:test

cd ../yjs-server
docker build -t myContainerRegistry.azurecr.io/yjs-server:test .
docker push myContainerRegistry.azurecr.io/yjs-server:test
```

## 6. GitHub Actions 워크플로우 확인

프로젝트의 `.github/workflows/deploy.yml` 파일이 올바르게 설정되어 있는지 확인:

```yaml
env:
  AZURE_CONTAINER_REGISTRY: ${{ secrets.AZURE_CONTAINER_REGISTRY }}
  AZURE_CONTAINER_INSTANCE_NAME: ${{ secrets.AZURE_CONTAINER_INSTANCE_NAME }}
  AZURE_RESOURCE_GROUP: ${{ secrets.AZURE_RESOURCE_GROUP }}
```

## 7. 코드 푸시 및 배포 테스트

```bash
# 코드를 GitHub에 푸시
git add .
git commit -m "Initial commit with Azure deployment setup"
git push origin main
```

## 8. 배포 확인

1. **GitHub Actions 확인**:
   - GitHub 저장소에서 **Actions** 탭 클릭
   - 워크플로우 실행 상태 확인

2. **Azure Portal에서 확인**:
   - Azure Portal > Container Apps
   - 생성된 앱 확인

3. **URL 확인**:
   - Container Apps에서 제공하는 URL로 접속 테스트

## 9. 문제 해결

### 일반적인 문제들:

1. **권한 오류**:
   ```bash
   # Azure CLI 재로그인
   az logout
   az login
   ```

2. **Container Registry 접근 오류**:
   ```bash
   # Container Registry 권한 확인
   az acr show --name <your-registry-name> --query accessControlList
   ```

3. **GitHub Actions 실패**:
   - GitHub Secrets 값 확인
   - Azure 구독 상태 확인
   - 리소스 그룹 권한 확인

## 10. 모니터링 설정

```bash
# Container Apps 로그 확인
az containerapp logs show --name web-app --resource-group myResourceGroup

# 메트릭 확인
az monitor metrics list \
    --resource <container-app-resource-id> \
    --metric CPUUtilization,MemoryUtilization
```

## 11. 비용 최적화

1. **개발 환경**: Basic SKU 사용
2. **프로덕션 환경**: Standard 또는 Premium SKU 고려
3. **자동 스케일링**: 트래픽에 따른 스케일링 설정
4. **리소스 모니터링**: Azure Monitor 설정

## 12. 보안 설정

1. **네트워크 보안**: Private Endpoint 고려
2. **인증**: Azure AD 통합
3. **시크릿 관리**: Azure Key Vault 사용
4. **SSL/TLS**: HTTPS 강제 적용