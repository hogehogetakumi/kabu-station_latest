from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any, List
import math
from datetime import datetime, time as dtime, timedelta
from const import symbol_list
from kabusapi_board import get_board_info
import time


@dataclass
class ScalpParams:
    # --- 価格系（呼値） ---
    tick: float = 1.0
    detect_tick_from_board: bool = True

    # --- テイクプロフィット/ストップ ---
    tp_min_ticks: int = 1
    tp_max_ticks: int = 1
    sl_ticks: int = 1
    take_profit_yen: float = 1.0  # “1円抜き”優先

    # --- 板・不均衡トリガ ---
    imbalance_take: float = 1.1          # 1.3 → 1.1（軽め優勢でテイク許可）
    small_ask_take: int = 0
    improve_when_spread_ge: int = 1
    thin_next_asks_ratio: float = 0.7

    # --- 出来高急増（1秒）トリガ ---
    vol_surge_mult: float = 1.2          # 1.5 → 1.2（急増条件を緩める）
    min_1s_value: int = 50_000           # 150k → 50k 円/秒（低位×超流動向け）
    require_surge_for_take: bool = False # 急増がなくてもテイク可

    # --- セーフティ/フィルタ ---
    max_spread_ticks: int = 2
    max_spread_pct: float = 0.25
    min_top_depth: int = 0
    allow_join_when_no_surge: bool = True

    # --- 価値（円）ベースの流動性チェック ---
    use_value_based_filters: bool = True
    min_top_value_yen: int = 150_000      # 200k → 150k（板トップの金額しきい緩和）
    small_ask_value_yen: int = 600_000    # 300k → 600k（小口Askなら“取りに行く”許可）

    # --- join/improve と take で分ける代金しきい ---
    min_1s_value_take: Optional[int] = None
    min_1s_value_join: Optional[int] = 30_000  # 100k → 30k

    # --- VWAP 乖離フィルタ（低位は無効化） ---
    vwap_disable_below_price: float = 100.0    # 50 → 100（JDI帯は実質無効）
    vwap_max_abs_yen: float = 2.0              # 1.0 → 2.0
    vwap_max_pct: float = 0.004                # 0.2% → 0.4%

    # --- キュー先行量（埋まり見込み時間） ---
    max_queue_eta_sec: float = 10.0            # 3 → 10（並び許容を拡大）
    # ※ 退出側ETAは関数内の固定30sのままでもOK（必要なら 20–30s で調整）

# 買いの条件を満たす銘柄を見つける
def search_buy_candidates() -> List[Dict[str, Any]]:
    """
    boards に含まれる各銘柄の板を評価し、
    Spread≥1tick / Exit≤15s / 売り薄(≤2) を満たす中から
    「退出ETAが最短」の銘柄の plan(dict) を1件だけ返す。
    ヒットなしなら None。関数名・引数・戻り値の形式は元のまま。
    ※ decide_prices_scalp の戻り値フォーマットは変更しない。
    """
    ETA_LIMIT   = 15.0
    RATIO_LIMIT = 2.0
    p = ScalpParams()

    # boards が空なら従来フロー（symbol_list → get_board_info）で補完
    source_boards: List[Dict[str, Any]] = []
    if not source_boards:
        for symbol in symbol_list:
            time.sleep(0.3)
            bd = get_board_info(f"{symbol}@1")
            if bd:
                source_boards.append(bd)

    best_plan: Optional[Dict[str, Any]] = None
    best_eta: float = float("inf")
    best_ratio: float = float("inf")
    best_symbol: Optional[str] = None

    for bd in source_boards:
        s1 = bd.get("Sell1") or {}
        b1 = bd.get("Buy1")  or {}
        ask = float(s1.get("Price") or bd.get("AskPrice") or 0.0)
        bid = float(b1.get("Price") or bd.get("BidPrice")  or 0.0)
        if ask <= 0 or bid <= 0:
            continue
        # スナップ逆転補正
        if ask < bid:
            ask, bid = bid, ask

        # 1) Spread ≥ 1tick
        tick = _infer_tick(bd, 1.0 if p.tick <= 0 else p.tick)
        if ask - bid < tick:
            continue

        # 2) 売りが薄い/買いが厚い … Sell1.Qty / Buy1.Qty ≤ 2
        s1q = float(s1.get("Qty") or bd.get("AskQty") or 0.0)
        b1q = float(b1.get("Qty") or bd.get("BidQty") or 0.0)
        if b1q <= 0:
            continue
        ratio = s1q / b1q
        if ratio > RATIO_LIMIT:
            continue

        # 3) Exit ≤ 15秒 … (Sell1.Price * Sell1.Qty) / OneSecValue ≤ 15
        osv = float(bd.get("OneSecValue") or 0.0)
        if osv <= 0.0:
            tv = float(bd.get("TradingValue") or 0.0)
            tstr = bd.get("TradingVolumeTime") or bd.get("CurrentPriceTime")
            osv = (tv / max(_session_elapsed_seconds(tstr), 1)) * 0.35
        if osv <= 0:
            continue
        eta_exit = (ask * s1q) / osv
        if eta_exit > ETA_LIMIT:
            continue

        # 上記フィルタ通過 → 実際の発注計画を既存関数で生成
        plan = decide_prices_scalp(bd, p)
        if not plan:
            continue

        # ランキング: ETA最短 → 比率が小さい → フロー大
        better = (
            (eta_exit < best_eta) or
            (eta_exit == best_eta and ratio < best_ratio) or
            (eta_exit == best_eta and ratio == best_ratio and osv > (best_plan.get("notes", {}).get("one_sec_value", -1) if best_plan else -1))
        )
        if better:
            best_plan = plan
            best_eta = eta_exit
            best_ratio = ratio
            best_symbol = bd.get("Symbol")

    # 可能なら target_symbol をモジュール変数として更新（戻り値の形式は不変）
    if best_symbol is not None:
        try:
            globals()["target_symbol"] = best_symbol  # 副作用で最終候補を保持
        except Exception:
            pass

    return best_plan if best_plan is not None else None



