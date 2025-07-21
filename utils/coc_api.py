# app/utils/coc_api.py
import urllib.request
import urllib.error
import json
import traceback
from flask import current_app 

def fetch_coc_api_data(endpoint: str, data_type: str, tag_value: str):
    data = None
    status_code = 200
    try:
        current_app.logger.info (f"Attempting to fetch {data_type} {tag_value}")
        current_app.logger.info (f"url : {endpoint}")

        req = urllib.request.Request(endpoint)
        req.add_header('Accept', 'application/json')

        APIKEY = current_app.config.get('APIKEY')
        # current_app.logger.info(f"APIKEY: {APIKEY}")
        req.add_header('Authorization', "Bearer " + APIKEY)

        #r = urllib.request.urlopen(req)
        #data = r.read()
        # current_app.logger.info(f"api return data: {data}")
        #status_code = r.getcode()
        # current_app.logger.info(f"api return code: {status_code}")

        with urllib.request.urlopen(req) as r:
            data = r.read()
            status_code = r.getcode()

        json.loads(data)

        return data, status_code

    except urllib.error.HTTPError as e:
        error_msg = f"CoC API HTTP Error fetching {data_type} {tag_value} : {e.code}"
        current_app.logger.warning(error_msg)
        try:
            error_details = e.read().decode('utf-8')
            current_app.logger.warning(f"CoC API Error Response Body: {error_details}")
            return error_details, e.code
        except Exception as read_e:
            current_app.logger.warning(f"Could not read error body from CoC API: {read_e}")
            return {'error': f"Failed to fetch {data_type} {tag_value}. CoC API returned status {read_e.code}"}, read_e.code

    except urllib.error.URLError as e:
        error_msg = f"CoC API Network/URL Error fetching {data_type} {tag_value}"
        current_app.logger.warning(error_msg)
        return {'error': f"Network error when connecting to CoC API: {e.reason}"}, 503

    except json.JSONDecodeError as e:
        current_app.logger.error(f"CoC API JSON decoding error for {data_type} {tag_value}: {e}")
        return {'error': f"CoC API returned malformed data for {data_type} {tag_value}"}, e.code

    except Exception as e:
        error_msg = f"CoC API unexpected error occurred while fetching {data_type} {tag_value}"
        current_app.logger.critical (f"{error_msg}\n{traceback.format_exc()}")
        return {'error': 'An unexpected internal server error occured.'}, 500



