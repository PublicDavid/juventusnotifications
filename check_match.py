import os
import requests
import time
import pytz
import json
from discord_webhook import DiscordWebhook, DiscordEmbed
from datetime import datetime, timedelta, timezone

# CONFIG VARIABLES
DISCORD_BOT = os.getenv("DISCORD_BOT")
TEAM = "Juventus"
TEAM_ID = 133676  # Juventus ID in TheSportsDB
TIMEZONE = "Europe/Brussels"
#Github Actions Token
GH_TOKEN = os.environ.get("GH_TOKEN")
GH_REPO = os.environ.get("GH_REPO")

# --- sends embed to discord channel ---
def send_discord_notification(embed):
    try:
        webhook = DiscordWebhook(url=DISCORD_BOT, rate_limit_retry=True)
        webhook.add_embed(embed)
        response = webhook.execute()
        print("Notification sent to Discord.")
    except Exception as e:
        print(f"Error sending Discord notification: {e}")

# --- sends a reminder a day before the match ---
def send_daily_reminder(match):
    global daily_reminder_sent_for_date

    match_date_str = match['dateEvent']

    # check if reminder has already been sent for this match date
    if daily_reminder_sent_for_date == match_date_str:
        print(f"Reminder already sent for match on {match_date_str}.")
        return
    
    if match['strHomeTeam'] == TEAM:
        opponent = match['strAwayTeam']
        opponent_logo = match.get('strAwayTeamBadge')
    else:
        opponent = match['strHomeTeam']
        opponent_logo = match.get('strHomeTeamBadge')

    competition = match['strLeague']

    datetime_str = f"{match['dateEvent']} {match['strTime']}"
    match_datetime_utc = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

    local_timezone = pytz.timezone(TIMEZONE)
    fixture_local = match_datetime_utc.astimezone(local_timezone)

    embed = DiscordEmbed(title="⚽ Matchday tomorrow! ⚽", description=f"Tomorrow ({fixture_local.strftime('%d-%m-%Y')}) Juventus plays a game in **{competition}**." ,color='000000')
    if opponent_logo:
        embed.set_thumbnail(url=opponent_logo)
    else:
        embed.set_thumbnail(url="https://nl.wikipedia.org/wiki/Juventus_FC#/media/Bestand:Juventus_FC_-_logo_black_(Italy,_2020).svg")
    embed.add_embed_field(name="Opponent", value=opponent)
    embed.add_embed_field(name="Time", value=f"{fixture_local.strftime('%H:%M')}")
    embed.set_footer(text="Fino alla fine! 🖤🤍")

    send_discord_notification(embed)
    daily_reminder_sent_for_date = match_date_str

# updates a github variable
def update_github_variable(variable_name, value):
    if not GH_TOKEN:
        raise ValueError("FATAL ERROR: De GH_TOKEN secret is niet gevonden of is leeg!")
    print(f"Token gevonden, begint met: {GH_TOKEN[:4]}...")
    url = f"https://api.github.com/repos/{GH_REPO}/actions/variables/{variable_name}"
    headers = {
        "Authorization": f"token {os.environ['GH_TOKEN']}",
        "Accept": "application/vnd.github+json"
    }
    data = {"name": variable_name, "value": json.dumps(value)}
    response = requests.patch(url, json=data)
    if response.status_code == 204:
        print(f"Github variable '{variable_name}' updated.")
    else:
        print(f"Error updating Github variable: {response.status_code} - {response.text}")
        raise Exception("Can't find Github variable.")
    
# find the next match and update the variable
def find_next_match():
    print("Searching next game...")
    url = f"https://www.thesportsdb.com/api/v1/json/123/eventsnext.php?id={TEAM_ID}"
    try:
        response = requests.get(url).json()
        if response.get('events'):
            match = response['events'][0]
            print(f"Found next game: {match['strEvent']} op {match['dateEvent']}")
            
            match_info_to_store = {
                "idEvent": match['idEvent'],
                "dateEvent": match['dateEvent'],
                "strTime": match['strTime'],
                "strEvent": match['strEvent']
            }
            update_github_variable('NEXT_MATCH_INFO', match_info_to_store)

            # Logic for daily reminders
            now_utc = datetime.now(timezone.utc)
            match_time_utc = datetime.strptime(f"{match['dateEvent']} {match['strTime']}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if now_utc.date() == (match_time_utc.date() - timedelta(days=1)):
                send_daily_reminder(match)
        else:
            print("Didn't find any upcoming games, resetting variable.")
            update_github_variable('NEXT_MATCH_INFO', {})

    except Exception as e:
        print(f"Error while fetching next game: {e}")

if __name__ == "__main__":
    find_next_match()
