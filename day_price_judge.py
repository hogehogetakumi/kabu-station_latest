from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any
from kabusapi_board  import get_board_info

@dataclass
class DecideParams:
    tick: float = 1.0                     # JDIは0.1円刻み
    tp_min_ticks: int = 1                 # 最低利確: +1tick
    tp_max_ticks: int = 3                 # 伸びても +3tick まで
    sl_ticks: int = 1                     # 損切り: -1tick
    wall_abs_qty: int = 300_000           # 「板の壁」とみなす絶対数量
    wall_rel_pct: float = 0.10            # 当日出来高の◯%超も「壁」
    near_low_allow_ticks: int = 3         # 当日安値+0.3円以内のみ買い許容
    min_room_to_resist_ticks: int = 2     # 壁まで最低 +0.2円 の余地が必要

def _tick_floor(p: float, tick: float) -> float:
    return round((int(round(p / tick, 0)) * tick), 1)

def _tick_round(p: float, tick: float) -> float:
    # 0.1刻み丸め
    return float(f"{p:.1f}")

def _prev_tick(p: float, tick: float) -> float:
    return _tick_round(p - tick, tick)

def _find_wall_side(board: Dict[str, Any], side: str, params: DecideParams, total_vol: float) -> Optional[Tuple[float, float]]:
    """
    side='Sell' or 'Buy'
    壁（数量が多い価格）を 1～10 本の板から先頭側で検出して返す (price, qty)。
    絶対数量 or 出来高に対する相対割合のどちらかを満たせば壁と判定。
    """
    threshold = max(params.wall_abs_qty, total_vol * params.wall_rel_pct / 100.0)
    # threshold は「◯株」を想定（TradingVolume が株数ならOK）
    for i in range(1, 11):
        key = f"{side}{i}"
        level = board.get(key)
        if not level:
            continue
        price, qty = level.get("Price"), level.get("Qty")
        if price is None or qty is None:
            continue
        if qty >= threshold:
            return float(price), float(qty)
    return None

def decide_prices(board: Dict[str, Any], params: DecideParams = DecideParams()) -> Optional[Dict[str, Any]]:
    """
    当日の板・レンジから
      - buy_price（買い指値）
      - sell_price（売り指値/利確）
      - stop_price（損切り）
      - 参考情報（検出した壁・当日レンジなど）
    を決める。条件が悪い場合は None を返す。
    """
    # 必要フィールド取得
    bid = board.get("BidPrice")
    ask = board.get("AskPrice")
    last = board.get("CurrentPrice")
    day_high = board.get("HighPrice")
    day_low  = board.get("LowPrice")
    total_vol = float(board.get("TradingVolume") or 0)

    if None in (ask, bid, last, day_high, day_low):
        return None

    ask = float(ask); bid = float(bid); last = float(last)
    day_high = float(day_high); day_low = float(day_low)

    # 壁検出
    sell_wall = _find_wall_side(board, "Sell", params, total_vol)  # 先頭側の抵抗
    buy_wall  = _find_wall_side(board, "Buy",  params, total_vol)  # 先頭側の支持

    # 買い候補：現状のAskと支持（買い壁）の高い方に寄せる（無理追いはしない）
    tentative_buy = ask
    if buy_wall:
        tentative_buy = max(tentative_buy, buy_wall[0])

    # 当日安値から離れすぎているなら見送り（リスク高）
    if (tentative_buy - day_low) > params.near_low_allow_ticks * params.tick:
        return None

    buy_price = _tick_round(tentative_buy, params.tick)

    # 利確候補：最低 +1tick、最大 +3tick。手前に強い売り壁があれば壁の1tick手前に置く
    tp_min = buy_price + params.tp_min_ticks * params.tick
    tp_max = buy_price + params.tp_max_ticks * params.tick
    target = tp_min
    if sell_wall:
        wall_price = sell_wall[0]
        # 壁が近すぎるなら利幅が確保できないため見送り
        if (wall_price - buy_price) < params.min_room_to_resist_ticks * params.tick:
            return None
        target = min(wall_price - params.tick, tp_max)

    sell_price = _tick_round(max(target, tp_min), params.tick)

    # ストップ：買値-1tick
    stop_price = _tick_round(buy_price - params.sl_ticks * params.tick, params.tick)

    # 境界チェック
    if not (day_low <= buy_price <= day_high):
        return None
    if sell_price <= buy_price:
        return None
    if stop_price >= buy_price:
        return None

    # 参考情報
    info = {
        "buy_price": buy_price,
        "sell_price": sell_price,
        "stop_price": stop_price,
        "ask": ask,
        "bid": bid,
        "last": last,
        "day_low": day_low,
        "day_high": day_high,
        "sell_wall": {"price": sell_wall[0], "qty": sell_wall[1]} if sell_wall else None,
        "buy_wall": {"price": buy_wall[0], "qty": buy_wall[1]} if buy_wall else None,
        "reason": []
    }

    # 理由メモ
    if buy_wall:
        info["reason"].append(f"買い壁 {buy_wall[0]:.1f} に寄せて買いを設定")
    else:
        info["reason"].append("買い壁検出なしのためAsk基準で買い設定")

    if sell_wall:
        info["reason"].append(f"売り壁 {sell_wall[0]:.1f} の1tick手前で利確")
    else:
        info["reason"].append(f"壁なしのため最小利確 {params.tp_min_ticks}tick を採用")

    info["reason"].append(f"損切りは {params.sl_ticks}tick（{stop_price:.1f}円）")
    return info

