import logging
import time
from datetime import datetime, time as dtime
from kabusapi_board import get_board_info
from kabusapi_positions import get_positions
from kabusapi_sendorder_cash_sell import send_cash_sell_order
from kabusapi_sendorder_cash_buy import send_cash_buy_order
from kabusapi_cash import get_cash_balance
from const import target_symbol, position_params, sell_obj, buy_obj, order_params_by_id, target_symbol_no_exchange
from total_func import is_within_limit, confirm_state, get_total, check_trades_and_limit
from kabusapi_orders import get_orders
from order_get import latest_detail_of_latest_order
import json
from day_price_judge import decide_prices_scalp, ScalpParams, search_buy_candidates
from copy import deepcopy
from kabusapi_cancelorder import cancel_order

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class TradeBot:
    """
    ランド株(8918)の短期売買を行うBot。
    - 現物買いは <= BUY_THRESHOLD
    - 現物売りは >= SELL_THRESHOLD
    - ポジション管理: 0株->買い, 保有->売り
    - 1日の取引上限チェック, 未約定注文の確認
    """
    BUY_THRESHOLD = 9.2
    SELL_THRESHOLD = 9.8
    TRADE_QTY = 100

    def __init__(self):
        self.symbol = target_symbol
        self.position_params = position_params
        self.target_symbol_no_exchange = target_symbol_no_exchange

    def has_pending_orders(self) -> bool:
        return confirm_state()

    def has_exceeded_limit(self) -> bool:
        return is_within_limit()

    def get_cash(self) -> float:
        data = get_cash_balance()
        return data.get('StockAccountWallet', 0)

    def is_holding(self) -> bool:
        # Load symbol from buy_price.json; fallback to self.target_symbol_no_exchange on error
        try:
            with open('buy_price.json', 'r', encoding='utf-8') as bf:
                bdata = json.load(bf)
                file_symbol = bdata.get('symbol')
        except Exception as e:
            file_symbol = self.target_symbol_no_exchange
        
        self.position_params['symbol'] = file_symbol
        positions = get_positions(self.position_params) or []
        
        for pos in positions:
            if (pos.get('Symbol') == file_symbol and
                float(pos.get('LeavesQty', 0)) > 0):
                return True
        return False
    
    def latest_orders(self) -> bool:
        orders = get_orders(order_params_by_id)
        res = latest_detail_of_latest_order(orders)
        return res
        
    def get_symbol_price(self) -> float:
        info = get_board_info(self.symbol)
        if info is None:
            raise RuntimeError("現在価格が取得できませんでした。")
        return info

    def check_conditions(self) -> bool:
        """
        未処理の注文があるか、1日の取引上限を超えているかをチェック。
        条件を満たしている場合はログを出力し、Trueを返す。
        """
        if self.has_pending_orders():
            logger.info("未処理の注文があります。処理をスキップします。")
            return True

        if self.has_exceeded_limit():
            logger.info("1日の取引上限を超えました。処理を中止します。")
            return True

        return False
    
    def get_order_latest(self, order_id="20250805A01N18930077") -> float:
        """
        最新の注文情報を取得し、ログに出力する。
        """
        order_params_by_id['id'] = order_id
        order = get_orders(order_params_by_id)
        details = {}
        print("取得した注文情報____:", order)
        for o in order:
            details = o['Details']
            if not details:
                logger.warning("注文詳細が見つかりません。")
                return None

        # SeqNum で最新を取る場合
        latest_by_seq = max(details, key=lambda d: d['SeqNum'])
        print("最新レコード（SeqNum基準）:", latest_by_seq)

        # TransactTime で最新を取る場合
        latest_by_time = max(
            details,
            key=lambda d: datetime.fromisoformat(d['TransactTime'])
        )
        print("最新レコード（時間基準）:", latest_by_time)
        with open('latest_price.json', 'w', encoding='utf-8') as f:
            json.dump({'last_price': latest_by_seq['Price']}, f, ensure_ascii=False, indent=2)
        return latest_by_seq['Price']


    def execute_trade(self):
        # 1) 日次上限などのガード
        if check_trades_and_limit():
            return

        # ========== ストップ監視: 既に売り注文が板にある間だけ実施 ==========
        if self.has_pending_orders():
            # buy_price.json から symbol / stop_price / order_id を取得
            try:
                with open('buy_price.json', 'r', encoding='utf-8') as bf:
                    bdata = json.load(bf)
                symbol_file   = bdata.get('symbol')
                stop_price    = float(bdata.get('stop_price')) if bdata.get('stop_price') is not None else None
                current_sell_order_id = bdata.get('order_id')
            except Exception as e:
                logger.warning(f"buy_price.json の読込に失敗: {e}（ストップ監視をスキップ）")
                return

            if not symbol_file or stop_price is None:
                logger.info("ストップ判定に必要な symbol / stop_price が未設定のためスキップ")
                return

            # 板取得（Best Bid = いま即売れる価格）
            bd = get_board_info(f"{symbol_file}@1") or get_board_info(symbol_file)
            if not bd:
                logger.warning("板情報が取得できず、ストップ判定をスキップ")
                return
            bid = None
            try:
                buy1 = bd.get("Buy1") or {}
                bid = float(buy1.get("Price") if buy1 else bd.get("BidPrice"))
            except Exception:
                pass
            if not bid:
                logger.info("Bid が取れずストップ判定をスキップ")
                return

            # 条件: いま売れる価格（Bid）が stop_price 以下 → 既存売りを取消して即時損切り
            if bid <= stop_price:
                logger.info(f"STOP 発動: Bid={bid} <= stop_price={stop_price}")
                # 既存の売り注文をキャンセル（ID があれば）
                if current_sell_order_id:
                    try:
                        cancel_order(current_sell_order_id)
                        logger.info(f"既存売り注文を取消: order_id={current_sell_order_id}")
                    except Exception as e:
                        logger.error(f"取消失敗（続行して成行損切り）: {e}")

                # 成行相当で損切り（Bid に寄せた指値）
                so = deepcopy(sell_obj)
                if isinstance(so, dict):
                    so["Price"] = bid
                try:
                    send_cash_sell_order(so, symbol_file, want_sell_price=bid)
                    logger.info(f"成行相当で損切り発注: {self.TRADE_QTY}@{bid}")
                except Exception as e:
                    logger.error(f"損切り発注に失敗: {e}")

                # このループは終了
                return
            else:
                # 価格が stop を下回っていない → 何もせず次ループへ
                logger.info(f"STOP 未発動: Bid={bid} > stop_price={stop_price}。このループは終了")
                return
        # ===============================================================
        
        # 株を保有してるか確認
        holding = self.is_holding()

        if not holding:
            # 2) 板取得 → その場の売買基準（buy/sell/stop）を算出
            plan = search_buy_candidates()
            if not plan:
                logger.info("見送り：当日レンジ/板条件を満たさず。")
                return

            buy_px  = plan["buy_price"]
            sell_px = plan["sell_price"]
            stop_px = plan["stop_price"]
            target_symbol = plan["target_symbol"]

            ask = plan["AskPrice"]
            bid = plan["BidPrice"]

        # 3) オートマトン
        if holding:
            # --- 保有中：損切り優先、そうでなければ問答無用で利確売り ---
            # buy_price.json があれば優先して買値+1 を利確価格として使う
            override_sell_px = 9999999
            try:
                with open('buy_price.json', 'r', encoding='utf-8') as bf:
                    bdata = json.load(bf)
                    bp = bdata.get('buy_price')
                    target_symbol = bdata.get('symbol')
                    if bp is not None:
                        override_sell_px = float(bp) + 1
                        logger.info(f"buy_price.json から買値を取得: {bp} → 利確を {override_sell_px} に上書き")
            except FileNotFoundError:
                logger.info('buy_price.json が見つからないため、planの利確価格を使用します。')
            except Exception as e:
                logger.warning(f"buy_price.json 読み込みエラー: {e} — planの利確価格を使用します。")

            # 2) 損切り条件に該当しない → 問答無用で利確売りを出す
            so = deepcopy(sell_obj)
            if isinstance(so, dict):
                so["Price"] = override_sell_px
            # 利確の売り注文を発注 → 戻り OrderId を buy_price.json に保存（取消に使う）
            try:
                sell_res = send_cash_sell_order(so, target_symbol, want_sell_price=override_sell_px)
                sell_order_id = sell_res.get("OrderId") if isinstance(sell_res, dict) else None
                if sell_order_id:
                    try:
                        with open('buy_price.json', 'r', encoding='utf-8') as bf:
                            bdata = json.load(bf)
                    except Exception:
                        bdata = {}
                    bdata.update({"order_id": sell_order_id})
                    with open('buy_price.json', 'w', encoding='utf-8') as bf:
                        json.dump(bdata, bf, ensure_ascii=False, indent=2)
                    logger.info(f"sell order_id を保存: {sell_order_id}")
            except Exception as e:
                logger.error(f"利確売り発注に失敗: {e}")
            return

        else:
            # --- 未保有：買いのみ ---
            if ask is None:
                logger.info("Ask が None。買い判定保留。")
                return

            # 「買ったら必ず売る」= 連続買い禁止 → latest_orders()/未約定でガード
            if self.latest_orders() and get_total(buy_px*100):
                res = send_cash_buy_order(buy_obj, target_symbol, want_buy_price=buy_px)
                order_id = res.get("OrderId") if isinstance(res, dict) else None
                logger.info(f"買い注文発注: {self.TRADE_QTY}@{buy_px} (ask={ask})")
                try:
                    # 先に候補の stop_price も保存（約定後に再保存）
                    with open('buy_price.json', 'w', encoding='utf-8') as bf:
                        json.dump({'symbol': target_symbol, 'buy_price': buy_px, 'stop_price': stop_px, 'order_id': None},
                                  bf, ensure_ascii=False, indent=2)
                        logger.info(f"buy_price.json に買値/ストップを保存: buy={buy_px}, stop={stop_px}")
                except Exception as e:
                    logger.warning(f"buy_price.json の保存に失敗しました: {e}")

                time.sleep(1)  # 直後の反映待ち
                if order_id:
                    # --- 約定監視（最大15秒、1秒おき） ---
                    WAIT_SEC = 15.0
                    INTERVAL = 1.0
                    t0 = time.time()
                    filled = False

                    while True:
                        od = self.get_order_latest(order_id) or {}

                        # 約定数量の取得（環境差吸収: ExecutedQty/CumQty/ExecutionQty を順に参照）
                        exec_qty = od.get("ExecutedQty") or od.get("CumQty") or od.get("ExecutionQty") or 0
                        try:
                            exec_qty = float(exec_qty)
                        except Exception:
                            exec_qty = 0.0

                        if exec_qty >= float(self.TRADE_QTY):
                            filled = True
                            logger.info(f"買い注文 約定完了: {exec_qty}/{self.TRADE_QTY} order_id={order_id}")
                            # 買値の保存（約定確認後）
                            try:
                                with open('buy_price.json', 'w', encoding='utf-8') as bf:
                                    json.dump({'symbol': target_symbol, 'buy_price': buy_px, 'stop_price': stop_px, 'order_id': None},
                                              bf, ensure_ascii=False, indent=2)
                                logger.info(f"buy_price.json に買値/ストップを保存（約定後）: buy={buy_px}, stop={stop_px}")
                            except Exception as e:
                                logger.warning(f"buy_price.json の保存に失敗しました: {e}")
                            break

                        # タイムアウト判定
                        if (time.time() - t0) >= WAIT_SEC:
                            logger.info(f"買い注文 未約定のため取消: 約定={exec_qty}/{self.TRADE_QTY}, order_id={order_id}")
                            try:
                                cancel_order(order_id)  # kabusapi_cancelorder.py の関数
                            except Exception as e:
                                logger.error(f"取消失敗: {e}")
                            # 未約定（または一部約定）で終了
                            return

                        time.sleep(INTERVAL)
            else:
                logger.info(f"買い見送り: ask={ask} > buy={buy_px} または latest_orders() NG")
                return


    def run(self):
        try:
            self.execute_trade()
        except Exception as e:
            logger.error(f"トレード処理中にエラーが発生しました: {e}")


