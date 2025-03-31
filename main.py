# main.py
from flask import Flask, request
from telegram import Update
from telegram.ext import ContextTypes
import os
import asyncio

from jarvis_bot import JatvisBot  # 假设你的类写在 jatvis.py 里

app = Flask(__name__)

# 初始化 Bot 实例（只初始化一次）
bot = JatvisBot("config.ini")
bot.start("https://jatvisbot-36623340325.asia-east1.run.app/webhook")  # ✅ 注册 Webhook
dispatcher = bot.updater.dispatcher

@app.route("/")
def home():
    return "✅ JatvisBot Cloud Run is alive!"

@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot.telegram_chatbot)
    dispatcher.process_update(update)
    return "ok"

if __name__ == "__main__":
    # Cloud Run 会设置 PORT 环境变量
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
    # 读取刚才部署用的 main.py 内容，确认 Flask 是否正确监听了 PORT=8080
   

