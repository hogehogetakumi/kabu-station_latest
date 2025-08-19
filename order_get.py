from datetime import datetime
from typing import Optional, Dict, Any, List

def latest_order(orders) -> Optional[Dict[str, Any]]:
    if isinstance(orders, str):
        orders = json.loads(orders)
    if not orders:
        return None
    return max(orders, key=lambda o: datetime.fromisoformat(o["RecvTime"]))

def latest_detail_of_latest_order(orders) -> bool:
    """
    直近の最新注文が「売り(Side=2)で未完了（終了=5以外 & 残数量>0）」なら False、
    それ以外は True を返す。
    """
    o = latest_order(orders)
    if not o:
        return True  # 注文が無い→新規発注OKという方針

    # Side はトップレベルから
    side = o.get("Side")
    if isinstance(side, str):
        try:
            side = int(side)
        except ValueError:
            side = None

    # 注文全体の状態と残数量で“生死”を判断
    state = int(o.get("OrderState", o.get("State", 5)))
    order_qty = float(o.get("OrderQty") or 0)
    cum_qty   = float(o.get("CumQty") or 0)
    leaves    = float(o.get("LeavesQty") or (order_qty - cum_qty))

    # 「最新が売りで未完了なら False」= 新規買いを抑止
    if side == 2 and state in (1, 2, 3, 4) and leaves > 0:
        return False
    return True
