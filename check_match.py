import os
import requests
import subprocess
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

# updates a github variable by calling the GitHub CLI
def update_github_variable(variable_name, value):
    """Update een GitHub Repository Variable door de 'gh' CLI aan te roepen."""
    print(f"Poging om variabele '{variable_name}' bij te werken via gh CLI...")
    
    # Converteer de Python dictionary naar een JSON string
    value_str = json.dumps(value)
    
    # Bouw het commando dat we in de terminal zouden typen
    command = [
        "gh",
        "variable",
        "set",
        variable_name,
        "--body",
        value_str
    ]
    
    try:
        # Voer het commando uit en vang de output op
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True  # Zorgt ervoor dat het script faalt als gh een error geeft
        )
        print(f"gh CLI succesvol uitgevoerd. Output: {result.stdout}")
        print(f"Github variable '{variable_name}' succesvol bijgewerkt.")

    except subprocess.CalledProcessError as e:
        # Dit blok wordt uitgevoerd als de gh commando een error code teruggeeft
        print(f"FATALE FOUT: De 'gh' commando faalde met exit code {e.returncode}.")
        print(f"Stderr: {e.stderr}") # Print de foutmelding van de gh tool
        raise Exception("Kon Github variable niet bijwerken via gh CLI.")
    except FileNotFoundError:
        # Dit gebeurt als de 'gh' tool niet is geïnstalleerd (niet van toepassing op GitHub Actions)
        print("FATALE FOUT: De 'gh' command-line tool is niet gevonden.")
        raise
    
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

