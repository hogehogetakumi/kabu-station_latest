from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any, List
import math
from datetime import datetime, time as dtime, timedelta
from const import symbol_list
from kabusapi_board import get_board_info
import time

# ===== 1) 80〜100円帯向けパラメータ =====

@dataclass
class ScalpParams:
    # --- 呼値（自動検出を基本とし、フォールバックは0.1円） ---
    tick: float = 1
    detect_tick_from_board: bool = True

    # --- 利確/損切り（低位スキャ向け：+1tick利確、SLは状況で1〜2tick） ---
    tp_min_ticks: int = 1
    tp_max_ticks: int = 1
    sl_ticks: int = 1          # 基本1tick（後で動的に2tickへ拡張）

    # --- スプレッド/板の厚みフィルタ ---
    max_spread_ticks: int = 2          # 80〜100円帯は2tick超は見送り
    max_spread_pct: float = 0.4 / 100  # 0.4%超のスプレッドも見送り

    # --- 1秒あたりの“代金”しきい（約定スピードの代理）---
    use_value_based_filters: bool = True
    min_top_value_yen: int = 150_000   # Top of book の金額が薄すぎる銘柄は見送り
    min_1s_value_join: int = 30_000    # Joinするなら最低これくらいは流れていてほしい
    min_1s_value_take: Optional[int] = None  # 「取りに行く」用（今回は未使用）

    # --- 売り板の薄さ条件（Sell1/Buy1 ≤ 2 など）---
    ratio_limit: float = 2.0
    thin_next_asks_ratio: float = 0.7  # Sell2,3が薄めなら◎（任意で使う）

    # --- キュー先行量から見た退出ETAの上限（秒）---
    max_exit_eta_sec: float = 15.0

    # --- VWAP乖離（80〜100円は実質オフ）---
    vwap_disable_below_price: float = 100.0
    vwap_max_abs_yen: float = 2.0
    vwap_max_pct: float = 0.4 / 100

    # --- キュー時間でSLを厚めにする閾値 ---
    expand_sl_eta_sec: float = 12.0


