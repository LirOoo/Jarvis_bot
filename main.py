# main.py
from flask import Flask, request
from telegram import Update
from telegram.ext import ContextTypes
import os
import asyncio

from jatvis import JatvisBot  # 假设你的类写在 jatvis.py 里

app = Flask(__name__)

# 初始化 JatvisBot（只初始化一次）
bot = JatvisBot("config.ini")
application = bot.updater  # 复用旧的 dispatcher 和 handlers（要兼容 PTB v20 建议迁移）

@app.route('/')
def home():
    return 'JatvisBot Cloud Run is online.'

@app.route('/webhook', methods=['POST'])
async def webhook():
    update = Update.de_json(request.get_json(force=True), bot.telegram_chatbot)
    await application.dispatcher.process_update(update)
    return "ok"

if __name__ == "__main__":
    # 不再用 polling，只运行 Flask
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
