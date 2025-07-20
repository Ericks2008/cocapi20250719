# ./api/player/routes.py
from flask import request, jsonify, current_app
import json
from . import player_bp # Import the blueprint instance
from ...utils.db import get_db, close_db # Import common function
import sqlite3 # Import for specific DB exceptions
from datetime import datetime, timedelta
import traceback 
import copy

progressItem = {'warStars':1,
    'attackWins':1,
    'donations':1,
    'donationsReceived':1}


@player_bp.route('/get_player_info/<player_tag>', defaults={'from_date': None}, methods=['GET'])
@player_bp.route('/get_player_info/<player_tag>/<string:from_date>', methods=['GET'])
def get_player_info(player_tag, from_date:None):
    conn = None # Initialize conn to None
    if from_date:
        from_start_date = from_date + ' 23:59:59'
    else:
        from_start_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_range = 90
 
    try: 
        conn = get_db()
        sql = "SELECT cocdata, dataTime  FROM player where tag = ? and dataTime <= ?  ORDER BY dataTime DESC Limit ?"
        data = conn.execute(sql, (player_tag, from_start_date, date_range,)).fetchall()
        if not data:
            current_app.logger.warning(f"get_player_info: {player_tag} no data") 
            return jsonify({'error': f"no player data found for tag: {player_tag}"}),404
        player_data = json.loads(data[0]['cocdata'])
        player_data['DateRange'] = date_range
        player_data['playerprogress'] = {}
        player_data['playerprogress']['history'] = []
        history_date = datetime.strptime(from_start_date, '%Y-%m-%d %H:%M:%S')

        for x in range (date_range):
            d = history_date - timedelta(days=x)
            player_data['playerprogress']['history'].append(d.strftime("%Y-%m-%d"))

        # sql = 'SELECT cocdata, dataTime FROM player where tag = ? and dataTime < ? ORDER BY dataTime DESC Limit ?'
        # data = conn.execute(sql, (player_tag, from_start_date, date_range,)).fetchall()
        working = {}
        for data_row in data: 
            try:
                player_data_row = json.loads(data_row['cocdata'])
                data_time_row = data_row['dataTime'][:10]
                player_data['playerprogress'][data_time_row] = {}
                for item in progressItem:
                    if item in working:
                        player_data['playerprogress'][data_time_row][item] = working[item] - player_data_row[item]
                    else:
                        player_data['playerprogress'][data_time_row][item] = player_data_row[item]
                    working[item] = player_data_row[item]
                for achievement in player_data_row.get('achievements', []):
                    if achievement['name'] in working:
                        player_data['playerprogress'][data_time_row][achievement['name']] = working[achievement['name']] - achievement['value']
                    else:
                        player_data['playerprogress'][data_time_row][achievement['name']] = achievement['value']
                    working[achievement['name']] = achievement['value']
            except json.JSONDecodeError as e:
                current_app.logger.warning(f"get_player_info: Failed to decode cocdata for player {player_tag} at {data_row['dataTime']}: {e}")
                continue # Skip this malformed record and continue with others
        return jsonify(player_data)
    except Exception as e:
        current_app.logger.error(f"An unexpected error occurred in get_player_info for {player_tag}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "An internal server error occurred."}), 500
    finally:
        close_db()




@player_bp.route('/get_player_progress_data/<player_tag>', methods=['GET'])
def get_player_progress_data(player_tag):
    date_range = 360
    conn = get_db()

    sql = "SELECT cocdata, dataTime FROM player where tag = ? ORDER BY dataTime DESC limit ?"
    data = conn.execute(sql, (player_tag, date_range + 1,)).fetchall()

    if not data:
        current_app.logger.info(f"get_player_progress_data: {player_tag} no data") 
        return jsonify({'error': f"no player data found for tag: {player_tag}"}), 404

    try:
        player_data = json.loads(data[0]['cocdata'])
    except Exception as e:
        current_app.logger.error(f"An unexpected error occurred in json loads for {player_tag}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "An internal server error occurred."}), 500

    player_data['upgradeprogress_list'] = []

    parsed_data = []
    for row in reversed(data):
        try:
            parsed_data.append({
                'cocdata': json.loads(row['cocdata']),
                'dataTime': row['dataTime'][:10]
            })
        except json.JSONDecodeError as e:
            current_app.logger.warning(f"Skipping malformed data for {player_tag} at {row['dataTime']}: {e}")
            continue

    if len(parsed_data) < 2:
        current_app.logger.info(f"get_player_progress_data: Not enough historical data for {player_tag} to track progress.")
        return jsonify(player_data)

    previous_state = {
        'home': {'townHallLevel': parsed_data[0]['cocdata'].get('townHallLevel', 0)},
        'builderBase': {'builderHallLevel': parsed_data[0]['cocdata'].get('builderHallLevel', 0)}
    }
    if 'townHallWeaponLevel' in parsed_data[0]['cocdata']:
        previous_state['home']['townHallWeaponLevel'] = parsed_data[0]['cocdata']['townHallWeaponLevel']

    for item_type in ['spells', 'troops', 'heroes']:
        for item in parsed_data[0]['cocdata'].get(item_type, []):
            if item.get('name') and item['name'][:5] != 'Super':
                previous_state[item.get('village', 'home')][item['name']] = item.get('level', 0)

    for i in range(1, len(parsed_data)):
        current_row = parsed_data[i]
        current_data = current_row['cocdata']
        current_date_str = current_row['dataTime']

        upgrade_found = False
        daily_upgrades = {'date': current_date_str, 'home': {}, 'builderBase': {}}

        current_th_level = current_data.get('townHallLevel', 0)
        if current_th_level != previous_state['home']['townHallLevel']:
            daily_upgrades['home']['townHallLevel'] = current_th_level
            upgrade_found = True
        previous_state['home']['townHallLevel'] = current_th_level

        current_bh_level = current_data.get('builderHallLevel', 0)
        if current_bh_level != previous_state['builderBase']['builderHallLevel']:
            daily_upgrades['builderBase']['builderHallLevel'] = current_bh_level
            upgrade_found = True
        previous_state['builderBase']['builderHallLevel'] = current_bh_level

        current_thw_level = current_data.get('townHallWeaponLevel')
        if current_thw_level is not None:
            if 'townHallWeaponLevel' in previous_state['home']:
                if current_thw_level != previous_state['home']['townHallWeaponLevel']:
                    daily_upgrades['home']['townHallWeaponLevel'] = current_thw_level
                    upgrade_found = True
            else:
                daily_upgrades['home']['townHallWeaponLevel'] = current_thw_level
                upgrade_found = True
            previous_state['home']['townHallWeaponLevel'] = current_thw_level
        
        for item_type in ['spells', 'troops', 'heroes']:
            for current_item in current_data.get(item_type, []):
                item_name = current_item.get('name')
                item_village = current_item.get('village', 'home')
                item_level = current_item.get('level', 0)

                if item_name and item_name[:5] != 'Super':
                    prev_level = previous_state[item_village].get(item_name, 0)

                    if item_level != prev_level:
                        daily_upgrades[item_village][item_name] = item_level
                        upgrade_found = True
                    previous_state[item_village][item_name] = item_level

        if upgrade_found:
            final_entry = {'date': daily_upgrades['date']}
            if daily_upgrades['home']:
                final_entry['home'] = daily_upgrades['home']
            if daily_upgrades['builderBase']:
                final_entry['builderBase'] = daily_upgrades['builderBase']
            player_data['upgradeprogress_list'].append(final_entry)

    player_data['upgradeprogress_list'].sort(key=lambda x: x['date'], reverse=True)
    player_data['upgradeprogress'] = { entry['date']: {k:v for k,v in entry.items() if k != 'date'} 
                                      for entry in player_data['upgradeprogress_list']}
    del player_data['upgradeprogress_list']

    close_db()
    return jsonify(player_data)


