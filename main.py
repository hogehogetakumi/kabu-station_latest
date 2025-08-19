import logging
import time
from datetime import datetime, time as dtime
from kabusapi_board import get_board_info
from kabusapi_positions import get_positions
from kabusapi_sendorder_cash_sell import send_cash_sell_order
from kabusapi_sendorder_cash_buy import send_cash_buy_order
from kabusapi_cash import get_cash_balance
from const import target_symbol, position_params, sell_obj, buy_obj, order_params_by_id, target_symbol_no_exchange
from total_func import is_within_limit, confirm_state, check_trades_and_limit
from kabusapi_orders import get_orders
from order_get import latest_detail_of_latest_order
import json
from day_price_judge import decide_prices, DecideParams 
from copy import deepcopy

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
        positions = get_positions(self.position_params) or []
        for pos in positions:
            if (pos.get('Symbol') == self.target_symbol_no_exchange and
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
        # 追加ガード：未約定注文があれば新規発注しない
        if self.has_pending_orders():
            logger.info("未処理の注文あり。新規発注をスキップ。")
            return

        # 2) 板取得 → その場の売買基準（buy/sell/stop）を算出
        board = self.get_symbol_price()
        plan = decide_prices(board, DecideParams())
        if not plan:
            logger.info("見送り：当日レンジ/板条件を満たさず。")
            return

        buy_px  = plan["buy_price"]
        sell_px = plan["sell_price"]
        stop_px = plan["stop_price"]

        ask = board.get("AskPrice")
        bid = board.get("BidPrice")

        holding = self.is_holding()

        # 3) オートマトン
        if holding:
            # --- 保有中：売りのみ ---
            if bid is None:
                logger.info("Bid が None。売り判定保留。")
                return

            # 3-1) 利確
            if bid >= sell_px:
                so = deepcopy(sell_obj)
                # send_cash_sell_order が価格引数を受けない設計なら、オブジェクト側に価格を入れて渡す
                if isinstance(so, dict):
                    so["Price"] = sell_px
                send_cash_sell_order(so, want_sell_price=sell_px)
                logger.info(f"利確売り発注: {self.TRADE_QTY}@{sell_px} (bid={bid})")
                return

            # 3-2) 損切り
            if bid <= stop_px:
                so = deepcopy(sell_obj)
                if isinstance(so, dict):
                    # ここは“確実に出る”ことを優先したいので、成行 or 価格は現在のBidに寄せる方針でもOK
                    so["Price"] = bid
                send_cash_sell_order(so)
                logger.info(f"損切り売り発注: {self.TRADE_QTY}@{bid} (stop={stop_px})")
                return

            logger.info(f"保有継続: bid={bid}, tp={sell_px}, sl={stop_px}")
            return

        else:
            # --- 未保有：買いのみ ---
            if ask is None:
                logger.info("Ask が None。買い判定保留。")
                return

            # 「買ったら必ず売る」= 連続買い禁止 → latest_orders()/未約定でガード
            if ask <= buy_px and self.latest_orders():
                res = send_cash_buy_order(buy_obj, want_buy_price=buy_px)
                order_id = res.get("OrderId") if isinstance(res, dict) else None
                logger.info(f"買い注文発注: {self.TRADE_QTY}@{buy_px} (ask={ask})")

                # 直後の反映待ち（必要に応じて短めスリープ）
                time.sleep(2)
                if order_id:
                    self.get_order_latest(order_id)
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
        end_of_day = dtime(15, 00)

        if t >= end_of_day:
            logger.info("取引時間終了のためスケジュールを停止します。")
            break

        # 実行
        bot.run()

        # 待機時間決定
        if morning_start <= t <= morning_end or afternoon_start <= t <= afternoon_end:
            interval = 2
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
