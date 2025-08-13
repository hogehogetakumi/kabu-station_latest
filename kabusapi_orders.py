import urllib.request
import json
import pprint
from kabusapi_token import get_token
from const import base_url, order_params

def get_orders(params=None):
    if params is None:
        params = { 'product': 0 }  # デフォルトで全ての注文を取得
    url = f'{base_url}orders'
    req = urllib.request.Request('{}?{}'.format(url, urllib.parse.urlencode(params)), method='GET')
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
            print("Orders retrieved successfully.", content)
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
    response = get_orders(params=order_params)
    print(response, 'thfsdfkjsd')