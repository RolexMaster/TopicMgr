# GitHub Secrets 설정 가이드

## 1. GitHub 저장소에서 Secrets 설정

### 단계별 설정 방법:

1. **GitHub 저장소 페이지로 이동**
   - GitHub에서 해당 저장소 페이지 열기

2. **Settings 메뉴로 이동**
   - 저장소 페이지 상단의 **Settings** 탭 클릭

3. **Secrets and variables 메뉴로 이동**
   - 왼쪽 사이드바에서 **Secrets and variables** 클릭
   - **Actions** 서브메뉴 클릭

4. **New repository secret 버튼 클릭**
   - **New repository secret** 버튼 클릭

5. **각 Secret 추가**

## 2. 필수 Secrets 목록

다음 Secrets들을 순서대로 추가하세요:

### AZURE_CONTAINER_REGISTRY
- **Name**: `AZURE_CONTAINER_REGISTRY`
- **Value**: `myContainerRegistry.azurecr.io` (실제 Container Registry 이름으로 변경)

### AZURE_REGISTRY_USERNAME
- **Name**: `AZURE_REGISTRY_USERNAME`
- **Value**: `myContainerRegistry` (실제 사용자명으로 변경)

### AZURE_REGISTRY_PASSWORD
- **Name**: `AZURE_REGISTRY_PASSWORD`
- **Value**: `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` (실제 비밀번호로 변경)

### AZURE_RESOURCE_GROUP
- **Name**: `AZURE_RESOURCE_GROUP`
- **Value**: `myResourceGroup` (실제 리소스 그룹 이름으로 변경)

### AZURE_CONTAINER_INSTANCE_NAME
- **Name**: `AZURE_CONTAINER_INSTANCE_NAME`
- **Value**: `my-web-app`

## 3. 실제 값 확인 방법

### Azure CLI로 Container Registry 정보 확인:

```bash
# Container Registry 로그인 서버 확인
az acr show --name <your-registry-name> --query loginServer --output tsv

# Container Registry 자격 증명 확인
az acr credential show --name <your-registry-name>
```

### 예시 출력:
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

## 4. 설정 완료 확인

모든 Secrets가 설정되면:

1. **Secrets 목록 확인**
   - Settings > Secrets and variables > Actions 페이지에서
   - 모든 필수 Secrets가 목록에 표시되는지 확인

2. **워크플로우 파일 확인**
   - `.github/workflows/deploy.yml` 파일이 올바르게 설정되어 있는지 확인

3. **코드 푸시**
   ```bash
   git add .
   git commit -m "Add Azure deployment configuration"
   git push origin main
   ```

## 5. 문제 해결

### 일반적인 문제들:

1. **Secret 값이 올바르지 않은 경우**
   - Azure CLI로 다시 확인
   - Secret 삭제 후 재생성

2. **권한 문제**
   - Azure 구독 상태 확인
   - Container Registry 권한 확인

3. **워크플로우 실행 실패**
   - GitHub Actions 로그 확인
   - Secret 이름과 값 재확인

## 6. 보안 고려사항

- **Secret 값은 절대 공개하지 마세요**
- **정기적으로 비밀번호 변경**
- **최소 권한 원칙 적용**
- **액세스 로그 모니터링**

## 7. 추가 설정 (선택사항)

### Azure AD 인증 (고급 설정)

더 안전한 인증을 위해 Azure AD 서비스 주체를 사용할 수 있습니다:

```bash
# 서비스 주체 생성
az ad sp create-for-rbac --name "github-actions" --role contributor \
    --scopes /subscriptions/<subscription-id>/resourceGroups/<resource-group> \
    --sdk-auth
```

이 경우 추가 Secrets가 필요합니다:
- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`