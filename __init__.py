from flask import Flask, jsonify, render_template, request, make_response
import urllib.request
import json
import sqlite3
import re
from datetime import datetime, timedelta
from ast import literal_eval
import copy
import os
from .utils.logging_config import configure_logging

# app = Flask(__name__)
app = Flask(__name__, instance_relative_config=True)

progressItem = {'warStars':1,
    'attackWins':1,
    'donations':1,
    'donationsReceived':1}

# Determine which config to load (e.g., from environment variable)
env = os.environ.get('FLASK_ENV', 'production')
if env == 'production':
    from .config import ProductionConfig
    app.config.from_object(ProductionConfig)
else: # default to development
    from .config import DevelopmentConfig
    app.config.from_object(DevelopmentConfig)

# --- Now configure logging with the loaded config ---
configure_logging(app)

SECRET_KEY = app.config.get('SECRET_KEY')
APIKEY = app.config.get('APIKEY')
DATABASE_PATH = app.config.get('DATABASE_PATH')

from .api.cwl import cwl_bp
from .api.clan import clan_bp
from .api.player import player_bp
app.register_blueprint(cwl_bp)
app.register_blueprint(clan_bp)
app.register_blueprint(player_bp)

def read_from_coc(urlAddress, dataType, dataTag):
    data = ""
    try:
        print ("call coc to get " + dataType + " " + dataTag)
        req = urllib.request.Request(urlAddress)
        req.add_header('Accept', 'application/json')
        req.add_header('Authorization', "Bearer " + APIKEY)
        r = urllib.request.urlopen(req)
        data = r.read()
        # print (data)
        # data = json.loads(resp)
    except urllib.error.URLError as e:
        print (e)
    try:
        check_data = json.loads(data)
        return data
    except:
        print ("read from coc JSON decoding error")
        return ""
    return data

def get_db_connection():
#    conn = sqlite3.connect('/var/www/flaskhelloworldsite.tk/logs/database.db')
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_db_lib_connection():
    conn = sqlite3.connect('/var/www/flaskhelloworldsite.tk/logs/library.db')
    conn.row_factory = sqlite3.Row
    return conn

def insert_db(db_table, tag, cocdata):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO " + db_table + "(tag, cocdata) VALUES (?, ?)", (tag, cocdata))
    conn.commit()
    conn.close()

@app.route('/cocplayer', methods=['GET', 'POST'])
def cocplayer():
    tr = request.args.get('TimeRange')
    if tr:
        TimeRange = int(tr)
    else:
        TimeRange = 82800
    PlayerTag = request.args.get('PlayerTag')
    try:
        if PlayerTag:
            conn = get_db_connection()
            data = conn.execute("SELECT * FROM player where tag ='" + PlayerTag + "' ORDER BY dataTime DESC").fetchone()
            conn.close()
            if data:
                if (datetime.now() - datetime.strptime(data['dataTime'], '%Y-%m-%d %H:%M:%S')).total_seconds() > TimeRange:
                    cocdata = read_from_coc("https://api.clashofclans.com/v1/players/%23" + urllib.parse.quote(PlayerTag), "player", PlayerTag)
                    data = json.loads(cocdata)
                    insert_db ('player', PlayerTag, cocdata)
                else:
                    cocdata = data['cocdata']
            else:
                cocdata = read_from_coc("https://api.clashofclans.com/v1/players/%23" + urllib.parse.quote(PlayerTag), "player", PlayerTag)
                data = json.loads(cocdata)
                #data = 'dummy data'
                insert_db ('player', PlayerTag, cocdata)
            return cocdata
        else:
            print ('cocplayer : no playertag')
            return ('No PlayerTag')
    except:
        print ('cocplayer : no data from coc')
        return ('No data from coc')

@app.route('/cocclan', methods=['GET', 'POST'])
def cocclan():
    tr = request.args.get('TimeRange')
    if tr:
        TimeRange = int(tr)
    else:
        TimeRange = 82800
    ClanTag = request.args.get('ClanTag')
    try: 
        if ClanTag:
            conn = get_db_connection()
            data = conn.execute("SELECT * FROM clan where tag ='" + ClanTag + "' ORDER BY dataTime DESC").fetchone()
            conn.close()
            if data:
                if (datetime.now() - datetime.strptime(data['dataTime'], '%Y-%m-%d %H:%M:%S')).total_seconds() > TimeRange:
                    cocdata = read_from_coc("https://api.clashofclans.com/v1/clans/%23" + urllib.parse.quote(ClanTag), "clan", ClanTag)
                    data = json.loads(cocdata)
                    insert_db ('clan', ClanTag, cocdata)
                else:
                    cocdata = data['cocdata']
            else:
                cocdata = read_from_coc("https://api.clashofclans.com/v1/clans/%23" + urllib.parse.quote(ClanTag), "clan", ClanTag)
                data = json.loads(cocdata)
                insert_db ('clan', ClanTag, cocdata)
            return cocdata
        else:
            print ('cocclan : no clan tag')
            return 'no clantag'
    except:
        print ('cocclan : no data from coc')
        return 'no data from coc'

def read_from_coccwl(ClanTag):
    cocdata = read_from_coc("https://api.clashofclans.com/v1/clans/%23" + urllib.parse.quote(ClanTag)+ '/currentwar/leaguegroup', "clanwarleague", ClanTag)
    if cocdata == "":
        print ('read_from_coccwl : ' + ClanTag + ' no data')
        return ""
    else:
        # print ('coccwl after read_from_coc')
        try:
            cwldata = json.loads(cocdata)
        except:
            print ("read_from_coccwl json loads error")
            return ""
        # print (cwldata['season'])
        if 'season' in cwldata:
            season = cwldata['season']
            conn = get_db_connection()
            conn.execute("INSERT OR REPLACE INTO clanwarleague (clanSeason, tag, cocdata, season) VALUES (?, ?, ?, ?)", (ClanTag + season, ClanTag, cocdata, season))
            conn.commit()
            conn.close()
            return (cocdata)
        else:
            print ('read_from_coccwl : ' + ClanTag + ' no season')
            return ""
    print ('read_from_coccwl : error ?')
    return ""

@app.route('/coccwl', methods=['GET', 'POST'])
def coccwl():
    ClanTag = request.args.get('ClanTag')
    if ClanTag == "":
        print ('coccwl : no clantag')
        return ('coccwl : no clantag')
    else:
        cocdata = read_from_coccwl(ClanTag)
        return (cocdata)
    print ('coccwl : error?')
    return ('coccwl : error?')


if __name__ == "__main__":
    app.run()


# "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6IjRiZTZiNDNlLThjMTYtNDNhYy04ZWNkLWVmOTdiOGIyMjgxMyIsImlhdCI6MTY0NzgxNDExMCwic3ViIjoiZGV2ZWxvcGVyLzRiZDhiNjA0LWI4MTctNjYyNy0zYzc5LWQ3OGJiODk1MDA1MiIsInNjb3BlcyI6WyJjbGFzaCJdLCJsaW1pdHMiOlt7InRpZXIiOiJkZXZlbG9wZXIvc2lsdmVyIiwidHlwZSI6InRocm90dGxpbmcifSx7ImNpZHJzIjpbIjM0LjcyLjExOC45MyJdLCJ0eXBlIjoiY2xpZW50In1dfQ.6QegOPvpcuqlnE7u_9TOF6FbdZNp5MdYtuNjuWLBGn4fE9UuNWbaijXHoLivppkYcYPNEq53p1h58TDu1BEnxQ"