def schedule_loop(bot: TradeBot):
    """
    時間帯に応じて bot.run() を繰り返し呼び出す。
    - 9:00〜11:30 / 12:30〜15:30 → 5秒毎
    - 9:00前 → 60秒毎
    - 15:31以降 → 終了
    - それ以外 → 300秒毎
    """
    # その日の株価を取得し、売買基準を決める
    # board_info = get_board_info()
    # if board_info is None:
    #     logger.error("株価情報が取得できませんでした。処理を中止します。")
    #     return
    # res = decide_prices(board_info)
    
    while True:
        now = datetime.now()
        t = now.time()
        # 取引時間帯
        morning_start = dtime(9, 00)
        morning_end = dtime(11, 30)
        afternoon_start = dtime(12, 30)
        afternoon_end = dtime(15, 00)
        end_of_day = dtime(20,00)

        if t >= end_of_day:
            logger.info("取引時間終了のためスケジュールを停止します。")
            break

        # 実行
        bot.run()

        # 待機時間決定
        if morning_start <= t <= morning_end or afternoon_start <= t <= afternoon_end:
            interval = 1
        elif t < morning_start:
            interval = 60
        else:
            interval = 300

        time.sleep(interval)

if __name__ == '__main__':
    bot = TradeBot()
    schedule_loop(bot)
    logger.info("スケジュール処理が完了しました。")
    # bot.get_order_latest()