def search_buy_candidates() -> List[Dict[str, Any]]:
    """
    symbol_list の各銘柄について板を評価し、
    ・価格帯が80〜100円
    ・Spread>=1tick
    ・Sell1/Buy1<=2
    ・Exit ETA<=15s
    を満たす中から「退出ETAが最短」の plan(dict) を1件返す（なければ None）。
    decide_prices_scalp() の戻り値フォーマットは既存のまま。
    """
    p = ScalpParams()
    ETA_LIMIT = p.max_exit_eta_sec

    best_plan: Optional[Dict[str, Any]] = None
    best_eta: float = float("inf")
    best_ratio: float = float("inf")

    for symbol in symbol_list:
        time.sleep(0.13)  # APIレート控えめ
        bd = get_board_info(f"{symbol}@1")
        if not bd:
            continue

        # 価格帯判定（先に軽く落とす）
        s1 = bd.get("Sell1") or {}
        b1 = bd.get("Buy1")  or {}
        ask = float((s1.get("Price") if s1 else bd.get("AskPrice")) or 0.0)
        bid = float((b1.get("Price") if b1 else bd.get("BidPrice")) or 0.0)
        if ask <= 0 or bid <= 0:
            continue
        if ask < bid:
            ask, bid = bid, ask
        mid = (ask + bid) / 2.0
        if not (80.0 <= mid <= 100.0):
            continue

        # スプレッドと板の厚みのざっくりチェック
        tick = _infer_tick(bd, p.tick) if p.detect_tick_from_board else max(1e-9, p.tick)
        if (ask - bid) < tick:
            continue
        ask_qty = float((s1.get("Qty") if s1 else bd.get("AskQty")) or 0.0)
        b1_qty = float((b1.get("Qty") if b1 else bd.get("BidQty")) or 0.0)
        if b1_qty <= 0:
            continue
        ratio = ask_qty / b1_qty
        if ratio > p.ratio_limit:
            continue

        # 退出ETAの概算（OneSecValue利用）
        osv = float(bd.get("OneSecValue") or 0.0)
        if osv <= 0.0:
            tv = float(bd.get("TradingValue") or 0.0)
            tstr = bd.get("TradingVolumeTime") or bd.get("CurrentPriceTime")
            osv = (tv / max(_session_elapsed_seconds(tstr), 1)) * 0.35
        if osv <= 0:
            continue
        eta_exit = (ask * ask_qty) / osv
        if eta_exit > ETA_LIMIT:
            continue

        # 本番計算（フィルタも内部で再チェック）
        plan = decide_prices_scalp(bd, p)
        if not plan:
            continue

        # ランキング: ETA最短 → 売り/買い比が軽い
        better = (
            (eta_exit < best_eta) or
            (eta_exit == best_eta and ratio < best_ratio)
        )
        if better:
            best_plan = plan
            best_eta = eta_exit
            best_ratio = ratio

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
    80〜100円帯の超低位スキャ専用:
      - スプレッド/板の厚み/1秒代金(OneSecValue近似)で流動性チェック
      - 買い: 基本 Buy1 に Join（spread>=1tick）
      - 売り: +1tick（tp_ticks=1）
      - 損切り: 1〜2tick（spreadが広い/売り優勢/退出ETAが長いときは2tick）
    戻り値フォーマットは既存と同じ（buy_price/sell_price/stop_price など）。
    """

    # ---- Best Bid/Ask の取得 ----
    s1 = board.get("Sell1") or {}
    b1 = board.get("Buy1")  or {}
    ask = s1.get("Price") if s1 else board.get("AskPrice")
    bid = b1.get("Price") if b1 else board.get("BidPrice")
    if ask is None or bid is None:
        return None
    ask = float(ask); bid = float(bid)
    if ask <= 0 or bid <= 0:
        return None
    if ask < bid:  # 逆転スナップの補正
        ask, bid = bid, ask

    mid = (ask + bid) / 2.0
    # ---- 価格帯フィルタ: 80〜105円のみ ----
    if not (80.0 <= mid <= 105.0):
        return None

    # ---- 呼値推定 ----
    # tick = _infer_tick(board, p.tick) if p.detect_tick_from_board else max(1e-9, p.tick)
    # if tick <= 0:
    #     tick = 0.1
    tick = p.tick

    spread = ask - bid
    spread_ticks = int(round(spread / tick)) if tick > 0 else 0
    spread_pct = spread / max(1.0, bid)

    # (1) スプレッド: 1以外の時は見送り
    if spread_ticks != 1:
        return None

    # ---- 板の厚み（Top of book金額 & Sell1/Buy1比）----
    ask_qty = float((s1.get("Qty") if s1 else board.get("AskQty")) or 0.0)
    bid_qty = float((b1.get("Qty") if b1 else board.get("BidQty")) or 0.0)
    if bid_qty <= 0:
        return None
    depth_ratio = ask_qty / bid_qty
    if depth_ratio > p.ratio_limit:
        return None

    # Top of book の金額（退出速度の粗い proxy）
    top_value_yen = ask * ask_qty
    if p.use_value_based_filters and top_value_yen < p.min_top_value_yen:
        return None

    # ---- 1秒あたりの代金 OneSecValue（なければセッション平均の0.35倍で近似）----
    osv = float(board.get("OneSecValue") or 0.0)
    if osv <= 0.0:
        tv = float(board.get("TradingValue") or 0.0)
        tstr = board.get("TradingVolumeTime") or board.get("CurrentPriceTime")
        sec = _session_elapsed_seconds(tstr)  # ヘルパー既存
        osv = (tv / max(sec, 1)) * 0.35

    if osv <= 0.0:
        return None
    if osv < p.min_1s_value_join:
        return None

    # ---- 退出ETA（次の売り板が掃けるまでのおおよそ秒）----
    eta_exit = (ask * ask_qty) / osv
    if eta_exit > p.max_exit_eta_sec:
        return None

    # ---- 価格の決定 ----
    buy_px  = bid                                  # Join
    tp_ticks = 1                                   # +1tick利確
    sell_px = _round_to_tick(buy_px + tick * tp_ticks, tick)

    # 損切りtickの動的拡張
    stop_ticks = max(1, int(p.sl_ticks))
    if spread_ticks >= 2 or depth_ratio >= 1.5 or eta_exit >= p.expand_sl_eta_sec:
        stop_ticks = max(stop_ticks, 2)

    # 安全弁: 割合が重すぎる銘柄はエントリー回避（たとえば 1.2%超のSLは重い）
    stop_pct = (tick * stop_ticks) / max(1.0, buy_px)
    if stop_pct > 0.013:   # 1.2%超は見送り
        return None

    stop_px = _round_to_tick(buy_px - tick * stop_ticks, tick)

    return {
        "target_symbol": board.get("Symbol"),
        "buy_price":  buy_px,
        "sell_price": sell_px,
        "stop_price": stop_px,
        "BidPrice":   bid,
        "AskPrice":   ask,
        "notes": {
            "tick": tick,
            "spread_ticks": spread_ticks,
            "spread_pct": spread_pct,
            "depth_ratio": depth_ratio,
            "top_value_yen": top_value_yen,
            "one_sec_value": osv,
            "eta_exit_sec": eta_exit
        }
    }