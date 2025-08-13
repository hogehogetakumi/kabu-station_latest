import urllib.request
import json
import pprint
from kabusapi_token import get_token
from const import api_key, base_url, buy_obj

def send_cash_buy_order(buy_obj, want_buy_price=None):
    json_data = json.dumps(buy_obj).encode('utf-8')
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

# 例: 関数を呼び出す場合
if __name__ == "__main__":
    response = send_cash_buy_order(buy_obj)
    print(response, 'thfsdfkjsd')