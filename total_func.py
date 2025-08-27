from kabusapi_orders import get_orders
from const import sample_order_history, buy_order_params, sell_order_params, total_limit
from datetime import datetime
from typing import List, Dict, Any

def calc_total_trade_value(buy_orders: list[dict], sell_orders: list[dict]) -> tuple[float, float]:
    """
    約定詳細（RecType=8）だけを集計して取引金額(Price×Qty)の合計を返す。
    - Stateは判定に使用しない（約定可否はRecType=8で判定）
    """
    def _sum_exec_notional(orders: list[dict]) -> float:
        total = 0.0
        for order in orders:
            for d in order.get("Details") or []:
                # 約定のみ（型混在に備えてintで判定）
                if int(d.get("RecType") or -1) == 8:
                    qty = float(d.get("Qty") or 0.0)
                    if qty <= 0:
                        continue
                    # 実約定価格を優先。無い/0.0なら注文Priceをフォールバック
                    p = d.get("Price")
                    price = float(p) if p is not None and p != "" else float(order.get("Price") or 0.0)
                    total += price * qty
        return total

    total_buy = _sum_exec_notional(buy_orders)
    total_sell = _sum_exec_notional(sell_orders)

    print(f"Total Buy: {total_buy:,.0f} 円, Total Sell: {total_sell:,.0f} 円")
    return total_buy, total_sell

def is_within_limit(limit: float = 1_000_000.0) -> bool:
    """
    当日の約定合計金額が limit 円以下かを判定し、結果を表示して True/False を返す
    """
    # 本番環境では get_orders()、テスト時は sample_order_history を使用
    try:
        buy_orders = get_orders(buy_order_params)  
        sell_orders = get_orders(sell_order_params)  
    except Exception:
        orders = sample_order_history

    total = calc_total_trade_value(buy_orders, sell_orders)
    print(f"当日の約定合計金額：{total:,.0f} 円")
    if total <= limit:
        print("✅ 1,000,000円以内です")
        return False
    else:
        print("⚠️ 1,000,000円を超えています")
        return True

def confirm_state() -> bool:
    """
    未完了の注文（終了=5以外）で、残数量>0のものが1件でもあれば True を返す。
    未完了が無ければ False。
    """
    try:
        buy_orders = get_orders(buy_order_params)
        sell_orders = get_orders(sell_order_params)
        orders = buy_orders + sell_orders
    except Exception:
        orders = sample_order_history

    if not orders:
        return False

    for o in orders:
        state = int(o.get("OrderState", o.get("State", 5)))  # OrderState優先
        order_qty = float(o.get("OrderQty") or 0)
        cum_qty   = float(o.get("CumQty") or 0)
        leaves    = float(o.get("LeavesQty") or (order_qty - cum_qty))

        # 1,2,3,4 = 未完了 / 5 = 終了（全約定・取消・失効・期限切れ・エラー）
        if state in (1, 2, 3, 4) and leaves > 0:
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
        buy_orders = get_orders(buy_order_params)
        sell_orders = get_orders(sell_order_params)
        orders = buy_orders + sell_orders
    except Exception:
        orders = sample_order_history
        buy_orders = orders
        sell_orders = orders

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
    total_buy, total_sell = calc_total_trade_value(buy_orders, sell_orders)
    total = total_buy + total_sell
    print(f"\n当日の約定合計金額：{total:,.0f} 円")

    # --- 4) 閾値チェック ---
    if total <= limit:
        print(f"✅ {limit:,.0f}円以内です")
        return False
    else:
        print(f"⚠️ {limit:,.0f}円を超えています")
        return True

def get_total(puls):
    try:
        buy_orders = get_orders(buy_order_params)
        sell_orders = get_orders(sell_order_params)
    except Exception:
        orders = sample_order_history
        buy_orders = orders
        sell_orders = orders

    if not buy_orders and not sell_orders:
        print("No orders found. Treating total as 0.")
        total = 0.0
    else:
        # --- 2) state 1 or 2 の注文詳細をすべて出力 ---
        print("=== State 1,2 の注文詳細 ===")
        for order in (buy_orders + sell_orders):
            for d in order.get("Details", []):
                state = d.get("State", 0)
                if state in (1, 2):
                    print(
                        f"Order ID: {d.get('ID')}, "
                        f"State: {state}, "
                        f"Price: {d.get('Price', 0.0):,.2f}, "
                        f"Qty: {d.get('Qty', 0.0):,.2f}"
                    )
        total_buy, total_sell = calc_total_trade_value(buy_orders, sell_orders)
        total = total_buy + total_sell

    combined = total + float(puls or 0)
    print(f"当日の約定合計金額 + puls = {combined:,.0f} 円 (total={total:,.0f}, puls={puls})")
    if combined <= 1_000_000:
        print(f"✅ {combined:,.0f}円は閾値 1,000,000 円以内です。戻り値: True")
        return True
    else:
        print(f"⚠️ {combined:,.0f}円は閾値 1,000,000 円を超えています。戻り値: False")
        return False

if __name__ == "__main__":
    print(calc_total_trade_value(buy_order_params, sell_order_params))
