import urllib.request
import json
import pprint
from kabusapi_token import get_token
from const import base_url, order_params


def get_positions(params=None):
    url = f'{base_url}positions'
    if params is None:
        params = { 'product': 0 }  # デフォルトで全てのポジションを取得
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
    params = {
        'product': "1",
        'symbol': '260A',
        'side': '2',
        'addinfo': 'true'
    }
    response = get_positions(params)
    print(response)