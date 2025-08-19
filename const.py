import os
from datetime import datetime

target_symbol = '9973@1'
target_symbol_no_exchange = '9973'

# # 検証環境
# api_key = os.environ["VERIFI_API_PASSWORD"]
# base_url = 'http://localhost:18081/kabusapi/'

# 本番環境
base_url = 'http://localhost:18080/kabusapi/'
api_key = os.environ["PRODUCTION_API_PASSWORD"]

# 本日の午前0時のタイムスタンプを取得する関数
def get_today_midnight():
    now = datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    print(midnight.strftime('%Y%m%d%H%M%S'))
    return midnight.strftime('%Y%m%d%H%M%S')

buy_obj = {
    "Symbol":       target_symbol_no_exchange,   # 銘柄コード
    "Exchange":     1,        # 市場コード（東証＝1）
    "SecurityType": 1,        # 現物＝1
    "Side":         2,      # 買い＝2
    "CashMargin":   1,        # 現物取引＝1
    "DelivType":    2,        # 預り金決済
    "FundType":     "02",     # 保護（預り金決済用）
    "AccountType":  4,        # 特定口座（源泉徴収あり）
    "Qty":          100,      # 株数
    "FrontOrderType": 20,      # 成行注文
    "Price":         9,       # 成行では必ず 0
    "ExpireDay":     0        # 当日有効
}


sell_obj = {
    "Symbol":         target_symbol_no_exchange,   # 銘柄コード
    "Exchange":       1,        # 東証
    "SecurityType":   1,        # 現物
    "Side":           1,        # 売り（1）
    "CashMargin":     1,        # 現物取引
    "DelivType":      0,        # 預り金決済
    "FundType":       '  ',     # 保護預り（信用代用 "AA" でも可）
    "AccountType":    4,        # 特定口座（源泉徴収あり）
    "Qty":            100,      # 株数
    "FrontOrderType": 20,       # 成行
    "Price":          10,        # 成行は必ず 0
    "ExpireDay":      0         # 当日有効
}

today_start = get_today_midnight()
order_params = {
    "product": "1",  # Enum値（1: 現物取引）
    "symbol": target_symbol_no_exchange,  # 銘柄コード
    "side": "2",  # Enum値（1: 売、2:
    "updtime": today_start,  # 本日の午前0時のタイムスタンプ
}

order_params_by_id = {
    "product": "1",  # Enum値（1: 現物取引）
    "updtime": today_start,  # 本日の午前0時のタイムスタンプ
}

