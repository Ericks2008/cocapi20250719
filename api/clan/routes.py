# ./api/clan/routes.py
from flask import request, jsonify, current_app
from datetime import datetime, timedelta, timezone
import json
import sqlite3 # Import for specific DB exceptions
import urllib.request

from . import clan_bp # Import the blueprint instance
from ...utils.db import get_db, close_db # Import common function
from ...utils.coc_api import fetch_coc_api_data

progressItem = {'warStars':1,
    'attackWins':1,
    'donations':1,
    'donationsReceived':1}

@clan_bp.route('/get_clan_details/<clan_tag>', methods=['GET'])
def get_clan_details(clan_tag):
    conn = None # Initialize conn to None
    try: 
        conn = get_db()
        clan_data_row = conn.execute("SELECT cocdata FROM clan where tag = ? ORDER BY dataTime DESC", (clan_tag,)).fetchone()
        if not clan_data_row:
            current_app.logger.warning(f"get_clan_detail: {clan_tag} no data")
            return jsonify({'error': f"No clan data found for tag: {clan_tag}"}), 404
        clandata = json.loads(clan_data_row['cocdata'])
        for member in clandata['memberList']:
            # cocdata = read_player_data(clandata['memberList'][memberIndex]['tag'][1:])
            sql = 'SELECT cocdata FROM player where tag = ? ORDER BY dataTime DESC'
            data2 = conn.execute(sql, (member['tag'][1:],)).fetchone()
            member['attackWins'] = 9999
            member['townHallLevel'] = 9999
            member['warPreference'] = ''
            if data2:
                cocdata = data2['cocdata']
                try:
                    playerdata = json.loads(cocdata)
                    member['attackWins'] = playerdata['attackWins']
                    member['townHallLevel'] = playerdata['townHallLevel']
                    member['warPreference'] = playerdata['warPreference']
                except:
                    current_app.logger.warning(f"get_clan_detail: member tag {member['tag']} data json decode error")
            else:
                current_app.logger.warning(f"get_clan_detail: member tag {member['tag']} no data")
        return jsonify(clandata)
    except Exception as e:
        current_app.logger.warning(f"An unexpected error occurred in get_clan_detail for {clan_tag}: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500
    finally:
        close_db()

@clan_bp.route('/supertroops/<clan_tag>', methods=['GET'])
def get_supertroops_list(clan_tag):
    conn = get_db()
    sql = 'SELECT * FROM clan where tag = ?  ORDER BY dataTime DESC limit 1'
    data = conn.execute(sql, (clan_tag,)).fetchone()
    if not data:
        current_app.logger.warning(f"get_supertroops_list: {clan_tag} no data")
        return jsonify({'error': f"No clan data found for tag: {clan_tag}"}), 404

    try:
        clan_data = json.loads(data['cocdata'])
    except Exception as e:
        current_app.logger.error(f"An unexpected error occurred in json loads for {clan_tag}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "An internal server error occurred."}), 500

    clan_data['activeSuperTroops'] = {}
    for member in clan_data['memberList']:
        sql = 'SELECT * FROM player where tag = ? ORDER BY dataTime DESC limit 1'
        data = conn.execute(sql, (member['tag'][1:],)).fetchone()
        try:
            player_data = json.loads(data['cocdata'])
        except:
            current_app.logger.info(f"get_supertroops_list: player {member['tag']} information missing or error")
            continue # Skip this malformed record and continue with others
        troops_data = {}
        for troop in player_data['troops']:
            if troop['village'] == 'home' and 'superTroopIsActive' in troop:
                if troop['name'] not in clan_data['activeSuperTroops']:
                    clan_data['activeSuperTroops'][troop['name']] = []
                clan_data['activeSuperTroops'][troop['name']].append(player_data['name'])
    close_db()
    return jsonify(clan_data)

    

@clan_bp.route('/troops/<clan_tag>', methods=['GET'])
def get_clan_troops(clan_tag):
    conn = get_db()
    sql = 'SELECT cocdata FROM clan where tag = ? ORDER BY dataTime DESC limit 1'
    data = conn.execute(sql, (clan_tag,)).fetchone()
    if not data:
        current_app.logger.warning(f"get_clan_troops: {clan_tag} no data")
        return jsonify({'error': f"No clan data found for tag: {clan_tag}"}), 404

    try:
        clan_data = json.loads(data['cocdata'])
    except json.JSONDecodeError as e:
        current_app.logger.error(f"An unexpected error occurred in json loads for {clan_tag}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "An internal server error occurred."}), 500

    player_tags_to_fetch = [member['tag'][1:] for member in clan_data['memberList']]
    if not player_tags_to_fetch:
        current_app.logger.info(f"get_clan_troops: Clan {clan_tag} has no members.")
        close_db()
        return jsonify(clan_data)

    placeholders = ', '.join(['?'] * len(player_tags_to_fetch))
    sql_players = f"""
        SELECT p.cocdata, p.tag
        FROM player p
        JOIN (
            SELECT tag, MAX(dataTime) as latest_dataTime
            FROM player
            WHERE tag IN ({placeholders})
            GROUP BY tag
        ) AS latest_data ON p.tag = latest_data.tag AND p.dataTime = latest_data.latest_dataTime;
    """
    all_players_data = conn.execute(sql_players, player_tags_to_fetch).fetchall()

    player_data_map = {}
    for row in all_players_data:
        try:
            player_data_map[row['tag']] = json.loads(row['cocdata'])
        except json.JSONDecodeError as e:
            current_app.logger.warning(f"Skipping malformed player data for tag {row['tag']}: {e}")
            continue
 
    for member in clan_data['memberList']:
        player_tag_cleaned = member['tag'][1:] # Get tag without '#'
        player_data = player_data_map.get(player_tag_cleaned)

        if not player_data:
            current_app.logger.info(f"get_clan_troops: Player {member['tag']} data not found in DB.")
            continue # Skip this member

        member['detail'] = {
            'troopslist': {t['name']: t for t in player_data.get('troops', []) if t.get('village') == "home"},
            'heroeslist': {h['name']: h for h in player_data.get('heroes', [])},
            'heroEquipmentlist': {e['name']: e for e in player_data.get('heroEquipment', [])},
            'spellslist': {s['name']: s for s in player_data.get('spells', [])},
            # Retain other essential player data for the frontend (e.g., townHallLevel)
            'townHallLevel': player_data.get('townHallLevel'),
            # Add any other top-level player info required by the template
        }

    close_db()
    return jsonify(clan_data)


@clan_bp.route('/progress/<clan_tag>', defaults={'achievement': None}, methods=['GET'])
@clan_bp.route('/progress/<clan_tag>/<achievement>', methods=['GET'])
def get_clan_progress_data(clan_tag, achievement:None):
    conn = get_db()
    sql = 'SELECT cocdata FROM clan where tag = ? ORDER BY dataTime DESC limit 1'
    data = conn.execute(sql, (clan_tag,)).fetchone()
    if not data:
        current_app.logger.warning(f"get_clan_progress_data: {clan_tag} no data")
        return jsonify({'error': f"No clan data found for tag: {clan_tag}"}), 404

    try:
        clan_data = json.loads(data['cocdata'])
    except json.JSONDecodeError as e:
        current_app.logger.warning(f"error occurred in json loads for {clan_tag}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "An internal server error occurred."}), 500

    sql = 'SELECT cocdata FROM player where tag = ? ORDER BY dataTime DESC limit 1'
    data = conn.execute(sql, (clan_data['memberList'][0]['tag'][1:],)).fetchone()
    if not data:
        current_app.logger.warning(f"clanprogress : first member no data {clan_data['memberList'][0]['tag'][1:]}")
        return jsonify({'error': 'An internal server error occurred.'}), 500

    try:
        player_data = json.loads(data['cocdata'])
    except json.JSONDecodeError as e:
        current_app.logger.warning(f"error in json loads for member {clan_data['memberList'][0]['tag'][1:]}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "An internal server error occurred."}), 500

    clan_data['achievements'] = player_data['achievements']
    clan_data['clanprogress'] = {'history': []}
    if achievement:
        clan_data['clanprogress']['name'] = achievement
    else:
        clan_data['clanprogress']['name'] = 'attackWins'
        achievement = 'attackWins'
    start_date = datetime.today()
    history_range = 60
    for x in range (history_range):
        d = start_date - timedelta(days=x)
        clan_data['clanprogress']['history'].append(d.strftime("%Y-%m-%d"))
 
    history_range += 1
    for member in clan_data['memberList']:
        working = {}
        member['clanprogress'] = {}

        sql = 'SELECT cocdata, dataTime FROM player where tag = ? ORDER BY dataTime DESC limit ?'
        data = conn.execute(sql, (member['tag'][1:], history_range, )).fetchall() 
        for data_row in data:
            if data_row != "":
                try:
                    member_data = json.loads(data_row['cocdata'])
                except json.JSONDecodeError as e:
                    current_app.logger.warning(f"Skipping malformed player data for tag {member['tag']}: {e}")
                    continue
                if achievement in progressItem:
                    if achievement in working:
                        member['clanprogress'][data_row['dataTime'][:10]] = working[achievement] - member_data[achievement]
                    else:
                        member['clanprogress'][data_row['dataTime'][:10]] = member_data[achievement]
                    working[achievement] = member_data[achievement]
                else:
                    for member_achievement in member_data.get('achievements', []):
                        if member_achievement['name'] == achievement:
                            if achievement in working:
                                member['clanprogress'][data_row['dataTime'][:10]] = working[achievement] - member_achievement['value']
                            else:
                                member['clanprogress'][data_row['dataTime'][:10]] = member_achievement['value']
    close_db()
    return jsonify(clan_data)


@clan_bp.route('/currentwar/<clan_tag>', methods=['GET'])
def get_current_war_detail(clan_tag: str):
    current_app.logger.info(f"involve currentwar {clan_tag} ")
    conn = get_db()
    status_code = 200
    try:
        sql ='SELECT cocdata, dataTime  FROM warlog where tag = ? ORDER BY dataTime DESC limit 1'
        db_data = conn.execute(sql, (clan_tag,)).fetchone()
    
        if db_data:
            cocdata = db_data['cocdata']
            war_data = json.loads(bytes(db_data['cocdata']).decode('utf-8'))
            war_state = war_data.get('state', '')
            if (war_state == 'inWar' and 
                (datetime.now() - datetime.strptime(db_data['dataTime'], '%Y-%m-%d %H:%M:%S')).total_seconds() > 900):
                fetch_from_api = True
            else:
                fetch_from_api = False
        else:
            fetch_from_api = True

        if fetch_from_api:
            base_api_url = 'https://api.clashofclans.com/v1/clans/%23' + urllib.parse.quote(clan_tag) + '/currentwar'
            api_response_data, status_code = fetch_coc_api_data(
                    endpoint = base_api_url,
                    data_type = 'currentwar',
                    tag_value = clan_tag
                    )

            war_data = json.loads(api_response_data)
            if status_code == 200:
                if 'endTime' in war_data:
                    endTime = clan_tag + war_data['endTime'][:8]
                    endTime2 = datetime.strptime(war_data['endTime'][:15], '%Y%m%dT%H%M%S')
                    if (datetime.now() > endTime2):
                        sql = 'INSERT OR REPLACE INTO warlog (endtime, tag, cocdata, dataTime) VALUES (?, ?, ?, ?)'
                        conn.execute(sql, (endTime, clan_tag, api_response_data, endTime2))
                    else:
                        sql = 'INSERT OR REPLACE INTO warlog (endtime, tag, cocdata) VALUES (?, ?, ?)' 
                        conn.execute(sql, (endTime, clan_tag, api_response_data))
                else:
                    conn.execute("INSERT OR REPLACE INTO warlog (endtime, tag, cocdata) VALUES (?, ?, ?)",
                                 (war_data['state'], clan_tag, api_response_data))
                conn.commit()
                if 'clan' in war_data:
                    war_data['clan']['tag'] = '#' + clan_tag
            elif 'error' not in war_data:
                war_data['error'] = f"unexpected error from fetch coc api data call, status {status_code}"
                
            if 'clan' in war_data:
                war_data['clan']['tag'] = '#' + clan_tag
 

        db_data = conn.execute("SELECT cocdata FROM clan where tag = ? ORDER BY dataTime DESC limit 1", (clan_tag,)).fetchone()
        clan_data = json.loads(bytes(db_data['cocdata']).decode('utf-8'))
        war_data['isWarLogPublic'] = clan_data['isWarLogPublic']

    finally:
        close_db()

    return jsonify(war_data), status_code



@clan_bp.route('/warlog/<clan_tag>', methods=['GET'])
def get_clan_war_history(clan_tag: str):
    conn = get_db()
    status_code = 200
    try:
        sql = 'SELECT cocdata, dataTime FROM clanwarlog where tag = ? ORDER BY dataTime DESC limit 1'
        db_data = conn.execute(sql, (clan_tag, )).fetchone()
        if db_data:
            last_update_time = datetime.strptime(db_data['dataTime'], '%Y-%m-%d %H:%M:%S')
            if (datetime.now() - last_update_time).total_seconds() > 43200:
                fetch_from_api = True
            else:
                fetch_from_api = False
        else:
            fetch_from_api = True
        # fetch latest data from api    
        if fetch_from_api:
            base_api_url = 'https://api.clashofclans.com/v1/clans/%23' + urllib.parse.quote(clan_tag) + '/warlog'
            api_response_data, status_code = fetch_coc_api_data(
                    endpoint = base_api_url,
                    data_type = 'clanwarlog',
                    tag_value = clan_tag
                    )
            clan_war_log = json.loads(api_response_data)
        else:
            clan_war_log = json.loads(bytes(db_data['cocdata']).decode('utf-8'))
        # udpate each war detail from database clanwarlog
        clan_war_log['print'] = []
        clan_war_log['warlog'] = {}
        count = 0
        for clan_war in clan_war_log['items']:
            if count < 10:
                if 'opponent' in clan_war and 'name' in clan_war['opponent']:
                    clan_war_log['print'].append(clan_war)
                    sql = 'SELECT cocdata FROM warlog where endTime = ? ORDER BY dataTime DESC limit 1'
                    db_data = conn.execute(sql, (clan_tag + clan_war['endTime'][:8], )).fetchone()
                    if db_data:
                        clan_war_log['warlog'][clan_war['endTime'][:8]] = json.loads(db_data['cocdata'])
                    else:
                        clan_war_log['warlog'][clan_war['endTime'][:8]] =  {'state': 'noData'}
                    count += 1
    finally:
        close_db()
    return jsonify(clan_war_log), status_code

@clan_bp.route('/wardetail/<clan_tag>/<war_date>', methods=['GET'])
def get_wardetail(clan_tag: str, war_date: str):
    conn = get_db()
    war_data = {'state': 'noData'}
    status_code = 200
    try:
        sql = 'SELECT cocdata FROM warlog where endTime = ? ORDER BY dataTime DESC'
        db_data = conn.execute(sql, (clan_tag + war_date, )).fetchone()
        if db_data:
            war_data = json.loads(bytes(db_data['cocdata']).decode('utf-8'))
        sql = 'SELECT cocdata FROM clan where tag = ? ORDER BY dataTime DESC limit 1'
        db_data = conn.execute(sql, (clan_tag,)).fetchone()
        clan_data = json.loads(bytes(db_data['cocdata']).decode('utf-8'))
        war_data['isWarLogPublic'] = clan_data['isWarLogPublic']
    except json.JSONDecodeError as e:
        self.logger.error(f"JSONDecodeError for war detail of {clan_tag} of {war_date} : {e}")
    except Exception as e:
        self.logger.exception(f"Unexpected error during get wardetail call {clan_tag} of {war_date}: {e}")
    finally: 
        close_db()
    return jsonify(war_data), status_code

    
