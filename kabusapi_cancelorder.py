# kabusapi_cancelorder.py
import urllib.request
import urllib.error
import json
import pprint
from kabusapi_token import get_token
from const import base_url

def cancel_order(order_id: str):
    """
    kabuステーションAPI: 注文取消（/cancelorder）
    - 引数: order_id ... 取消対象の注文ID（例: "20200709A02N04712032"）
    - 戻り値: 成功/失敗いずれもAPI応答(dict)を返す。例外時は None を返す。
    """
    # payload は OrderId が正。必要なら下の OrderID を併送して互換性を担保してください。
    payload = {
        "OrderId": order_id,
        # "OrderID": order_id,  # ← 互換が必要なら有効化
    }
    json_data = json.dumps(payload).encode("utf-8")

    url = f"{base_url}cancelorder"  # base_url 末尾にスラッシュが無い前提（他ファイルと同様）
    req = urllib.request.Request(url, data=json_data, method="PUT")
    req.add_header("Content-Type", "application/json")

    # kabusapi_board/kabusapi_sendorder_cash_buy と同様、都度トークン取得してヘッダ付与
    token = get_token()
    req.add_header("X-API-KEY", token)

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
        try:
            content = json.loads(e.read())
            pprint.pprint(content)
            return content
        except Exception:
            return None
    except Exception as e:
        print(e)
        return None

# 例: 単体テスト
if __name__ == "__main__":
    # 実注文IDに置き換えて試してください
    resp = cancel_order("20200709A02N04712032")
    print("cancel_order response:", resp)
