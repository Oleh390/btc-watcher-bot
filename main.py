import os
import asyncio
import requests
import websockets
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

@app.route("/")
def index():
    return "✅ BTC Watcher Bot is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
