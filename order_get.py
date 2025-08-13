import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from const import target_symbol, position_params, sell_obj, buy_obj, order_params_by_id, target_symbol_no_exchange

def latest_order(orders) -> Optional[Dict[str, Any]]:
    """
    RecvTime が最も新しい注文を返す
    """
    if isinstance(orders, str):
        orders = json.loads(orders)

    if not orders:
        return None

    return max(orders, key=lambda o: datetime.fromisoformat(o["RecvTime"]))

def latest_detail_of_latest_order(order) -> Optional[Dict[str, Any]]:
    """
    1. 最新注文を取得
    2. その Details から TransactTime が最大の要素（末端レコード）を返す
    """
    order = latest_order(order)
    if not order:
        return None

    details = order.get("Details", [])
    if not details:
        return None

    latest = max(details, key=lambda d: datetime.fromisoformat(d["TransactTime"]))
    side = latest.get("Side")
    state = latest.get("State")
    # Sideが2かつStateが5ならTrue、Sideが2以外ならTrue
    print(f"-----------0---Latest Order - Side: {side}, State: {state}")
    if side == 2 and state == 5:
        return True
    elif side == 2:
        return False
    else:
        return True
    
# --- 使用例 --------------------------------------------------------------
# latest_detail = latest_detail_of_latest_order(orders_response)
# print(json.dumps(latest_detail, indent=2, ensure_ascii=False))
