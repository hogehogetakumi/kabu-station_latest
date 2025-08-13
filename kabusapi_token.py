import urllib.request
import json
import pprint
import os
from const import api_key, base_url

obj = { 'APIPassword': api_key}
json_data = json.dumps(obj).encode('utf8')
url = f'{base_url}token'

req = urllib.request.Request(url, json_data, method='POST')
req.add_header('Content-Type', 'application/json')

def get_token():
    try:
        with urllib.request.urlopen(req) as res:
            print(res.status, res.reason)
            for header in res.getheaders():
                print(header)
            print()
            content = json.loads(res.read())
            pprint.pprint(content)
            return content['Token']
    except urllib.error.HTTPError as e:
        print(e)
        content = json.loads(e.read())
        pprint.pprint(content)
    except Exception as e:
        print(e)
