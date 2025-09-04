# send_score.py
import os
import requests
import json
import pytz
from discord_webhook import DiscordWebhook, DiscordEmbed
from datetime import datetime, timedelta, timezone

# --- CONFIGURATIE (hetzelfde als in check_match.py) ---
DISCORD_BOT = os.environ.get("DISCORD_BOT")
GH_TOKEN = os.environ.get("GH_TOKEN")
GH_REPO = os.environ.get("GH_REPO")
BASE_URL = "https://www.thesportsdb.com/api/v1/json/123/"
TEAM = "Juventus"
TIMEZONE = "Europe/Brussels"

# --- sends embed to discord channel ---
def send_discord_notification(embed):
    try:
        webhook = DiscordWebhook(url=DISCORD_BOT, rate_limit_retry=True)
        webhook.add_embed(embed)
        response = webhook.execute()
        print("Notification sent to Discord.")
    except Exception as e:
        print(f"Error sending Discord notification: {e}")

# --- shows final score of game ---
def send_final_score(match_id):
    url = f"{BASE_URL}lookupevent.php?id={match_id}"

    print("Fetching final score for match ID:", match_id)

    try:
        response = requests.get(url).json()

        if response.get('events'):
            match = response['events'][0]

            # check if the game is finished
            if match.get('strStatus') == 'Match Finished':
                home_team = match['strHomeTeam']
                away_team = match['strAwayTeam']
                home_score = match['intHomeScore']
                away_score = match['intAwayScore']
                competition = match['strLeague']

                if match['strHomeTeam'] == TEAM:
                    opponent = match['strAwayTeam']
                    opponent_logo = match.get('strAwayTeamBadge')
                else:
                    opponent = match['strHomeTeam']
                    opponent_logo = match.get('strHomeTeamBadge')

                embed = DiscordEmbed(title="🏆 Match Ended! 🏆", description=f"Juventus played a game in **{competition}**." ,color='000000')
                if opponent_logo:
                    embed.set_thumbnail(url=opponent_logo)
                else:
                    embed.set_thumbnail(url="https://nl.wikipedia.org/wiki/Juventus_FC#/media/Bestand:Juventus_FC_-_logo_black_(Italy,_2020).svg")
                embed.add_embed_field(name="Opponent", value=opponent)
                embed.add_embed_field(name="Final Score", value=f"{home_team} {home_score} - {away_score} {away_team}")
                embed.set_footer(text="Fino alla fine! 🖤🤍")

                send_discord_notification(embed)
                print("Final score notification sent.")
                return True
            else:
                print("No match details found for final score.")

    except Exception as e:
        print(f"Error fetching final score: {e}")

    return False


# updates a github variable
def update_github_variable(variable_name, value):
    print("Trying to update variable '{variable_name}")
    value_str = json.dumps(value)
    command = ["gh", "variable", "set", variable_name, "--body", value_str]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        print(f"gh cli succesfull")
    except subprocess.CalledProcessError as e:
        print(f"FATAL ERROR: gh command failed with exit code: {e.returncode}")
        print(f"Stderr: {e.stderr}")
        raise Exception("Couldn't update github variable via gh cli")
    

def get_github_variable(variable_name):
    url = f"https://api.github.com/repos/{GH_REPO}/actions/variables/{variable_name}"
    headers = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()['value']
    else:
        raise Exception(f"Can't read Github variable: {response.text}")

# Checks if game has ended and sends final score
def check_and_send_final_score():
    print("Checking if final score is avaialable...")
    match_info_str = get_github_variable('NEXT_MATCH_INFO')
    
    if not match_info_str or match_info_str == "{}":
        print("No game available.")
        return

    match_info = json.loads(match_info_str)
    
    datetime_str = f"{match_info['dateEvent']} {match_info['strTime']}"
    match_time_utc = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    match_end_time = match_time_utc + timedelta(minutes=130)
    
    if datetime.now(timezone.utc) > match_end_time:
        print(f"Game {match_info['idEvent']} has ended. Fetching final score...")
        success = send_final_score(match_info['idEvent'])
        if success:
            print("Final score has been send._Resetting Github variable.")
            update_github_variable('NEXT_MATCH_INFO', {})
        else:
            print("Final score not available yet, trying again in 15 minutes.")
    else:
        print("Game not finished yet.")

if __name__ == "__main__":
    check_and_send_final_score()
