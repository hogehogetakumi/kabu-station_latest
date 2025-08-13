from kabusapi_orders import get_orders
from const import sample_order_history, order_params
from datetime import datetime
from typing import List, Dict, Any

def calc_total_trade_value(orders: list[dict]) -> float:
    """
    約定詳細を走査して取引金額(Price × Qty)の合計を返す
    - RecType=1 (約定) かつ State=3 (処理済) のみを集計
    """
    total = 0.0
    for order in orders:
        for d in order.get("Details", []):
            if d.get("RecType") == 1 and d.get("State") == 3:
                price = d.get("Price") or 0.0
                qty   = d.get("Qty")   or 0.0
                total += price * qty
    return total

def is_within_limit(limit: float = 1_000_000.0) -> bool:
    """
    当日の約定合計金額が limit 円以下かを判定し、結果を表示して True/False を返す
    """
    # 本番環境では get_orders()、テスト時は sample_order_history を使用
    try:
        orders = get_orders(order_params)  
    except Exception:
        orders = sample_order_history

    total = calc_total_trade_value(orders)
    print(f"当日の約定合計金額：{total:,.0f} 円")
    if total <= limit:
        print("✅ 1,000,000円以内です")
        return False
    else:
        print("⚠️ 1,000,000円を超えています")
        return True

def confirm_state() -> bool:
    """
    state:1, 2 の注文の約定金額を計算して返す
    """
    total = 0.0
    orders = get_orders(order_params)
    if not orders:
        print("No orders found.")   
        pass
    
    for order in orders:
        for d in order.get("Details", []):
            if d.get("State") == 1 or d.get("State") == 2:
                print(f"Order ID: {d.get('ID')}, State: {d.get('State')}, Price: {d.get('Price')}, Qty: {d.get('Qty')}")
                return True
    return False



def check_trades_and_limit(
    limit: float = 1_000_000.0
) -> bool:
    """
    1) state が 1 or 2 の注文詳細を出力
    2) 当日の約定合計金額を計算・表示
    3) limit 円を超えていれば True, 以下なら False を返す
    """
    # --- 1) 注文取得 ---
    try:
        orders: List[Dict[str, Any]] = get_orders(order_params)
    except Exception:
        orders = sample_order_history

    if not orders:
        print("No orders found.")
        return False

    # --- 2) state 1 or 2 の詳細をすべて出力 ---
    print("=== State 1,2 の注文詳細 ===")
    for order in orders:
        for d in order.get("Details", []):
            state = d.get("State", 0)
            if state in (1, 2):
                print(
                    f"Order ID: {d.get('ID')}, "
                    f"State: {state}, "
                    f"Price: {d.get('Price', 0.0):,.2f}, "
                    f"Qty: {d.get('Qty', 0.0):,.2f}"
                )

    # --- 3) 総約定金額を計算・表示 ---
    total: float = calc_total_trade_value(orders)
    print(f"\n当日の約定合計金額：{total:,.0f} 円")

    # --- 4) 閾値チェック ---
    if total <= limit:
        print(f"✅ {limit:,.0f}円以内です")
        return False
    else:
        print(f"⚠️ {limit:,.0f}円を超えています")
        return True

if __name__ == "__main__":
    print(check_trades_and_limit())