# ---- サンプル実行（提示いただいたBoardを使用） ----
if __name__ == "__main__":
    board = {
        'AskPrice': 18.0, 'AskQty': 8967700.0, 'AskSign': '0101',
        'AskTime': '2025-08-13T15:30:00+09:00', 'BidPrice': 19.0, 'BidQty': 7792800.0,
        'BidSign': '0101', 'BidTime': '2025-08-13T15:30:00+09:00',
        'Buy1': {'Price': 18.0, 'Qty': 8967700.0, 'Sign': '0101', 'Time': '2025-08-13T15:30:00+09:00'},
        'Buy2': {'Price': 17.0, 'Qty': 16935400.0}, 'Buy3': {'Price': 16.0, 'Qty': 5800400.0},
        'Buy4': {'Price': 15.0, 'Qty': 3922300.0}, 'Buy5': {'Price': 14.0, 'Qty': 1390800.0},
        'Buy6': {'Price': 13.0, 'Qty': 493100.0}, 'Buy7': {'Price': 12.0, 'Qty': 250500.0},
        'Buy8': {'Price': 11.0, 'Qty': 107300.0}, 'Buy9': {'Price': 10.0, 'Qty': 206500.0},
        'Buy10': {'Price': 9.0, 'Qty': 33500.0}, 'CalcPrice': 18.0, 'ChangePreviousClose': 0.0,
        'ChangePreviousClosePer': 0.0, 'CurrentPrice': 18.0, 'CurrentPriceChangeStatus': '0061',
        'CurrentPriceStatus': 1, 'CurrentPriceTime': '2025-08-13T15:30:00+09:00', 'Exchange': 1,
        'ExchangeName': '東証プ', 'HighPrice': 19.0, 'HighPriceTime': '2025-08-13T09:00:01+09:00',
        'LowPrice': 18.0, 'LowPriceTime': '2025-08-13T09:00:00+09:00', 'MarketOrderBuyQty': 0.0,
        'MarketOrderSellQty': 0.0, 'OpeningPrice': 18.0, 'OpeningPriceTime': '2025-08-13T09:00:00+09:00',
        'OverSellQty': 7305300.0, 'PreviousClose': 18.0, 'PreviousCloseTime': '2025-08-12T00:00:00+09:00',
        'SecurityType': 1, 'Sell1': {'Price': 19.0, 'Qty': 7792800.0, 'Sign': '0101', 'Time': '2025-08-13T15:30:00+09:00'},
        'Sell2': {'Price': 20.0, 'Qty': 10384800.0}, 'Sell3': {'Price': 21.0, 'Qty': 4883900.0},
        'Sell4': {'Price': 22.0, 'Qty': 2287700.0}, 'Sell5': {'Price': 23.0, 'Qty': 1056000.0},
        'Sell6': {'Price': 24.0, 'Qty': 1521400.0}, 'Sell7': {'Price': 25.0, 'Qty': 1411900.0},
        'Sell8': {'Price': 26.0, 'Qty': 1105500.0}, 'Sell9': {'Price': 27.0, 'Qty': 1145200.0},
        'Sell10': {'Price': 28.0, 'Qty': 655800.0}, 'Symbol': '6740', 'SymbolName': 'ジャパンディスプレイ',
        'TotalMarketValue': 69846984396.0, 'TradingValue': 2985595200.0, 'TradingVolume': 165863200.0,
        'TradingVolumeTime': '2025-08-13T15:30:00+09:00', 'UnderBuyQty': 38835900.0, 'VWAP': 18.0003
    }

    plan = decide_prices(board)
    print(plan)
