FROM python:3.10-slim

WORKDIR /app

# Python 依赖
COPY requirements.txt .
RUN pip install  -i https://pypi.tuna.tsinghua.edu.cn/simple   --no-cache-dir gunicorn -r requirements.txt

# 项目代码
COPY . .

# 非 root 用户
RUN useradd -m -u 1000 tarot && chown -R tarot:tarot /app
USER tarot

EXPOSE 5002

CMD ["gunicorn", "-c", "gunicorn.conf.py", "tarot.app:create_app()"]
