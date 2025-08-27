import urllib.request
import json
import pprint
from kabusapi_token import get_token
from const import api_key, base_url, target_symbol_no_exchange

def get_board_info(symbol='260A@1'):
    url = f'{base_url}/board/{symbol}'
    req = urllib.request.Request(url, method='GET')
    req.add_header('Content-Type', 'application/json')
    token = get_token()
    req.add_header('X-API-KEY', token)

    try:
        with urllib.request.urlopen(req) as res:
            print(res.status, res.reason)
            for header in res.getheaders():
                print(header)
            print()
            content = json.loads(res.read())
            pprint.pprint(content)
            return content
    except urllib.error.HTTPError as e:
        print(e)
        content = json.loads(e.read())
        pprint.pprint(content)
        return content
    except Exception as e:
        print(e)
        return None

if __name__ == "__main__":
    response = get_board_info()
    print(response['CurrentPrice'], 'thfsdfkjsd')