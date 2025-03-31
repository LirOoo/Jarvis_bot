# 使用轻量的 Python 3.12 镜像
FROM python:3.12-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 安装构建依赖（编译 gensim 和 scikit-learn 用）
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    libopenblas-dev \
    liblapack-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY . /app

# 安装 pip 包
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# 启动 bot 程序
CMD ["python", "jarvis_bot.py"]
