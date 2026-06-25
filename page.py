import os
import time
from quart import Quart
from cogs.war_tracker import bot  # Import bot to pull live stats

app = Quart(__name__)

# Track when the dashboard script loaded
START_TIME = time.time()

@app.route('/')
async def home():
    # Gather live statistics from your Discord bot safely
    bot_name = bot.user.name if bot.user else "Clan War Tracker"
    avatar_url = bot.user.avatar.url if bot.user and bot.user.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
    guild_count = len(bot.guilds)
    total_users = sum(g.member_count for g in bot.guilds) if bot.guilds else 0
    latency = round(bot.latency * 1000) if bot.latency else 0
    
    # Simple uptime calculation
    uptime_seconds = int(time.time() - START_TIME)
    uptime_hours = uptime_seconds // 3600
    uptime_mins = (uptime_seconds % 3600) // 60
    uptime_string = f"{uptime_hours}h {uptime_mins}m"

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{bot_name} - Dashboard</title>
        <style>
            :root {{
                --bg-color: #0f111a;
                --card-bg: #1e2235;
                --accent-color: #4e73df;
                --success-color: #2ecc71;
                --text-color: #f8f9fc;
                --text-muted: #a0aec0;
            }}
            
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: var(--bg-color);
                color: var(--text-color);
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
            }}

            .container {{
                width: 100%;
                max-width: 800px;
                padding: 20px;
                box-sizing: border-box;
            }}

            .profile-card {{
                background: var(--card-bg);
                border-radius: 16px;
                padding: 30px;
                text-align: center;
                box-shadow: 0 10px 30px rgba(0,0,0,0.5);
                border: 1px solid rgba(255,255,255,0.05);
                margin-bottom: 24px;
            }}

            .avatar {{
                width: 100px;
                height: 100px;
                border-radius: 50%;
                border: 4px solid var(--accent-color);
                box-shadow: 0 0 20px rgba(78, 115, 223, 0.5);
                margin-bottom: 15px;
            }}

            h1 {{
                margin: 10px 0 5px 0;
                font-size: 2rem;
                letter-spacing: 0.5px;
            }}

            .status-badge {{
                display: inline-flex;
                align-items: center;
                background: rgba(46, 204, 113, 0.1);
                color: var(--success-color);
                padding: 6px 16px;
                border-radius: 20px;
                font-size: 0.9rem;
                font-weight: 600;
                letter-spacing: 0.5px;
                border: 1px solid rgba(46, 204, 113, 0.2);
            }}

            .status-dot {{
                width: 8px;
                height: 8px;
                background-color: var(--success-color);
                border-radius: 50%;
                margin-right: 8px;
                box-shadow: 0 0 10px var(--success-color);
            }}

            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
                gap: 16px;
            }}

            .stat-card {{
                background: var(--card-bg);
                border-radius: 12px;
                padding: 20px;
                text-align: center;
                border: 1px solid rgba(255,255,255,0.02);
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                transition: transform 0.2s ease;
            }}

            .stat-card:hover {{
                transform: translateY(-3px);
                border-color: rgba(78, 115, 223, 0.3);
            }}

            .stat-value {{
                font-size: 1.6rem;
                font-weight: bold;
                color: var(--text-color);
                margin-bottom: 4px;
            }}

            .stat-label {{
                font-size: 0.85rem;
                color: var(--text-muted);
                text-transform: uppercase;
                letter-spacing: 1px;
            }}

            footer {{
                text-align: center;
                margin-top: 30px;
                font-size: 0.8rem;
                color: var(--text-muted);
            }}
        </style>
    </head>
    <body>

        <div class="container">
            <div class="profile-card">
                <img class="avatar" src="{avatar_url}" alt="Bot Avatar">
                <h1>{bot_name}</h1>
                <p style="color: var(--text-muted); margin-top: 0; margin-bottom: 20px;">Clash of Clans Tracker</p>
                <div class="status-badge">
                    <span class="status-dot"></span>
                    ONLINE & OPERATIONAL
                </div>
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">{guild_count}</div>
                    <div class="stat-label">Servers</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{total_users}</div>
                    <div class="stat-label">Users Tracking</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{latency}ms</div>
                    <div class="stat-label">Ping Latency</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{uptime_string}</div>
                    <div class="stat-label">Uptime</div>
                </div>
            </div>

            <footer>
                Powered by Quart & Render Async Architecture
            </footer>
        </div>

    </body>
    </html>
    """

async def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    await app.run_task(host="0.0.0.0", port=port)