sample_order_history = [
  {
    "ID": "20250803A01B000001",
    "State": 5,
    "OrderState": 5,
    "OrdType": 1,
    "RecvTime": "2025-08-03T09:01:10.000000+09:00",
    "Symbol": target_symbol_no_exchange,
    "SymbolName": "ランド",
    "Exchange": 1,
    "ExchangeName": "東証プ",
    "TimeInForce": 1,
    "Price": 9.0,
    "OrderQty": 100,
    "CumQty": 1000,
    "Side": "2",           
    "CashMargin": 1,        
    "AccountType": 4,
    "DelivType": 2,
    "ExpireDay": 20250803,
    "MarginTradeType": 0,
    "MarginPremium": None,
    "Details": [
      {
        "SeqNum": 1,
        "ID": "20250803A01B000001",
        "RecType": 1,
        "ExchangeID": "00000000-0000-0000-0000-00000000",
        "State": 3,
        "TransactTime": "2025-08-03T09:01:11.000000+09:00",
        "OrdType": 1,
        "Price": 9.0,
        "Qty": 100,
        "ExecutionID": "E202508030001",
        "ExecutionDay": "2025-08-03T09:02:00+09:00",
        "DelivDay": 20250805,
        "Commission": 0,
        "CommissionTax": 0
      }
    ]
  },
  {
    "ID": "20250803A01S000002",
    "State": 5,
    "OrderState": 5,
    "OrdType": 1,
    "RecvTime": "2025-08-03T09:10:05.000000+09:00",
    "Symbol": target_symbol_no_exchange,
    "SymbolName": "ランド",
    "Exchange": 1,
    "ExchangeName": "東証プ",
    "TimeInForce": 1,
    "Price": 9.0,
    "OrderQty": 100,
    "CumQty": 1000,
    "Side": "1",            
    "CashMargin": 1,
    "AccountType": 4,
    "DelivType": 2,
    "ExpireDay": 20250803,
    "MarginTradeType": 0,
    "MarginPremium": None,
    "Details": [
      {
        "SeqNum": 1,
        "ID": "20250803A01S000002",
        "RecType": 1,
        "ExchangeID": "00000000-0000-0000-0000-00000000",
        "State": 3,
        "TransactTime": "2025-08-03T09:10:06.000000+09:00",
        "OrdType": 1,
        "Price": 9.0,
        "Qty": 100,
        "ExecutionID": "E202508030002",
        "ExecutionDay": "2025-08-03T09:10:45+09:00",
        "DelivDay": 20250805,
        "Commission": 0,
        "CommissionTax": 0
      }
    ]
  },
  {
    "ID": "20250803A02B000003",
    "State": 5,
    "OrderState": 5,
    "OrdType": 1,
    "RecvTime": "2025-08-03T09:30:20.000000+09:00",
    "Symbol": target_symbol_no_exchange,
    "SymbolName": "ランド",
    "Exchange": 1,
    "ExchangeName": "東証プ",
    "TimeInForce": 1,
    "Price": 10.0,
    "OrderQty": 100,
    "CumQty": 800,
    "Side": "2",
    "CashMargin": 1,
    "AccountType": 4,
    "DelivType": 2,
    "ExpireDay": 20250803,
    "MarginTradeType": 0,
    "MarginPremium": None,
    "Details": [
      {
        "SeqNum": 1,
        "ID": "20250803A02B000003",
        "RecType": 1,
        "ExchangeID": "00000000-0000-0000-0000-00000000",
        "State": 3,
        "TransactTime": "2025-08-03T09:30:21.000000+09:00",
        "OrdType": 1,
        "Price": 10.0,
        "Qty": 100,
        "ExecutionID": "E202508030003",
        "ExecutionDay": "2025-08-03T09:31:00+09:00",
        "DelivDay": 20250805,
        "Commission": 0,
        "CommissionTax": 0
      }
    ]
  },
  {
    "ID": "20250803A02S000004",
    "State": 5,
    "OrderState": 5,
    "OrdType": 1,
    "RecvTime": "2025-08-03T09:45:40.000000+09:00",
    "Symbol": target_symbol_no_exchange,
    "SymbolName": "ランド",
    "Exchange": 1,
    "ExchangeName": "東証プ",
    "TimeInForce": 1,
    "Price": 10.0,
    "OrderQty": 100,
    "CumQty": 800,
    "Side": "1",
    "CashMargin": 1,
    "AccountType": 4,
    "DelivType": 2,
    "ExpireDay": 20250803,
    "MarginTradeType": 0,
    "MarginPremium": None,
    "Details": [
      {
        "SeqNum": 1,
        "ID": "20250803A02S000004",
        "RecType": 1,
        "ExchangeID": "00000000-0000-0000-0000-00000000",
        "State": 3,
        "TransactTime": "2025-08-03T09:45:41.000000+09:00",
        "OrdType": 1,
        "Price": 10.0,
        "Qty": 100,
        "ExecutionID": "E202508030004",
        "ExecutionDay": "2025-08-03T09:46:15+09:00",
        "DelivDay": 20250805,
        "Commission": 0,
        "CommissionTax": 0
      }
    ]
  }
]


position_params = {
    'product': 1,  # Enum値（0: 全て、1: 現物、2: 信用、3: 先物、4: OP）
    'symbol': target_symbol_no_exchange,  # 銘柄コード
    'side': '1',  # Enum値（1: 売、2: 買）
    'addinfo': 'false'  # true: 追加情報を出力する、false: 出力しない
}