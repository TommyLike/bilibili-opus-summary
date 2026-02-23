# Stage 1: 构建 Vue 前端
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# Stage 2: Flask 运行时
FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bilibili_summary.py app.py ./

# 将 Vue 构建产物复制到 Flask 的 static 目录
COPY --from=frontend /app/frontend/dist ./static

# output 目录挂载点（存储生成文件）
VOLUME /app/output

EXPOSE 5000

CMD ["python", "app.py"]
