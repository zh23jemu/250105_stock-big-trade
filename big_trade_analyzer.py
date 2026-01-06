import os
import pandas as pd
import glob
import random
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading

# 定义常量
MARKET_MAP = {
    '沪市': lambda code: code.startswith('6'),
    '深市': lambda code: code.startswith('000'),
    '创业板': lambda code: code.startswith('300') or code.startswith('301')
}

class BigTradeAnalyzer:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.stock_data = {}
        self.market_data = {
            '全部股票': {},
            '沪市': {},
            '深市': {},
            '创业板': {}
        }
        self.is_loaded = False
    
    def load_data(self, progress_callback=None):
        """加载随机500只股票数据"""
        csv_files = glob.glob(os.path.join(self.data_dir, '*.csv'))
        total_files = len(csv_files)
        
        # 随机选择500只股票
        sample_size = min(500, total_files)
        selected_files = random.sample(csv_files, sample_size)
        
        if progress_callback:
            progress_callback(f"共发现 {total_files} 只股票数据")
            progress_callback(f"随机选择 {sample_size} 只股票进行分析")
        
        for i, file_path in enumerate(selected_files):
            # 显示进度
            progress = (i + 1) / sample_size * 100
            if progress_callback:
                progress_callback(f"加载进度: {progress:.1f}% ({i+1}/{sample_size})")
            
            # 从文件名提取股票代码
            filename = os.path.basename(file_path)
            stock_code = filename.split('_')[-1].split('.')[0]
            
            try:
                # 读取CSV文件
                df = pd.read_csv(file_path, delimiter=',')
                
                # 清理列名（去除首尾空格和特殊字符）
                df.columns = df.columns.str.strip()
                
                # 转换Volume为手数（1手=100股）
                df['Volume_Hand'] = df['Volume'] / 100
                
                # 保存数据
                self.stock_data[stock_code] = df
                
                # 分类到不同市场
                # 沪市：6开头
                # 深市：0开头（不含创业板）
                # 创业板：3开头
                if stock_code.startswith('6'):
                    self.market_data['沪市'][stock_code] = df
                elif stock_code.startswith('3'):
                    self.market_data['创业板'][stock_code] = df
                elif stock_code.startswith('0'):
                    self.market_data['深市'][stock_code] = df
                # 所有股票都添加到"全部股票"中
                self.market_data['全部股票'][stock_code] = df
                
            except Exception as e:
                if progress_callback:
                    progress_callback(f"处理文件 {file_path} 时出错: {e}")
        
        if progress_callback:
            progress_callback("数据加载完成！")
        self.is_loaded = True
    
    def analyze_big_trades(self, buy_threshold, sell_threshold):
        """分析大买卖单"""
        results = {}
        
        for market, stocks in self.market_data.items():
            market_results = []
            
            for stock_code, df in stocks.items():
                # 统计大买单（Side=1 或其他表示主动买的标识）
                # 根据数据观察，Side=1 是主动买，Side=-1/-11 是主动卖
                big_buys = df[(df['Side'] == 1) & (df['Volume_Hand'] >= buy_threshold)]
                big_sells = df[(df['Side'].isin([-1, -11])) & (df['Volume_Hand'] >= sell_threshold)]
                
                # 计算总成交手数
                total_volume = df['Volume_Hand'].sum()
                
                # 计算大买单和大卖单的总手数
                total_big_buy = big_buys['Volume_Hand'].sum()
                total_big_sell = big_sells['Volume_Hand'].sum()
                
                # 计算大买单和大卖单的笔数
                count_big_buy = len(big_buys)
                count_big_sell = len(big_sells)
                
                # 如果有大买单或大卖单，添加到结果中
                if count_big_buy > 0 or count_big_sell > 0:
                    market_results.append({
                        '股票代码': stock_code,
                        '大买单笔数': count_big_buy,
                        '大买单总手数': round(total_big_buy, 2),
                        '大卖单笔数': count_big_sell,
                        '大卖单总手数': round(total_big_sell, 2),
                        '总成交手数': round(total_volume, 2)
                    })
            
            # 按大买单总手数降序排序
            market_results.sort(key=lambda x: (x['大买单总手数'], x['大卖单总手数']), reverse=True)
            results[market] = market_results
        
        return results
    
    def format_results(self, results, buy_threshold, sell_threshold):
        """格式化结果为字符串"""
        output = []
        output.append("=" * 80)
        output.append(f"大买卖单分析结果（买入阈值：{buy_threshold}手，卖出阈值：{sell_threshold}手）")
        output.append("=" * 80)
        
        for market, data in results.items():
            output.append(f"\n{market}（共{len(data)}只股票）")
            output.append("-" * 80)
            output.append(f"{'股票代码':<10} {'大买单笔数':<10} {'大买单总手数':<12} {'大卖单笔数':<10} {'大卖单总手数':<12} {'总成交手数':<15}")
            output.append("-" * 80)
            
            for stock in data:
                output.append(f"{stock['股票代码']:<10} {stock['大买单笔数']:<10} {stock['大买单总手数']:<12} {stock['大卖单笔数']:<10} {stock['大卖单总手数']:<12} {stock['总成交手数']:<15}")
            
            output.append("-" * 80)
        
        return "\n".join(output)

