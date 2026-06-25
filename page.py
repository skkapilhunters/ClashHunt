import os
from quart import Quart

app = Quart(__name__)

@app.route('/')
async def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Bot Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; background-color: #1a1a1a; color: #ffffff; text-align: center; padding: 50px; }
            .status { color: #2ecc71; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>🤖 Clan War Tracker Dashboard</h1>
        <p>Status: <span class="status">ONLINE & RUNNING</span></p>
    </body>
    </html>
    """

async def run_web_server():
    # Render automatically passes a PORT environment variable. If missing, it defaults to 8080.
    port = int(os.environ.get("PORT", 8080))
    # Run the server on 0.0.0.0 so Render can access it from the outside
    await app.run_task(host="0.0.0.0", port=port)
