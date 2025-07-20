# ./api/cwl/routes.py

from flask import request, jsonify, current_app
import copy
from datetime import datetime
import json
import traceback
import urllib.parse

from . import cwl_bp # Import the blueprint instance
from ...utils.coc_api import fetch_coc_api_data
from ...utils.db import get_db, close_db # Import common function

@cwl_bp.route('/get_cwl_list/<clan_tag>', methods=['GET'])
def get_cwl_list(clan_tag):
    try:
        conn = get_db()
        # Example: fetch player data (use parameterized queries!)
        clan_data_row = conn.execute("SELECT cocdata FROM clan WHERE tag = ? ORDER BY dataTime DESC", (clan_tag,)).fetchone()
        if not clan_data_row:
            current_app.logger.warning(f'get_cwl_list: {clan_tag} no data')
            return jsonify({'error': f'No clan data found for tag: {clan_tag}'}), 404
        clandata = json.loads(clan_data_row['cocdata'])
        clandata['CWLlist'] = []
        cwl_entries = conn.execute("SELECT cocdata FROM clanwarleague WHERE tag = ? ORDER BY dataTime DESC limit 6", (clan_tag,)).fetchall()
        for cwl_entry in cwl_entries:
            try:
                cwl_cocdata = json.loads(cwl_entry['cocdata'])
                if 'season' in cwl_cocdata:
                    clandata['CWLlist'].append(cwl_cocdata['season'])
            except json.JSONDecodeError as e:
                current_app.logger.warning(f"Error decoding CWL cocdata for tag {clan_tag}: {e}")
        close_db()
        return jsonify(clandata)
    except Exception as e:
        current_app.logger.warning(f"An unexpected error occurred in CWLlist for {clan_tag}: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500


@cwl_bp.route('/get_cwl_season_data/<clan_tag>/<req_season>', methods=['GET'])
@cwl_bp.route('/get_cwl_season_data/<clan_tag>', defaults={'req_season': None},  methods=['GET'])
def db_clanwarleague(clan_tag, req_season: str = None):
    cwl_data, status_code = _get_cwl_data_from_db(clan_tag, req_season)
    return jsonify(cwl_data), status_code

def _get_cwl_data_from_db(clan_tag: str, req_season: str = None):
    conn = get_db()
    cwl_data = None
    status_code = 500

    try:
        if req_season:
            sql = 'SELECT cocdata FROM clanwarleague where clanSeason = ? limit 1'
            db_data = conn.execute(sql, (clan_tag + req_season,)).fetchone()
        else:
            sql = 'SELECT cocdata FROM clanwarleague where tag = ? ORDER BY clanSeason DESC limit 1'
            db_data = conn.execute(sql, (clan_tag,)).fetchone()

        if db_data:
            try:
                cwl_data = json.loads(bytes(db_data['cocdata']).decode('utf-8'))
                current_app.logger.info(f"CWL group data for clan {clan_tag} season {req_season or 'latest'} loaded from DB.")
            except json.JSONDecodeError as e:
                error_msg = f"JSON decode error for cached CWL group data {clan_tag} season: {req_season or 'latest'} : {e}\n"
                error_msg += f"{traceback.format_exc()}"
                current_app.logger.error(error_msg)
                cwl_data = None
            except Exception as e:
                error_msg = f"Unexpected error decoding cached CWL group data ({clan_tag}, {req_season or 'latest'}): {e}\n"
                error_msg += f"{traceback.format_exc()}"
                current_app.logger.error(error_msg)
                cwl_data = None
        else:
            current_app.logger.warning(f"get_cwl_data_from_db :  clan {clan_tag} sesaon {req_season} no cwl data")
            cwl_data = None

        # clandata = read_clan_data(ClanTag)
        if cwl_data and 'state' in cwl_data:
            sql = 'SELECT * FROM clan where tag = ? ORDER BY dataTime DESC limit 1'
            data = conn.execute(sql, (clan_tag,)).fetchone()
            if data:
                cwl_data['name'] = json.loads(data['cocdata'])
                status_code = 200
            else:
                app.logger.warning (f"get_cwl_season_data {clan_tag} no clan data")
    except Exception as e:
        error_msg = f"Critical error in _get_cwl_data_from_db for {clan_tag}: {e}\n{traceback.format_exc()}"
        current_app.logger.critical(error_msg)
        cwl_data = {'error': 'An internal server error occurred while retrieving CWL group data.'}
    finally:        
        close_db()
    return cwl_data, status_code


@cwl_bp.route('/wartag/<war_tag>/<season>', methods=['GET'])
def db_wartag(war_tag, season):
    war_data, status_code = _get_war_data_cached_or_api(war_tag, season)
    return jsonify(war_data), status_code

def _get_war_data_cached_or_api(war_tag: str, season: str):
    conn = get_db()
    return_data = None
    status_code = 200
    try:
        sql = 'SELECT cocdata, dataTime FROM cwlwarlog where seasonWarTag = ? '
        db_record = conn.execute(sql, (season + war_tag,)).fetchone()

        if db_record:
            try:
                return_data = json.loads(bytes(db_record['cocdata']).decode('utf-8'))
                cache_hit = True
            except json.JSONDecodeError as e:
                error_msg = f"DB cached war_data JSON decode error for seasonWarTag {season + war_tag}: {e}\n"
                error_msg += f"{traceback.format_exc()}"
                current_app.logger.error(error_msg)
                cache_hit = False
            except Exception as e:
                error_msg = f"Unexpected error processing DB cached war_data for seasonWarTag {season + war_tag}: {e}\n"
                error_msg += f"{traceback.format_exc()}" 
                current_app.logger.error(error_msg)
                cache_hit = False
        else:
            cache_hit = False

        if cache_hit:
            data_time = datetime.strptime(db_record['dataTime'], '%Y-%m-%d %H:%M:%S') 
            time_since_last_fetch = (datetime.now() - data_time).total_seconds()
            war_state = return_data.get('state', None)

            if time_since_last_fetch > 300 and \
                war_state not in ['warEnded', 'notInWar']:
                current_app.logger.info(f"Cached data for {war_tag} season {season} is stale or not final; refreshing.")
                return_data, status_code = _fetch_and_store_war_data(war_tag, season) # Fallback to fetching from CoC API
            else:
                error_msg = f"Serving {war_tag} season {season} from cache (state: {war_state}, "
                error_msg += f"age: {int(time_since_last_fetch)}s)."
                current_app.logger.info(error_msg)
                status_code = 200
        else:
            current_app.logger.info(f"No cached data found for {war_tag} season {season}, fetching from CoC API.")
            return_data, satus_code = _fetch_and_store_war_data(war_tag, season) # Fallback to fetching from CoC API

    except Exception as e:
        error_msg = f"Unexpected error in db_wartag for {war_tag} season {season}: {e}\n{traceback.format_exc()}"
        current_app.logger.critical(error_msg)
        return_data = {'error': 'An internal server error occurred while retrieving war data.'}
        status_code = 500

    finally:
        close_db()

    return return_data, status_code

def _fetch_and_store_war_data(war_tag: str, season: str):
    conn = get_db()
    current_season = str(datetime.now())[:7]
    base_api_url = 'https://api.clashofclans.com/v1/clanwarleagues/wars/%23' + urllib.parse.quote(war_tag)
    if current_season == season:
        api_response_data, status_code = fetch_coc_api_data(
                endpoint = base_api_url,
                data_type = 'WarTag',
                tag_value = war_tag
                )
        if status_code == 200:
            sql = 'INSERT OR REPLACE INTO cwlwarlog (seasonWartag, wartag, cocdata) VALUES (?, ?, ?)'
            conn.execute(sql, (season + war_tag, war_tag, api_response_data))
            conn.commit()
            current_app.logger.info(f"wartag db successfully updated {war_tag} {season}")
        return api_response_data, status_code
    else:
        return jsonify({'error': f"Not current season {season} {war_tag}"}), 500
         
 
@cwl_bp.route('/summary/<clan_tag>/<season>', methods=['GET'])
def cwl_summary(clan_tag: str, season: str):
    cwl_data, cwl_status_code = _get_cwl_data_from_db(clan_tag, season)
    #data, status = db_clanwarleague(clan_tag, season)
    #cwl_data = json.loads(data.get_data().decode("utf-8"))


    if cwl_status_code != 200 or 'error' in cwl_data or 'rounds' not in cwl_data:
        current_app.logger.error(f"Failed to get base CWL data for summary: {cwl_data.get('error', 'Unknown error')}")
        return jsonify(cwl_data), cwl_status_code

    # Add 'day' to each round for easier iteration in template
    for i, round_detail in enumerate(cwl_data.get('rounds', [])):
        round_detail['day'] = i + 1

    clan_list = {}
    # Initialize 'attack' structure once for deepcopy
    initial_attack_structure = {str(i): {} for i in range(1, len(cwl_data.get('rounds', [])) + 1)}

    for clan in cwl_data.get('clans', []):
        memberlist = {}
        for member in clan.get('members', []):
            member_copy = copy.deepcopy(member)
            member_copy['attack'] = copy.deepcopy(initial_attack_structure)
            memberlist[member['tag']] = member_copy

        clan_list[clan['tag']] = {
            'name': clan['name'],
            'memberlist': memberlist
        }

    # Populate attack data from individual war tags into clan_list
    for round_detail in cwl_data.get('rounds', []):
        day = round_detail['day']
        for wartag_full in round_detail.get('warTags', []):
            if wartag_full == "#0": # Skip dummy war tags
                continue

            # Call the internal helper function to get war data
            war_data, war_status_code = _get_war_data_cached_or_api(wartag_full[1:], cwl_data['season'])

            if war_status_code == 200 and war_data:
                # Ensure the war_data has expected keys before accessing
                clan_tag_in_war = war_data.get('clan', {}).get('tag')
                opponent_tag_in_war = war_data.get('opponent', {}).get('tag')

                if clan_tag_in_war and clan_tag_in_war in clan_list:
                    current_clan_memberlist = clan_list[clan_tag_in_war]['memberlist']
                    for member in war_data.get('clan', {}).get('members', []):
                        if member['tag'] in current_clan_memberlist:
                            # copy each clan member attack detail from wartag into clan_list
                            # clan_list[war_data['clan']['tag']]['memberlist'][war_data['clan']['members']['tag']]['attack'][day] = war_data['clan']['members']
                            current_clan_memberlist[member['tag']]['attack'][str(day)] = copy.deepcopy(member)
                        else:
                            error_msg = f"Member {member['tag']} found in war {wartag_full} "
                            error_msg += f"but not in main clanlist for {clan_tag_in_war}."
                            current_app.logger.warning(error_msg)

                if opponent_tag_in_war and opponent_tag_in_war in clan_list:
                    current_opponent_memberlist = clan_list[opponent_tag_in_war]['memberlist']
                    for member in war_data.get('opponent', {}).get('members', []):
                        if member['tag'] in current_opponent_memberlist:
                            # copy each opponent member attack detail from wartag into clan_list
                            # clan_list[war_data['opponent']['tag']]['memberlist'][war_data['opponent']['members']['tag']]['attack'][day] = war_data['opponent']['members']
                            current_opponent_memberlist[member['tag']]['attack'][str(day)] = copy.deepcopy(member)
                        else:
                            error_msg = f"Member {member['tag']} found in war {wartag_full} "
                            error_msg += f"but not in main clanlist for {opponent_tag_in_war}."
                            current_app.logger.warning(error_msg)
            else:
                error_msg = f"Failed to get war data for {wartag_full} in season {cwl_data['season']}: "
                error_msg += f"Status {war_status_code}, Error: {war_data.get('error', 'N/A')}"
                current_app.logger.warning(error_msg)

    # Work out each member's mapPosition sequence for sorting
    for clantag_in_list, c_data in clan_list.items():

        memberseq = {}
        last_position = len(c_data['memberlist']) + 1

        for member_tag, member_data in c_data['memberlist'].items():

            member_position = max(
                (int(a.get('mapPosition', 0)) for k, a in member_data['attack'].items()),
                default=0  # safe fallback if empty
            )

            if member_position == 0:
                member_position = last_position
                last_position += 1

            member_data['mapPosition'] = member_position
            memberseq[member_position] = member_tag

        c_data['sortedMemberSeq'] = [memberseq[k] for k in sorted(memberseq)]

    # Generate clan member performance summary
    clansummary_data = copy.deepcopy(clan_list['#' + clan_tag])
    clansummary_data['tag'] = '#' + clan_tag
    for membertag, member_summary in clansummary_data['memberlist'].items():
        total_star = 0
        attack_count = 0
        total_percentage = 0.0

        for rounds, rounds_data in member_summary['attack'].items():
            if 'mapPosition' in rounds_data:
                attack_count += 1
                if 'attacks' in rounds_data:
                    total_star += int(rounds_data['attacks'][0].get('stars', '0'))
                    total_percentage += float(rounds_data['attacks'][0].get('destructionPercentage', '0.0'))

        member_summary['attackcount'] = attack_count
        member_summary['totalstar'] = total_star
        member_summary['totalpercentage'] = total_percentage

        if attack_count == 0:
            member_summary['averagestar'] = 0.0
            member_summary['averagepercentage'] = 0.0
        else:
            member_summary['averagestar'] = "{:.2f}".format(total_star / attack_count)
            member_summary['averagepercentage'] = "{:.2f}".format(total_percentage / attack_count)

    cwl_data['clanlist'] = clan_list
    cwl_data['clansummary'] = clansummary_data # Assign the correctly calculated summary

    return jsonify(cwl_data), 200 # Always return jsonify and a status code

    