class BigTradeUI:
    def __init__(self, root):
        self.root = root
        self.root.title("A股大买卖单分析系统")
        self.root.geometry("1000x700")
        
        # 初始化分析器
        self.analyzer = BigTradeAnalyzer('deal_20251231')
        
        # 创建UI组件
        self.create_widgets()
    
    def create_widgets(self):
        """创建UI组件"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 顶部控制区域
        control_frame = ttk.LabelFrame(main_frame, text="控制选项", padding="10")
        control_frame.pack(fill=tk.X, pady=5)
        
        # 加载数据按钮
        self.load_btn = ttk.Button(control_frame, text="加载数据", command=self.load_data)
        self.load_btn.pack(side=tk.LEFT, padx=5)
        
        # 状态标签
        self.status_var = tk.StringVar(value="等待加载数据...")
        status_label = ttk.Label(control_frame, textvariable=self.status_var, foreground="blue")
        status_label.pack(side=tk.LEFT, padx=10)
        
        # 参数设置区域
        params_frame = ttk.LabelFrame(main_frame, text="参数设置", padding="10")
        params_frame.pack(fill=tk.X, pady=5)
        
        # 买入阈值
        ttk.Label(params_frame, text="买入阈值（1-10000手）：").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.buy_threshold = tk.StringVar(value="5000")
        buy_entry = ttk.Entry(params_frame, textvariable=self.buy_threshold, width=10)
        buy_entry.grid(row=0, column=1, padx=5, pady=5)
        
        # 卖出阈值
        ttk.Label(params_frame, text="卖出阈值（1-10000手）：").grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        self.sell_threshold = tk.StringVar(value="5000")
        sell_entry = ttk.Entry(params_frame, textvariable=self.sell_threshold, width=10)
        sell_entry.grid(row=0, column=3, padx=5, pady=5)
        
        # 分析按钮
        analyze_btn = ttk.Button(params_frame, text="开始分析", command=self.analyze_data)
        analyze_btn.grid(row=0, column=4, padx=10, pady=5)
        
        # 结果显示区域
        result_frame = ttk.LabelFrame(main_frame, text="分析结果", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 结果文本框
        self.result_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD, font=('Consolas', 10))
        self.result_text.pack(fill=tk.BOTH, expand=True)
    
    def load_data(self):
        """加载数据"""
        # 禁用加载按钮
        self.load_btn.config(state=tk.DISABLED)
        self.status_var.set("正在加载数据...")
        
        # 清空结果
        self.result_text.delete(1.0, tk.END)
        
        # 在后台线程中加载数据
        def load_thread():
            self.analyzer.load_data(progress_callback=self.update_status)
            self.analyzer.is_loaded = True
            self.root.after(0, lambda: self.load_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.status_var.set("数据加载完成！"))
        
        thread = threading.Thread(target=load_thread)
        thread.daemon = True
        thread.start()
    
    def update_status(self, message):
        """更新状态信息"""
        self.root.after(0, lambda: self.status_var.set(message))
        self.result_text.insert(tk.END, message + "\n")
        self.result_text.see(tk.END)
    
    def analyze_data(self):
        """分析数据"""
        if not self.analyzer.is_loaded:
            self.status_var.set("请先加载数据！")
            return
        
        try:
            # 获取阈值
            buy_threshold = int(self.buy_threshold.get())
            sell_threshold = int(self.sell_threshold.get())
            
            # 验证阈值范围
            if not (1 <= buy_threshold <= 10000 and 1 <= sell_threshold <= 10000):
                self.status_var.set("阈值必须在1-10000手之间！")
                return
            
            # 分析数据
            self.status_var.set("正在分析数据...")
            results = self.analyzer.analyze_big_trades(buy_threshold, sell_threshold)
            
            # 格式化并显示结果
            formatted_results = self.analyzer.format_results(results, buy_threshold, sell_threshold)
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, formatted_results)
            self.status_var.set("分析完成！")
            
        except ValueError:
            self.status_var.set("请输入有效的整数！")
        except Exception as e:
            self.status_var.set(f"分析出错：{e}")

if __name__ == "__main__":
    # 创建并运行UI
    root = tk.Tk()
    app = BigTradeUI(root)
    root.mainloop()