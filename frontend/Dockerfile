FROM node:20-alpine

# pnpm 설치
RUN npm install -g pnpm

WORKDIR /app

# 의존성 설치
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install

COPY . .

EXPOSE 5173

# 모든 네트워크 인터페이스에서 접근 가능하도록 --host 옵션 사용
CMD ["pnpm", "dev", "--host"]
