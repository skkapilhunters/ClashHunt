import os
import json
import time
import uuid
import math

import firebase_admin
from firebase_admin import credentials, firestore
from quart import Quart, request, render_template_string
from bot_instance import bot  # Pulling bot instance safely
from local_logger import save_to_history  # Import your existing db logic

app = Quart(__name__)

# Initialize Firebase from Environment Variable
firebase_creds_raw = os.environ.get("FIREBASE_CREDENTIALS")

if firebase_creds_raw:
    try:
        cred_dict = json.loads(firebase_creds_raw)
        # Fix escaped newlines in RSA private keys when loaded from ENV vars
        if "private_key" in cred_dict:
            cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
            
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print(f"⚠️ Error parsing FIREBASE_CREDENTIALS: {e}")
else:
    print("⚠️ FIREBASE_CREDENTIALS environment variable not set!")

db = firestore.client()

# Track when the dashboard script loaded
START_TIME = time.time()

# A dictionary to temporarily hold valid tokens and track channel info
ACTIVE_TOKENS = {}

# Reusable template wrapper to keep the theme identical across all pages
def get_base_html(title, content):
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <style>
            :root {{
                --bg-color: #0f111a;
                --card-bg: #1e2235;
                --accent-color: #4e73df;
                --success-color: #2ecc71;
                --text-color: #f8f9fc;
                --text-muted: #a0aec0;
                --danger-color: #e74c3c;
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

            h1, h2 {{
                margin: 10px 0 5px 0;
                letter-spacing: 0.5px;
            }}
            
            h1 {{ font-size: 2rem; }}
            h2 {{ font-size: 1.5rem; color: #4fffc0; text-align: left; margin-bottom: 15px; }}

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

            textarea {{
                width: 100%;
                height: 350px;
                background-color: #121420;
                color: #00ff66;
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px;
                padding: 15px;
                font-family: monospace;
                font-size: 14px;
                box-sizing: border-box;
                resize: vertical;
                margin-bottom: 15px;
            }}
            
            textarea:focus {{
                outline: none;
                border-color: var(--accent-color);
                box-shadow: 0 0 10px rgba(78, 115, 223, 0.3);
            }}

            button {{
                background-color: var(--accent-color);
                color: white;
                border: none;
                padding: 14px 24px;
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
                cursor: pointer;
                width: 100%;
                transition: background 0.2s, transform 0.1s;
                box-shadow: 0 4px 15px rgba(78, 115, 223, 0.3);
            }}
            
            button:hover {{ background-color: #355bc7; transform: translateY(-1px); }}
            button:active {{ transform: translateY(1px); }}

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
            {content}
            <footer>
                Powered by Quart & Render Async Architecture
            </footer>
        </div>
    </body>
    </html>
    """

@app.route('/')
async def home():
    bot_name = bot.user.name if bot.user else "Clan War Tracker"
    avatar_url = bot.user.avatar.url if bot.user and bot.user.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
    guild_count = len(bot.guilds)
    total_users = sum(g.member_count for g in bot.guilds) if bot.guilds else 0
    
    if bot.latency and not math.isnan(bot.latency):
        latency = round(bot.latency * 1000)
    else:
        latency = 0   
        
    uptime_seconds = int(time.time() - START_TIME)
    uptime_hours = uptime_seconds // 3600
    uptime_mins = (uptime_seconds % 3600) // 60
    uptime_string = f"{uptime_hours}h {uptime_mins}m"

    homepage_content = f"""
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
    """
    return get_base_html(f"{bot_name} - Dashboard", homepage_content)


@app.route('/war_conflicts', methods=['GET'])
async def war_conflicts():
    # Supports both /war_conflicts?docid=ID and /war_conflicts?2LRGQ2L9L_2026-08-03_10-38-53
    doc_id = request.args.get('docid')
    if not doc_id and request.args:
        doc_id = list(request.args.keys())[0]

    if not doc_id:
        return "Missing Document ID: Please provide a document parameter in the URL query string.", 400

    try:
        # Fetch document from Firestore "ended_wars" collection
        doc_ref = db.collection('ended_wars').document(doc_id)
        doc = doc_ref.get()

        if not doc.exists:
            return f"War Document Not Found: No war records match ID {doc_id}", 404

        data = doc.to_dict()
        conflict_data = data.get('conflict_data', {})
        war_meta = conflict_data.get('war_metadata', {})
        clans = conflict_data.get('clans', {})
        rosters = conflict_data.get('rosters', [])

        clan_a = clans.get('clan_a', {})
        clan_b = clans.get('clan_b', {})

        # Helper function to match the old attack formatting (e.g. "1. Hit #5: 3 stars 100")
        def format_attacks(attacks_list):
            if not attacks_list or not isinstance(attacks_list, list):
                return "No attacks"
            
            formatted = []
            for i, att in enumerate(attacks_list, 1):
                if isinstance(att, dict):
                    defender = att.get('defender', '?')
                    stars = att.get('stars', 0)
                    destruction = att.get('destruction', 0)
                    formatted.append(f"{i}. Hit #{defender}: {stars} stars {destruction}")
                elif isinstance(att, str):
                    formatted.append(f"{i}. {att}")
                    
            return "<br>".join(formatted) if formatted else "No attacks"

        # Build table rows matching the 6-column format
        roster_rows = ""
        for item in rosters:
            pos = item.get('position', '-')
            ca = item.get('clan_a_member', {})
            cb = item.get('clan_b_member', {})

            ca_attacks = format_attacks(ca.get('attacks'))
            cb_attacks = format_attacks(cb.get('attacks'))
            
            ca_name = ca.get('name', 'N/A')
            ca_tag = ca.get('tag', '')
            cb_name = cb.get('name', 'N/A')
            cb_tag = cb.get('tag', '')

            roster_rows += f"""<tr>
                <td>{pos}</td>
                <td>{ca_name} (<a href="https://link.clashofclans.com/en/?action=OpenPlayerProfile&tag={ca_tag}">{ca_tag}</a>)</td>
                <td>{ca_attacks}</td>
                <td class='lb'>{pos}</td>
                <td>{cb_name} (<a href="https://link.clashofclans.com/en/?action=OpenPlayerProfile&tag={cb_tag}">{cb_tag}</a>)</td>
                <td>{cb_attacks}</td>
            </tr>\n"""

        # Bypassing get_base_html to guarantee the pure white layout without CSS bleed
        full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <title>Chocolate Clash: Viewing War</title>
    <style>
        body {{
            font-family: "Times New Roman", Times, serif;
            font-size: 16px;
            background-color: #ffffff;
            color: #000000;
            margin: 0;
            padding: 20px;
        }}
        #container {{
            width: 75%;
            margin: 20px auto;
            border: 1px solid black;
            text-align: center;
            padding: 10px;
            background-color: #ffffff;
        }}
        #title {{
            font-weight: bold;
            font-size: 32px;
            cursor: pointer;
            color: #000000;
        }}
        #top {{
            display: block;
            text-align: left;
            font-size: 16px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        td {{
            width: inherit;
            border-bottom: 1px solid gray;
            font-size: 16px;
            text-align: left;
            padding: 4px;
            vertical-align: top;
            color: #000000;
        }}
        td.lb {{
            border-left: 1px solid gray;
        }}
        a {{
            text-decoration: none;
            color: blue;
        }}
        a:visited {{
            color: blue;
        }}
        #credits {{
            text-align: center;
            font-size: 16px;
            margin-top: 20px;
            color: #000000;
        }}
    </style>
</head>
<body>
    <div id="container">
        <span id="title">FWA ChocolateClash</span>
        <br><br>
        <span id="top">
            Showing details for a saved clan war. (<a href="#">Show flags & NIC</a>)<br><br>
            <b>Prep. Day Start: </b>{war_meta.get('prep_day_start', 'N/A')}<br>
            <b>Battle Day Start: </b>{war_meta.get('battle_day_start', 'N/A')}<br>
            <b>War Ends: </b>{war_meta.get('war_ends', 'N/A')}<br><br>
            <b>Status: </b>{war_meta.get('status', 'N/A')}<br>
            <b>Last Updated: </b>{war_meta.get('last_updated', 'N/A')}<br>
            <br>
        </span>
        <table>
            <tbody>
                <tr>
                    <td style="width:2%">&nbsp;</td>
                    # <td><img style="width: 50px; height: 50px;" src="https://api-assets.clashofclans.com/badges/512/iZ72bTHH7Kj30_CYE1zSt2YSsY_uzbZTq886n4nokM4.png" alt="Clash of Clans Badge"> </td>
                    <td colspan="2" style="width:48%"><span style="color:red;"><b>Clan A</b></span></td>
                    # <td><img style="width: 50px; height: 50px;" src="{clan_b.get('badge')}" alt="Clash of Clans Badge"></td>
                    <td style="width:2%">&nbsp;</td>
                    <td colspan="2" style="width:48%"><span style="color:red;"><b>Clan B</b></span></td>
                </tr>
                <tr>
                    # <td style="width:2%">&nbsp;</td>
                    <td><img style="width: 50px; height: 50px;" src="{clan_a.get('badge')}" alt="Clash of Clans Badge"> </td>
                    <td colspan="2">
                        {clan_a.get('name', 'N/A')} (<a href="https://link.clashofclans.com/en/?action=OpenClanProfile&tag={clan_a.get('tag')}">{clan_a.get('tag', '')}</a>) lvl. {clan_a.get('level', 0)}<br>
                        {clan_a.get('members_count', 0)} people, {clan_a.get('stars', 0)}★ {clan_a.get('destruction_percentage', '0.0%')} {clan_a.get('attacks_used', 0)} Attacks
                    </td>
                    # <td style="width:2%" class="lb">&nbsp;</td>
                    <td><img style="width: 50px; height: 50px;" src="{clan_b.get('badge')}" alt="Clash of Clans Badge"></td>
                    <td colspan="2">
                        {clan_b.get('name', 'N/A')} (<a href="https://link.clashofclans.com/en/?action=OpenClanProfile&tag={clan_b.get('tag')}">{clan_b.get('tag', '')}</a>) lvl. {clan_b.get('level', 0)}<br>
                        {clan_b.get('members_count', 0)} people, {clan_b.get('stars', 0)}★ {clan_b.get('destruction_percentage', '0.0%')} {clan_b.get('attacks_used', 0)} Attacks
                    </td>
                </tr>
                <tr></tr>
                {roster_rows}
            </tbody>
        </table>
    </div>
    <div id="credits">
        Maintained by Justin <br>
        <a href="#">Support</a> - <a href="#">ToS</a> - <a href="#">Old</a> - <a href="#">Home</a> - <a href="#">Split</a>
    </div>
</body>
</html>"""
        
        # Return full HTML directly with a 200 OK status
        return full_html, 200

    except Exception as e:
        return f"Internal Fetch Failure: {str(e)}", 500

@app.route('/push/<token>', methods=['GET'])
async def view_push_page(token):
    if token not in ACTIVE_TOKENS:
        error_content = """
        <div class="profile-card" style="border-color: var(--danger-color);">
            <h1 style="color: var(--danger-color); font-size: 3.5rem; margin-bottom: 10px;">❌</h1>
            <h1>Link Expired or Invalid</h1>
            <p style="color: var(--text-muted); margin-top: 15px;">Please generate a fresh temporary transmission link using <code>?push</code> in Discord.</p>
        </div>
        """
        return get_base_html("Link Expired - ClashHunt", error_content), 403

    portal_content = """
    <div class="profile-card" style="text-align: left;">
        <h2>🌐 ClashHunt Data Submission Portal</h2>
        <p style="color: var(--text-muted); font-size: 0.95rem; margin-bottom: 25px; line-height: 1.5;">
            Paste your raw JSON data string inside the entry window below.
        </p>
        <form method="POST">
            <textarea name="json_data" placeholder="Paste your raw JSON content here..." required></textarea>
            <button type="submit">🚀 Sync data to Database</button>
        </form>
    </div>
    """
    return get_base_html("Submit Data - ClashHunt", portal_content)


@app.route('/push/<token>', methods=['POST'])
async def handle_push_submit(token):
    if token not in ACTIVE_TOKENS:
        error_content = """
        <div class="profile-card" style="border-color: var(--danger-color);">
            <h1>❌ Access Terminated</h1>
        </div>
        """
        return get_base_html("Error - ClashHunt", error_content), 403
    
    form = await request.form
    raw_data = form.get("json_data", "").strip()
    ctx_info = ACTIVE_TOKENS.pop(token) 
    
    if not raw_data:
        error_content = """
        <div class="profile-card" style="border-color: var(--danger-color);">
            <h1>❌ Submission Rejected</h1>
            <p style="color: var(--text-muted);">Data payload cannot be empty.</p>
        </div>
        """
        return get_base_html("Failed - ClashHunt", error_content), 400

    try:
        save_to_history(raw_data)
        
        channel = bot.get_channel(ctx_info["channel_id"])
        if channel:
            bot.loop.create_task(
                channel.send(f"✅ **Web Sync Complete:** Raw data submitted by <@{ctx_info['author_id']}> processed successfully!")
            )

        success_content = """
        <div class="profile-card" style="border-color: var(--success-color);">
            <h1 style="color: var(--success-color); font-size: 3.5rem; margin-bottom: 10px;">✅</h1>
            <h1>Data Synchronized!</h1>
        </div>
        """
        return get_base_html("Success - ClashHunt", success_content)

    except Exception as e:
        failure_content = f"""
        <div class="profile-card" style="border-color: var(--danger-color);">
            <h1 style="color: var(--danger-color);">❌ Database Synced Error</h1>
            <p style="color: var(--text-muted); font-family: monospace;">{str(e)}</p>
        </div>
        """
        return get_base_html("Execution Failed - ClashHunt", failure_content), 500


@app.route('/post', methods=['GET', 'POST'])
async def handle_resource_post():
    try:
        account_name = request.args.get('account_name', 'Unknown')
        townhall = request.args.get('townhall', 'N/A')
        total_builders = request.args.get('total_builders', 'N/A')
        player_gold = request.args.get('player_gold', '0')
        player_elixir = request.args.get('player_elixir', '0')

        resource_cog = bot.get_cog('ResourceAlert')
        if resource_cog:
            success = await resource_cog.send_resource_embed(
                account_name, townhall, total_builders, player_gold, player_elixir
            )
            if success:
                success_html = """
                <div class="profile-card" style="border-color: var(--success-color);">
                    <h1 style="color: var(--success-color); font-size: 3.5rem; margin-bottom: 10px;">✅</h1>
                    <h1>Alert Dispatched!</h1>
                </div>
                """
                return get_base_html("Success - ClashHunt", success_html), 200

        fail_html = """
        <div class="profile-card" style="border-color: var(--danger-color);">
            <h1>❌ PUSH FAILED</h1>
        </div>
        """
        return get_base_html("Error - ClashHunt", fail_html), 500

    except Exception as e:
        err_html = f"""
        <div class="profile-card" style="border-color: var(--danger-color);">
            <h1>❌ Internal Processing Failure</h1>
            <p style="color: var(--text-muted); font-family: monospace;">{str(e)}</p>
        </div>
        """
        return get_base_html("Error - ClashHunt", err_html), 500


async def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    await app.run_task(host="0.0.0.0", port=port)
