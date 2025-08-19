import urllib.request
import json
import pprint
from kabusapi_token import get_token
from const import api_key, base_url, sell_obj

def send_cash_sell_order(sell_obj, want_sell_price=None):
    if want_sell_price is not None:
        sell_obj["Price"] = want_sell_price
    json_data = json.dumps(sell_obj).encode('utf-8')
    print('--------', json_data)
    url = f'{base_url}sendorder'
    req = urllib.request.Request(url, json_data, method='POST')
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
    response = send_cash_sell_order(sell_obj)
    print(response, 'thfsdfkjsd')