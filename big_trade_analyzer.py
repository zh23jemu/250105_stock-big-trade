import os
import pandas as pd
import glob
import random
import tkinter as tk
from tkinter import ttk
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

class BigTradeUI:
    def __init__(self, root):
        self.root = root
        self.root.title("A股大买卖单分析系统")
        self.root.geometry("1200x800")
        
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
        
        # 创建标签页控件
        self.notebook = ttk.Notebook(result_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 创建表格容器，每个市场一个标签页
        self.tables = {}
        self.table_frames = {}
        markets = ['全部股票', '沪市', '深市', '创业板']
        
        for market in markets:
            # 创建标签页框架
            frame = ttk.Frame(self.notebook)
            self.table_frames[market] = frame
            
            # 添加到标签页
            self.notebook.add(frame, text=market)
            
            # 创建滚动条
            scrollbar_y = ttk.Scrollbar(frame, orient=tk.VERTICAL)
            scrollbar_x = ttk.Scrollbar(frame, orient=tk.HORIZONTAL)
            
            # 创建表格
            columns = ('股票代码', '大买单笔数', '大买单总手数', '大卖单笔数', '大卖单总手数', '总成交手数')
            tree = ttk.Treeview(frame, columns=columns, show='headings', 
                               yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
            
            # 设置列宽和对齐方式
            tree.column('股票代码', width=100, anchor=tk.CENTER)
            tree.column('大买单笔数', width=100, anchor=tk.CENTER)
            tree.column('大买单总手数', width=120, anchor=tk.CENTER)
            tree.column('大卖单笔数', width=100, anchor=tk.CENTER)
            tree.column('大卖单总手数', width=120, anchor=tk.CENTER)
            tree.column('总成交手数', width=120, anchor=tk.CENTER)
            
            # 设置列标题
            tree.heading('股票代码', text='股票代码')
            tree.heading('大买单笔数', text='大买单笔数')
            tree.heading('大买单总手数', text='大买单总手数')
            tree.heading('大卖单笔数', text='大卖单笔数')
            tree.heading('大卖单总手数', text='大卖单总手数')
            tree.heading('总成交手数', text='总成交手数')
            
            # 配置滚动条
            scrollbar_y.config(command=tree.yview)
            scrollbar_x.config(command=tree.xview)
            
            # 布局
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
            scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
            tree.pack(fill=tk.BOTH, expand=True)
            
            # 保存表格引用
            self.tables[market] = tree
    
    def load_data(self):
        """加载数据"""
        # 禁用加载按钮
        self.load_btn.config(state=tk.DISABLED)
        self.status_var.set("正在加载数据...")
        
        # 清空所有表格
        for market, tree in self.tables.items():
            for item in tree.get_children():
                tree.delete(item)
        
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
            
            # 显示结果
            self.display_results(results)
            self.status_var.set(f"分析完成！买入阈值：{buy_threshold}手，卖出阈值：{sell_threshold}手")
            
        except ValueError:
            self.status_var.set("请输入有效的整数！")
        except Exception as e:
            self.status_var.set(f"分析出错：{e}")
    
    def display_results(self, results):
        """将结果显示在表格中"""
        # 清空所有表格
        for market, tree in self.tables.items():
            for item in tree.get_children():
                tree.delete(item)
        
        # 填充数据到对应表格
        for market, data in results.items():
            if market in self.tables:
                tree = self.tables[market]
                for stock in data:
                    tree.insert('', tk.END, values=(
                        stock['股票代码'],
                        stock['大买单笔数'],
                        stock['大买单总手数'],
                        stock['大卖单笔数'],
                        stock['大卖单总手数'],
                        stock['总成交手数']
                    ))

if __name__ == "__main__":
    # 创建并运行UI
    root = tk.Tk()
    app = BigTradeUI(root)
    root.mainloop()