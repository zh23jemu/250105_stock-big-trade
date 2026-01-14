import os
import pandas as pd
import glob

def find_max_hand_in_gem():
    """查找科创板股票中最大手数的股票"""
    data_dir = 'deal_20251231'
    csv_files = glob.glob(os.path.join(data_dir, '*.csv'))
    
    max_hand = 0
    max_hand_stock = None
    max_hand_details = {}
    
    print(f"🔍 开始分析科创板股票最大手数...")
    
    # 遍历所有CSV文件
    for file_path in csv_files:
        # 从文件名提取股票代码
        filename = os.path.basename(file_path)
        parts = filename.replace('.csv', '').split('_')
        stock_code = parts[-1]
        
        # 只处理科创板股票（68开头）
        if not stock_code.startswith('68'):
            continue
        
        try:
            # 读取CSV文件
            df = pd.read_csv(file_path, delimiter=',')
            
            # 清理列名
            df.columns = df.columns.str.strip()
            
            if 'Volume' not in df.columns:
                continue
            
            # 计算最大手数（1手=100股）
            df['Volume_Hand'] = df['Volume'] / 100
            max_stock_hand = df['Volume_Hand'].max()
            
            # 记录最大手数的行
            max_row = df[df['Volume_Hand'] == max_stock_hand].iloc[0]
            
            # 更新全局最大值
            if max_stock_hand > max_hand:
                max_hand = max_stock_hand
                max_hand_stock = stock_code
                max_hand_details = {
                    'price': max_row['Price'],
                    'volume': max_row['Volume'],
                    'volume_hand': max_stock_hand,
                    'deal_time': max_row['DealTime'],
                    'trading_day': max_row['TradingDay'],
                    'side': max_row['Side']
                }
            
            print(f"📊 处理股票: {stock_code}，最大手数: {max_stock_hand:.2f}")
            
        except Exception as e:
            print(f"⚠️ 处理 {stock_code} 时出错: {e}")
            continue
    
    if max_hand_stock:
        print(f"\n🎉 找到科创板最大手数股票！")
        print(f"📈 股票代码: {max_hand_stock}")
        print(f"📊 最大手数: {max_hand_details['volume_hand']:.2f} 手")
        print(f"💵 成交价格: {max_hand_details['price']:.2f} 元")
        print(f"📋 成交股数: {max_hand_details['volume']:.0f} 股")
        print(f"⏰ 成交时间: {max_hand_details['deal_time']}")
        print(f"📅 交易日: {max_hand_details['trading_day']}")
        print(f"📌 成交方向: {'买入' if max_hand_details['side'] == 1 else '卖出' if max_hand_details['side'] in [-1, -11] else '未知'}")
    else:
        print("❌ 未找到科创板股票数据")

if __name__ == "__main__":
    find_max_hand_in_gem()
