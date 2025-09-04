import os
import requests
import time
import pytz
from discord_webhook import DiscordWebhook, DiscordEmbed
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

# CONFIG VARIABLES
DISCORD_BOT = os.getenv("DISCORD_BOT")
TEAM = "Juventus"
BASE_URL = "https://www.thesportsdb.com/api/v1/json/123/"
TEAM_ID = 133676  # Juventus ID in TheSportsDB
TIMEZONE = "Europe/Brussels"

# Global variables
next_match_info = None
daily_reminder_sent_for_date = None
final_score_sent_for_id = None

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
            else:
                print("No match details found for final score.")

    except Exception as e:
        print(f"Error fetching final score: {e}")

    return False

# main loop of background task
def main_loop():
    global next_match_info, final_score_sent_for_id

    while True:
        now_utc = datetime.now(timezone.utc)

        #--- LOGIC FOR GAME MODE ---
        if next_match_info:
            datetime_str = f"{next_match_info['dateEvent']} {next_match_info['strTime']}"
            match_time_utc = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            match_start_time = match_time_utc
            match_end_time = match_start_time + timedelta(minutes=130)
                
            # Has the match ended?
            if now_utc > match_end_time and next_match_info.get('idEvent') != final_score_sent_for_id:
                print("Match has ended. Trying to send the final score. Match ID:", next_match_info.get('idEvent'))

                juventus_match_id = next_match_info.get('idEvent')
                succes = send_final_score(juventus_match_id)

                # mark that final score has been sent for this match
                if succes:
                    print("Final score sent. Back to waiting for next match.")
                    final_score_sent_for_id = juventus_match_id
                    # reset next_match_info to look for new match
                    next_match_info = None
                else:
                    print("Final score could not be sent. Will retry later.")

                time.sleep(15 * 60)  # Wait 15 minutes before next check
                continue

        if not next_match_info:

            #--- LOGIC FOR WAITING FOR NEXT MATCH ---
            print("WAIT MODUS ACTIVE. Checking for next match...")

            url = f"{BASE_URL}eventsnext.php?id={TEAM_ID}"

            try:
                response = requests.get(url).json()

                if response.get('events'):
                    match = response['events'][0]

                    # create a match_info dictionary similar to the previous structure
                    next_match_info = match

                    print(f"Next match found: {match['strHomeTeam']} vs {match['strAwayTeam']} on {match['dateEvent']}")

                    match_time_utc = datetime.strptime(f"{match['dateEvent']} {match['strTime']}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

                    # Send daily reminder if the match is tomorrow
                    if now_utc.date() == (match_time_utc.date() - timedelta(days=1)):
                        send_daily_reminder(next_match_info)
                    else:
                        print("No reminder sent today.")
                else:
                    print("No upcoming matches found.")
                    next_match_info = None

            except Exception as e:
                print(f"Error fetching next match: {e}")

        # no need for frequent checks when waiting for next match
        print("Sleeping for 15 seconds before next check...")
        time.sleep(4 * 60 * 60)  # Check every 4 hours



if __name__ == "__main__":
    if not DISCORD_BOT or not TEAM_ID:
        print("Error: DISCORD_BOT and API_KEY must be set in the environment variables.")
    else:
        main_loop()