def _levels(board: Dict[str, Any], side: str, n: int = 3) -> List[Tuple[float, float]]:
    out = []
    for i in range(1, n+1):
        lv = board.get(f"{side}{i}", {})
        p, q = lv.get("Price"), lv.get("Qty")
        if p is not None and q is not None:
            out.append((float(p), float(q)))
    return out

def _round_to_tick(p: float, tick: float) -> float:
    if tick <= 0:
        tick = 1.0
    return float(f"{round(p / tick) * tick:.3f}")

def _ticks_for_yen(yen: float, tick: float) -> int:
    if tick <= 0:
        return 1
    return max(1, int(round(yen / tick)))

def _infer_tick(board: Dict[str, Any], fallback_tick: float) -> float:
    for k in ("Tick", "TickSize", "MinTick", "PriceTick"):
        t = board.get(k)
        if t is not None:
            try:
                t = float(t)
                if t > 0:
                    return t
            except Exception:
                pass
    prices: List[float] = []
    for side in ("Sell", "Buy"):
        for i in range(1, 4):
            lv = board.get(f"{side}{i}", {})
            p = lv.get("Price")
            if p is not None:
                try:
                    prices.append(float(p))
                except Exception:
                    pass
    if any(abs(round(px * 10) - px * 10) < 1e-6 and abs(round(px) - px) > 1e-6 for px in prices):
        return 0.1
    return fallback_tick if fallback_tick > 0 else 1.0

def _session_elapsed_seconds(time_str: Optional[str]) -> int:
    """
    '2025-08-20T13:01:33+09:00' のようなISO文字列から、当日9:00:00(JST)からの経過秒を概算。
    文字列が無い/壊れている場合は 1 を返す（ゼロ割回避）。
    ※ 昼休みは無視（安全側の過大評価＝ETAが厳しめになる）
    """
    try:
        ts = datetime.fromisoformat(time_str)
        start = ts.replace(hour=9, minute=0, second=0, microsecond=0)
        if ts < start:
            return 1
        return max(1, int((ts - start).total_seconds()))
    except Exception:
        return 1

