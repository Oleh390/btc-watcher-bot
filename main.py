import os
from flask import Flask, request

app = Flask(__name__)

@app.route("/", methods=["POST"])
def get_chat_id():
    data = request.json
    if data and "message" in data:
        chat_id = data["message"]["chat"]["id"]
        print(f"👤 chat_id: {chat_id}")
    return "OK"

if __name__ == "__main__":
    print("🚀 Flask сервер запущен. Жду сообщения...")
    app.run(host="0.0.0.0", port=8000)