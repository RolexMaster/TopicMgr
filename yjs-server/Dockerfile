FROM node:18-alpine

# 작업 디렉토리 설정
WORKDIR /app

# package.json과 package-lock.json 복사
COPY package*.json ./

# 의존성 설치
RUN npm ci --only=production

# 소스 코드 복사
COPY src/ ./src/
COPY public/ ./public/

# 포트 노출
EXPOSE 1234

# 환경 변수 설정
ENV NODE_ENV=production
ENV PORT=1234

# 애플리케이션 실행
CMD ["node", "src/index.js"]