def decide_prices_scalp(board: Dict[str, Any], p: ScalpParams = ScalpParams()) -> Optional[Dict[str, Any]]:
    """
    【超簡略版】
    条件は以下の3つのみで判定し、満たしたら Buy1 に並び +1tick で利確、-p.sl_ticks*tick で損切り。
      1) Spread ≥ 1tick  … Sell1.Price - Buy1.Price ≥ tick
      2) Exit ≤ 15秒      … (Sell1.Price * Sell1.Qty) / OneSecValue ≤ 15
      3) 売りが薄い/買いが厚い … Sell1.Qty / Buy1.Qty ≤ 2
    * OneSecValue が無い場合は (TradingValue / 当日経過秒) * 0.35 で近似。
    * 関数名・引数・戻り値の形式は既存と同じ。
    """
    # --- Best Bid/Ask（Sell1/Buy1優先、Ask/Bidはフォールバック） ---
    sell1 = board.get("Sell1") or {}
    buy1  = board.get("Buy1")  or {}

    ask = sell1.get("Price", None) if sell1 else None
    bid = buy1.get("Price", None)  if buy1  else None
    if ask is None:
        ask = board.get("AskPrice")
    if bid is None:
        bid = board.get("BidPrice")
    if ask is None or bid is None:
        print("day_price_judge: Bid/Ask not found in board data.")
        return None

    ask = float(ask); bid = float(bid)

    # スナップ逆転対策（理論上起きないが、入れ替えで整合）
    if ask < bid:
        ask, bid = bid, ask

    # --- Qty も Sell1/Buy1 を優先（notes用/比率用） ---
    ask_qty = float((sell1.get("Qty") if sell1 else board.get("AskQty")) or 0.0)
    bid_qty = float((buy1.get("Qty")  if buy1  else board.get("BidQty"))  or 0.0)

    # --- tick 決定 ---
    tick = _infer_tick(board, p.tick) if p.detect_tick_from_board else max(1e-9, p.tick)
    if tick <= 0:
        tick = 1.0

    spread = ask - bid
    spread_ticks = int(round(spread / tick)) if tick > 0 else 0
    spread_pct = spread / max(1.0, bid)

    # 1) Spread ≥ 1tick
    if spread < tick:
        print(f"day_price_judge: Spread < 1tick (spread={spread:.4f}, tick={tick}).")
        return None

    # 2) 売りが薄い/買いが厚い … Sell1.Qty / Buy1.Qty ≤ 2
    RATIO_LIMIT = 2.0
    if bid_qty <= 0:
        print("day_price_judge: BidQty is zero; cannot evaluate ratio.")
        return None
    ratio = (ask_qty / bid_qty) if bid_qty > 0 else float("inf")
    if ratio > RATIO_LIMIT:
        print(f"day_price_judge: Depth ratio too heavy (Sell1/Buy1={ratio:.2f} > {RATIO_LIMIT}).")
        return None

    # 3) Exit ≤ 15秒 … (Sell1.Price * Sell1.Qty) / OneSecValue ≤ 15
    one_sec_value = float(board.get("OneSecValue") or 0.0)
    if one_sec_value <= 0.0:
        tv = float(board.get("TradingValue") or 0.0)  # 当日売買代金(円)
        tstr = board.get("TradingVolumeTime") or board.get("CurrentPriceTime")
        elapsed = _session_elapsed_seconds(tstr)
        one_sec_value = (tv / max(elapsed, 1)) * 0.35  # 保守近似

    ETA_LIMIT = 15.0
    eta_exit = (ask * ask_qty) / max(one_sec_value, 1.0) if ask > 0 else float("inf")
    if eta_exit > ETA_LIMIT:
        print(f"day_price_judge: Exit ETA too long ({eta_exit:.2f}s > {ETA_LIMIT}s).")
        return None

    # --- 条件クリア → Buy1でjoin、+1tick利確、-p.sl_ticks損切り ---
    buy_price  = _round_to_tick(float(bid), tick)
    tp_ticks   = 1
    sell_price = _round_to_tick(buy_price + tp_ticks * tick, tick)
    stop_price = _round_to_tick(buy_price - max(1, p.sl_ticks) * tick, tick)

    if not (sell_price > buy_price and stop_price < buy_price):
        print("day_price_judge: Invalid price order (sell/stop must be >/< buy).")
        return None

    # 参考: 成行/成買/成売の情報（不均衡メモ）
    mkt_buy  = float(board.get("MarketOrderBuyQty")  or 0.0)
    mkt_sell = float(board.get("MarketOrderSellQty") or 0.0)
    imbalance = (bid_qty + mkt_buy) / max(1.0, (ask_qty + mkt_sell))

    return {
        "target_symbol": board.get("Symbol", ""),
        "buy_price": buy_price,
        "sell_price": sell_price,
        "stop_price": stop_price,
        "AskPrice": ask,
        "BidPrice": bid,
        "entry_style": "join",   # 常に Buy1 に並ぶ
        "notes": {
            "tick": tick,
            "spread_ticks": spread_ticks,
            "spread_pct": round(spread_pct, 4),
            "imbalance": round(imbalance, 2),
            "bid_qty": bid_qty,
            "ask_qty": ask_qty,
            "mkt_buy": mkt_buy,
            "mkt_sell": mkt_sell,
            "tp_ticks": tp_ticks,
            "vol_ratio": 0.0,             # 簡略化のため未評価
            "is_surge": False,            # 簡略化のため未評価
            "one_sec_value": int(one_sec_value),
        }
    }
