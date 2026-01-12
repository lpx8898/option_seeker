# 1. 使用官方 Python 3.10 轻量版镜像 (体积小，速度快)
FROM python:3.10-slim

# 2. 设置容器内的工作目录
WORKDIR /app

# 3. 设置环境变量 (防止 Python 生成 .pyc 文件，让日志即时输出)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 4. 这一步是优化：先只复制依赖清单
# 这样如果你只改了代码没改依赖，Docker 会利用缓存，不用重新安装库
COPY requirements.txt .

# 5. 安装 Python 依赖库
# 顺便升级 pip，并使用清华源或默认源 (这里使用默认源)
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. 复制剩下的所有代码文件 (app.py, ib_logic.py 等) 到容器里
COPY . .

# 7. 暴露 Streamlit 的默认端口
EXPOSE 8501

# 8. 启动命令
# --server.address=0.0.0.0 是必须的，否则外部无法访问
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]