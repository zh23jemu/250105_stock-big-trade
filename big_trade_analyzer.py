import os
import pandas as pd
import glob
import random
import tkinter as tk
from tkinter import ttk
import threading
from datetime import datetime
import akshare as ak

# 定义常量
MARKET_MAP = {
    '沪市': lambda code: code.startswith('6') and not code.startswith('68'),
    '科创板': lambda code: code.startswith('68'),
    '深市': lambda code: code.startswith('000'),
    '创业板': lambda code: code.startswith('300') or code.startswith('301')
}

class BigTradeAnalyzer:
    def __init__(self, data_dir, random_sample=0):
        self.data_dir = data_dir
        self.stock_data = {}
        self.market_data = {
            '全部股票': {},
            '沪市主板': {},
            '科创板': {},
            '深市主板': {},
            '创业板': {}
        }
        self.stock_name_cache = {}  # 股票名称缓存，避免重复请求
        self.is_loaded = False
        self.random_sample = random_sample  # 随机选取的股票总数，0表示选取所有股票
    
    def load_data(self, progress_callback=None):
        """加载股票数据，支持按市场类型随机选取"""
        if not os.path.exists(self.data_dir):
            if progress_callback:
                progress_callback(f"错误: 目录 {self.data_dir} 不存在")
            return

        csv_files = glob.glob(os.path.join(self.data_dir, '*.csv'))
        total_files = len(csv_files)
        
        if total_files == 0:
            if progress_callback:
                progress_callback(f"错误: 在 {self.data_dir} 中未找到 CSV 文件")
            return

        # 按市场类型分类股票文件
        market_files = {
            '沪市主板': [],
            '深市主板': [],
            '创业板': [],
            '科创板': []
        }
        
        for file_path in csv_files:
            # 从文件名提取股票代码
            filename = os.path.basename(file_path)
            parts = filename.replace('.csv', '').split('_')
            stock_code = parts[-1]
            
            # 分类到不同市场
            if stock_code.startswith('68'):
                market_files['科创板'].append(file_path)
            elif stock_code.startswith('6'):
                market_files['沪市主板'].append(file_path)
            elif stock_code.startswith('3'):
                market_files['创业板'].append(file_path)
            elif stock_code.startswith('0'):
                market_files['深市主板'].append(file_path)
        
        # 计算主板总数量（沪市主板 + 深市主板）
        mainboard_total = len(market_files['沪市主板']) + len(market_files['深市主板'])
        gem_total = len(market_files['创业板'])
        star_total = len(market_files['科创板'])
        
        if progress_callback:
            progress_callback(f"🔍 共发现 {total_files} 只股票数据")
            progress_callback(f"� 市场分布: 沪市主板 {len(market_files['沪市主板'])} 只, 深市主板 {len(market_files['深市主板'])} 只, 创业板 {gem_total} 只, 科创板 {star_total} 只")
        
        # 根据random_sample参数决定是否随机选取
        selected_files = []
        if self.random_sample > 0:
            # 按比例分配：主板50%，创业板25%，科创板25%
            mainboard_count = int(self.random_sample * 0.5)
            gem_count = int(self.random_sample * 0.25)
            star_count = int(self.random_sample * 0.25)
            
            # 主板再分配到沪市和深市
            if mainboard_total > 0:
                # 按沪市和深市的实际比例分配
                sh_mainboard_ratio = len(market_files['沪市主板']) / mainboard_total
                sh_mainboard_count = int(mainboard_count * sh_mainboard_ratio)
                sz_mainboard_count = mainboard_count - sh_mainboard_count
            else:
                sh_mainboard_count = 0
                sz_mainboard_count = 0
            
            # 随机选取各市场的股票
            if sh_mainboard_count > 0:
                selected_sh = random.sample(market_files['沪市主板'], min(sh_mainboard_count, len(market_files['沪市主板'])))
                selected_files.extend(selected_sh)
            
            if sz_mainboard_count > 0:
                selected_sz = random.sample(market_files['深市主板'], min(sz_mainboard_count, len(market_files['深市主板'])))
                selected_files.extend(selected_sz)
            
            if gem_count > 0:
                selected_gem = random.sample(market_files['创业板'], min(gem_count, len(market_files['创业板'])))
                selected_files.extend(selected_gem)
            
            if star_count > 0:
                selected_star = random.sample(market_files['科创板'], min(star_count, len(market_files['科创板'])))
                selected_files.extend(selected_star)
            
            if progress_callback:
                progress_callback(f"🎲 随机选取 {len(selected_files)} 只股票进行分析")
                progress_callback(f"📋 选取分布: 沪市主板 {len(selected_sh) if 'selected_sh' in locals() else 0} 只, 深市主板 {len(selected_sz) if 'selected_sz' in locals() else 0} 只, 创业板 {len(selected_gem) if 'selected_gem' in locals() else 0} 只, 科创板 {len(selected_star) if 'selected_star' in locals() else 0} 只")
        else:
            # 加载所有股票
            selected_files = csv_files
            if progress_callback:
                progress_callback(f"�📥 开始加载所有 {total_files} 只股票数据")
        
        # 清空旧数据
        self.stock_data = {}
        for market in self.market_data:
            self.market_data[market] = {}

        for i, file_path in enumerate(selected_files):
            # 显示进度
            progress = (i + 1) / len(selected_files) * 100
            if progress_callback:
                progress_callback(f"⏳ 加载进度: {progress:.1f}% ({i+1}/{len(selected_files)})")
            
            # 从文件名提取股票代码
            filename = os.path.basename(file_path)
            # 假设文件名格式包含股票代码，如 deal_600000.csv
            parts = filename.replace('.csv', '').split('_')
            stock_code = parts[-1]
            
            try:
                # 读取CSV文件
                df = pd.read_csv(file_path, delimiter=',')
                
                # 清理列名（去除首尾空格和特殊字符）
                df.columns = df.columns.str.strip()
                
                if 'Volume' not in df.columns or 'Side' not in df.columns or 'Price' not in df.columns:
                    continue

                # 修正Price值：除以100，保留两位小数
                df['Price'] = (df['Price'] / 100).round(2)
                
                # 转换Volume为手数（1手=100股）
                df['Volume_Hand'] = df['Volume'] / 100
                
                # 保存数据
                self.stock_data[stock_code] = df
                
                # 分类到不同市场
                if stock_code.startswith('68'):
                    self.market_data['科创板'][stock_code] = df
                elif stock_code.startswith('6'):
                    self.market_data['沪市主板'][stock_code] = df
                elif stock_code.startswith('3'):
                    self.market_data['创业板'][stock_code] = df
                elif stock_code.startswith('0'):
                    self.market_data['深市主板'][stock_code] = df
                
                # 所有股票都添加到"全部股票"中
                self.market_data['全部股票'][stock_code] = df
                
            except Exception as e:
                if progress_callback:
                    progress_callback(f"⚠️ 处理 {stock_code} 时出错: {e}")
        
        if progress_callback:
            progress_callback("✅ 数据加载完成！")
        self.is_loaded = True
    
    def get_stock_name(self, stock_code):
        """使用akshare获取股票名称，带缓存"""
        if stock_code in self.stock_name_cache:
            return self.stock_name_cache[stock_code]
        
        try:
            # 使用akshare获取所有A股代码和名称
            stock_info = ak.stock_info_a_code_name()
            # 将DataFrame转换为字典，方便查找
            stock_dict = dict(zip(stock_info['code'], stock_info['name']))
            
            # 更新缓存
            self.stock_name_cache = stock_dict
            
            # 获取当前股票名称
            stock_name = stock_dict.get(stock_code, stock_code)
            return stock_name
        except Exception as e:
            print(f"获取股票名称失败: {e}")
            return stock_code
    
    def analyze_big_trades(self, buy_threshold, sell_threshold, buy_amount_threshold=0, sell_amount_threshold=0, 
                          buy_logic='不选', sell_logic='不选', progress_callback=None):
        """分析大买卖单"""
        results = {}
        
        # 计算总股票数量
        total_stocks = sum(len(stocks) for stocks in self.market_data.values())
        processed_stocks = 0
        
        for market, stocks in self.market_data.items():
            market_results = []
            
            for stock_code, df in stocks.items():
                processed_stocks += 1
                
                # 更新进度
                if progress_callback:
                    progress = (processed_stocks / total_stocks) * 100
                    progress_callback(f"🔍 分析中: {market} - {stock_code} ({processed_stocks}/{total_stocks}, {progress:.1f}%)")
                
                # 计算每笔交易的金额
                df['Amount'] = df['Price'] * df['Volume']
                
                # 统计大买单（Side=0 表示主动买入）
                buy_mask = (df['Side'] == 0)
                
                if buy_logic == '与and':
                    buy_mask &= (df['Volume_Hand'] >= buy_threshold) & (df['Amount'] >= buy_amount_threshold)
                elif buy_logic == '或or':
                    buy_mask &= ((df['Volume_Hand'] >= buy_threshold) | (df['Amount'] >= buy_amount_threshold))
                elif buy_logic == '不选':
                    buy_mask &= (df['Volume_Hand'] >= buy_threshold)
                
                big_buys = df[buy_mask]
                
                # 统计大卖单（Side=1 表示主动卖出）
                sell_mask = (df['Side'] == 1)
                
                if sell_logic == '与and':
                    sell_mask &= (df['Volume_Hand'] >= sell_threshold) & (df['Amount'] >= sell_amount_threshold)
                elif sell_logic == '或or':
                    sell_mask &= ((df['Volume_Hand'] >= sell_threshold) | (df['Amount'] >= sell_amount_threshold))
                elif sell_logic == '不选':
                    sell_mask &= (df['Volume_Hand'] >= sell_threshold)
                
                big_sells = df[sell_mask]
                
                # 计算总成交手数
                total_volume = df['Volume_Hand'].sum()
                
                # 计算大买单和大卖单的总手数
                total_big_buy = big_buys['Volume_Hand'].sum()
                total_big_sell = big_sells['Volume_Hand'].sum()
                
                # 计算大买单和大卖单的总金额（金额 = 价格 * 成交量）
                # 注意：Volume是股数，1手=100股，所以总金额 = 价格 * Volume
                # 转换为万元单位（保留两位小数）
                total_big_buy_amount = (big_buys['Price'] * big_buys['Volume']).sum() / 10000
                total_big_sell_amount = (big_sells['Price'] * big_sells['Volume']).sum() / 10000
                
                # 计算大买单和大卖单的笔数
                count_big_buy = len(big_buys)
                count_big_sell = len(big_sells)
                
                # 如果有大买单或大卖单，添加到结果中
                if count_big_buy > 0 or count_big_sell > 0:
                    # 获取股票名称，默认使用代码
                    stock_name = self.get_stock_name(stock_code)
                    
                    # 保存详细的大单交易记录
                    big_trades = {
                        'buys': big_buys.to_dict('records'),
                        'sells': big_sells.to_dict('records')
                    }
                    
                    market_results.append({
                        '股票代码': stock_code,
                        '股票名称': stock_name,
                        '大买单笔数': count_big_buy,
                        '大买单总手数': round(total_big_buy, 2),
                        '大买单总金额': round(total_big_buy_amount, 2),
                        '大卖单笔数': count_big_sell,
                        '大卖单总手数': round(total_big_sell, 2),
                        '大卖单总金额': round(total_big_sell_amount, 2),
                        '总成交手数': round(total_volume, 2),
                        'big_trades': big_trades  # 保存详细的大单交易记录
                    })
            
            # 按大买单总手数降序排序
            market_results.sort(key=lambda x: (x['大买单总手数'], x['大卖单总手数']), reverse=True)
            results[market] = market_results
        
        return results

class BigTradeUI:
    def __init__(self, root, random_sample=0):
        self.root = root
        self.root.title("A股大买卖单分析系统 v2.0")
        self.root.geometry("1300x850")
        
        # 默认模式为深色
        self.dark_mode = True
        
        # 颜色方案
        self.colors = {
            'dark': {
                'bg': '#1e1e1e',
                'fg': '#e0e0e0',
                'header_bg': '#2d2d2d',
                'accent': '#007acc',
                'accent_hover': '#005a9e',
                'row_alt': '#252526',
                'border': '#333333',
                'input_bg': '#3c3c3c',
                'status_blue': '#4fc3f7',
                'status_green': '#81c784',
                'status_red': '#e57373'
            },
            'light': {
                'bg': '#ffffff',
                'fg': '#333333',
                'header_bg': '#f3f3f3',
                'accent': '#0066cc',
                'accent_hover': '#0052a3',
                'row_alt': '#fafafa',
                'border': '#cccccc',
                'input_bg': '#ffffff',
                'status_blue': '#0066cc',
                'status_green': '#2e7d32',
                'status_red': '#c62828'
            }
        }
        
        # 初始化分析器
        self.analyzer = BigTradeAnalyzer('deal_20251231', random_sample=random_sample)
        
        # 应用样式
        self.style = ttk.Style()
        self.apply_styles()
        
        # 创建UI组件
        self.create_widgets()
        
        # 初始刷新样式
        self.update_theme_colors()

    def apply_styles(self):
        """配置通用样式"""
        # 使用 clam 主题以获得更好的跨平台颜色自定义支持
        try:
            self.style.theme_use('clam')
        except:
            pass
            
        font_main = ("Microsoft YaHei", 10)
        font_bold = ("Microsoft YaHei", 10, "bold")
        font_header = ("Microsoft YaHei", 11, "bold")
        
        self.root.option_add("*Font", font_main)
        
        # Treeview 样式基础配置
        self.style.configure("Treeview", font=font_main, rowheight=30)
        self.style.configure("Treeview.Heading", font=font_header)
        
        # Notebook 样式
        self.style.configure("TNotebook", padding=2)
        self.style.configure("TNotebook.Tab", padding=[20, 5], font=font_bold)
        
        # 标签框架样式
        self.style.configure("TLabelframe", padding=10)
        self.style.configure("TLabelframe.Label", font=font_bold)

    def update_theme_colors(self):
        """根据当前模式更新所有颜色"""
        theme = 'dark' if self.dark_mode else 'light'
        c = self.colors[theme]
        
        # 更新根窗口
        self.root.configure(bg=c['bg'])
        
        # 通用组件样式配置
        styles = {
            "TFrame": {"background": c['bg']},
            "TLabelframe": {"background": c['bg'], "foreground": c['border']}, # 边框颜色
            "TLabelframe.Label": {"background": c['bg'], "foreground": c['accent']},
            "TLabel": {"background": c['bg'], "foreground": c['fg']},
            "TEntry": {
                "fieldbackground": c['input_bg'], 
                "background": c['input_bg'],
                "foreground": c['fg'],
                "insertcolor": c['fg'], # 光标颜色
                "bordercolor": c['border'],
                "lightcolor": c['border']
            },
            "TButton": {
                "background": c['header_bg'],
                "foreground": c['fg'],
                "bordercolor": c['border'],
                "padding": 5
            },
            "Accent.TButton": {
                "background": c['accent'],
                "foreground": "white",
                "padding": 5
            },
            "TNotebook": {
                "background": c['bg'],
                "bordercolor": c['border'],
                "darkcolor": c['bg'],
                "lightcolor": c['bg']
            },
            "TNotebook.Tab": {
                "background": c['header_bg'],
                "foreground": c['fg'],
                "bordercolor": c['border'],
                "lightcolor": c['bg']
            },
            "Treeview": {
                "background": c['bg'],
                "foreground": c['fg'],
                "fieldbackground": c['bg'],
                "bordercolor": c['border'],
                "lightcolor": c['bg'],
                "darkcolor": c['bg']
            },
            "Treeview.Heading": {
                "background": c['header_bg'],
                "foreground": c['fg'],
                "bordercolor": c['border'],
                "relief": "flat"
            }
        }

        # 应用所有配置
        for style_name, config in styles.items():
            self.style.configure(style_name, **config)

        # 特殊映射配置 (状态切换)
        self.style.map("TButton", 
            background=[('active', c['border']), ('disabled', c['bg'])],
            foreground=[('disabled', '#888888')])

        self.style.map("Accent.TButton", 
            background=[('active', c['accent_hover']), ('disabled', c['header_bg'])])

        self.style.map("TNotebook.Tab",
            background=[('selected', c['accent']), ('active', c['accent_hover'])],
            foreground=[('selected', 'white')])

        self.style.map("Treeview",
            background=[('selected', c['accent'])],
            foreground=[('selected', 'white')])
            
        self.style.map("TEntry",
            bordercolor=[('focus', c['accent'])],
            lightcolor=[('focus', c['accent'])])

        # 更新标题和状态标签
        if hasattr(self, 'title_label'):
            self.title_label.configure(bg=c['bg'], fg=c['accent'])
        if hasattr(self, 'status_label'):
            self.status_label.configure(foreground=c['status_blue'] if self.dark_mode else c['accent'])
        
        # 刷新所有表格标签颜色
        if hasattr(self, 'tables'):
            for tree in self.tables.values():
                self.refresh_tree_tags(tree)

    def toggle_theme(self):
        """切换深色/浅色模式"""
        self.dark_mode = not self.dark_mode
        self.theme_btn.config(text="🌙 深色模式" if not self.dark_mode else "☀️ 浅色模式")
        self.update_theme_colors()

    def refresh_tree_tags(self, tree):
        """刷新表格的交替行颜色"""
        theme = 'dark' if self.dark_mode else 'light'
        c = self.colors[theme]
        
        # 交替行颜色
        tree.tag_configure('oddrow', background=c['bg'], foreground=c['fg'])
        tree.tag_configure('evenrow', background=c['row_alt'], foreground=c['fg'])
        
        # 金额颜色标签
        tree.tag_configure('buy_amount', foreground=c['status_red'])  # 大买单金额红色
        tree.tag_configure('sell_amount', foreground=c['status_green'])  # 大卖单金额绿色


    def create_widgets(self):
        """创建UI组件"""
        # 创建主框架
        self.main_frame = ttk.Frame(self.root, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 顶部标题和模式切换
        header_frame = ttk.Frame(self.main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        title_label = tk.Label(header_frame, text="📊 A股大买卖单分析系统", 
                             font=("Microsoft YaHei", 18, "bold"), 
                             bg=self.colors['dark']['bg'], fg=self.colors['dark']['accent'])
        title_label.pack(side=tk.LEFT)
        self.title_label = title_label # 保存引用以便更新颜色
        
        self.theme_btn = ttk.Button(header_frame, text="☀️ 浅色模式", command=self.toggle_theme)
        self.theme_btn.pack(side=tk.RIGHT)
        
        # 控制和设置区域 (放在一行)
        top_panels = ttk.Frame(self.main_frame)
        top_panels.pack(fill=tk.X, pady=5)
        
        # 加载数据面板
        load_frame = ttk.LabelFrame(top_panels, text="文件操作", padding="15")
        load_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        self.load_btn = ttk.Button(load_frame, text="📂 加载原始成交数据", command=self.load_data, style="Accent.TButton")
        self.load_btn.pack(pady=5)
        
        self.status_var = tk.StringVar(value="准备就绪")
        self.status_label = ttk.Label(load_frame, textvariable=self.status_var, wraplength=200)
        self.status_label.pack(pady=5)
        
        # 参数设置面板
        params_frame = ttk.LabelFrame(top_panels, text="分析参数设置", padding="15")
        params_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        grid_frame = ttk.Frame(params_frame)
        grid_frame.pack(expand=True)
        
        # 买入参数设置
        ttk.Label(grid_frame, text="买入阈值 (手):").grid(row=0, column=0, padx=10, pady=5, sticky=tk.E)
        self.buy_threshold = tk.StringVar(value="5000")
        buy_entry = ttk.Entry(grid_frame, textvariable=self.buy_threshold, width=15)
        buy_entry.grid(row=0, column=1, padx=10, pady=5)
        
        ttk.Label(grid_frame, text="买入金额阈值 (万元):").grid(row=1, column=0, padx=10, pady=5, sticky=tk.E)
        self.buy_amount_threshold = tk.StringVar(value="0")
        buy_amount_entry = ttk.Entry(grid_frame, textvariable=self.buy_amount_threshold, width=15)
        buy_amount_entry.grid(row=1, column=1, padx=10, pady=5)
        
        ttk.Label(grid_frame, text="买入条件关系:").grid(row=2, column=0, padx=10, pady=5, sticky=tk.E)
        self.buy_logic = tk.StringVar(value="不选")
        buy_logic_combo = ttk.Combobox(grid_frame, textvariable=self.buy_logic, values=["不选", "与and", "或or"], width=13, state="readonly")
        buy_logic_combo.grid(row=2, column=1, padx=10, pady=5)
        
        # 卖出参数设置
        ttk.Label(grid_frame, text="卖出阈值 (手):").grid(row=0, column=2, padx=10, pady=5, sticky=tk.E)
        self.sell_threshold = tk.StringVar(value="5000")
        sell_entry = ttk.Entry(grid_frame, textvariable=self.sell_threshold, width=15)
        sell_entry.grid(row=0, column=3, padx=10, pady=5)
        
        ttk.Label(grid_frame, text="卖出金额阈值 (万元):").grid(row=1, column=2, padx=10, pady=5, sticky=tk.E)
        self.sell_amount_threshold = tk.StringVar(value="0")
        sell_amount_entry = ttk.Entry(grid_frame, textvariable=self.sell_amount_threshold, width=15)
        sell_amount_entry.grid(row=1, column=3, padx=10, pady=5)
        
        ttk.Label(grid_frame, text="卖出条件关系:").grid(row=2, column=2, padx=10, pady=5, sticky=tk.E)
        self.sell_logic = tk.StringVar(value="不选")
        sell_logic_combo = ttk.Combobox(grid_frame, textvariable=self.sell_logic, values=["不选", "与and", "或or"], width=13, state="readonly")
        sell_logic_combo.grid(row=2, column=3, padx=10, pady=5)
        
        self.analyze_btn = ttk.Button(grid_frame, text="🚀 开始扫描分析", command=self.analyze_data, style="Accent.TButton")
        self.analyze_btn.grid(row=1, column=4, padx=20, pady=5, rowspan=2)
        
        # 结果显示区域
        result_frame = ttk.LabelFrame(self.main_frame, text="多维度分析结果", padding="5")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=(15, 0))
        
        # 创建标签页控件
        self.notebook = ttk.Notebook(result_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 创建表格容器
        self.tables = {}
        markets = [('全部股票', '🌐'), ('沪市主板', '🏛️'), ('深市主板', '🏙️'), ('创业板', '🚀'), ('科创板', '🔬')]
        
        for market_name, emoji in markets:
            # 创建标签页框架
            frame = ttk.Frame(self.notebook, padding=5)
            self.notebook.add(frame, text=f"{emoji} {market_name}")
            
            # 创建表格和滚动条容器
            table_container = ttk.Frame(frame)
            table_container.pack(fill=tk.BOTH, expand=True)
            
            # 创建表格
            columns = ('股票代码', '股票名称', '大买单笔数', '大买单总手数', '大买单总金额', '大卖单笔数', '大卖单总手数', '大卖单总金额', '总成交手数', '大单总额', '大单净额', '大单买卖比')
            tree = ttk.Treeview(table_container, columns=columns, show='headings', selectmode='browse')
            
            # 设置列宽和对齐方式
            tree.column('股票代码', width=120, anchor=tk.CENTER)
            tree.column('股票名称', width=150, anchor=tk.CENTER)
            tree.column('大买单笔数', width=120, anchor=tk.CENTER)
            tree.column('大买单总手数', width=150, anchor=tk.CENTER)
            tree.column('大买单总金额', width=180, anchor=tk.CENTER)
            tree.column('大卖单笔数', width=120, anchor=tk.CENTER)
            tree.column('大卖单总手数', width=150, anchor=tk.CENTER)
            tree.column('大卖单总金额', width=180, anchor=tk.CENTER)
            tree.column('总成交手数', width=150, anchor=tk.CENTER)
            tree.column('大单总额', width=150, anchor=tk.CENTER)
            tree.column('大单净额', width=150, anchor=tk.CENTER)
            tree.column('大单买卖比', width=120, anchor=tk.CENTER)
            
            # 设置列标题
            for col in columns:
                tree.heading(col, text=col, command=lambda _col=col, _tree=tree: self.sort_column(_tree, _col, False))
            
            # 滚动条
            scrollbar_y = ttk.Scrollbar(table_container, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar_y.set)
            
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
            tree.pack(fill=tk.BOTH, expand=True)
            
            # 保存表格引用
            self.tables[market_name] = tree
            self.refresh_tree_tags(tree)

    def sort_column(self, tree, col, reverse):
        """表格点击标题排序"""
        l = [(tree.set(k, col), k) for k in tree.get_children('')]
        
        # 尝试转换为数字进行排序
        try:
            # 处理数值字符串：移除千分位分隔符、百分号和万元单位
            l.sort(key=lambda t: float(t[0].replace(',', '').replace('%', '').replace('万元', '')), reverse=reverse)
        except ValueError:
            # 回退到字符串排序
            l.sort(reverse=reverse)

        for index, (val, k) in enumerate(l):
            tree.move(k, '', index)
            # 更新交替行颜色
            tree.item(k, tags=('evenrow' if index % 2 == 0 else 'oddrow'))
        
        # 反向排序逻辑
        tree.heading(col, command=lambda: self.sort_column(tree, col, not reverse))

    def load_data(self):
        """加载数据"""
        self.load_btn.config(state=tk.DISABLED)
        self.analyze_btn.config(state=tk.DISABLED)
        
        # 清空所有表格
        for tree in self.tables.values():
            for item in tree.get_children():
                tree.delete(item)
        
        def load_thread():
            self.analyzer.load_data(progress_callback=self.update_status)
            self.root.after(0, self.on_load_complete)
        
        thread = threading.Thread(target=load_thread)
        thread.daemon = True
        thread.start()
    
    def on_load_complete(self):
        """加载完成后的回调"""
        self.load_btn.config(state=tk.NORMAL)
        self.analyze_btn.config(state=tk.NORMAL)
        if self.analyzer.is_loaded:
            self.status_var.set("✅ 数据就绪，可以开始分析")
    
    def update_status(self, message):
        """更新状态信息"""
        self.root.after(0, lambda: self.status_var.set(message))
        # 根据消息类型改变颜色 (简易判断)
        if "错误" in message or "⚠️" in message:
            color = self.colors['dark' if self.dark_mode else 'light']['status_red']
        elif "完成" in message or "✅" in message:
            color = self.colors['dark' if self.dark_mode else 'light']['status_green']
        else:
            color = self.colors['dark' if self.dark_mode else 'light']['status_blue']
        self.root.after(0, lambda: self.status_label.configure(foreground=color))

    def analyze_data(self):
        """分析数据"""
        if not self.analyzer.is_loaded:
            self.update_status("⚠️ 请先加载数据！")
            return
        
        try:
            buy_threshold = int(self.buy_threshold.get())
            sell_threshold = int(self.sell_threshold.get())
            
            if not (1 <= buy_threshold <= 20000 and 1 <= sell_threshold <= 20000):
                self.update_status("⚠️ 阈值范围: 1-20000手")
                return
            
            # 禁用按钮防止重复点击
            self.analyze_btn.config(state=tk.DISABLED)
            self.load_btn.config(state=tk.DISABLED)
            
            def analyze_thread():
                """分析线程"""
                try:
                    # 获取金额阈值（万元）并转换为元
                    buy_amount_threshold = float(self.buy_amount_threshold.get()) * 10000
                    sell_amount_threshold = float(self.sell_amount_threshold.get()) * 10000
                    
                    # 获取逻辑关系
                    buy_logic = self.buy_logic.get()
                    sell_logic = self.sell_logic.get()
                    
                    results = self.analyzer.analyze_big_trades(
                        buy_threshold, sell_threshold, 
                        buy_amount_threshold, sell_amount_threshold,
                        buy_logic, sell_logic,
                        progress_callback=self.update_status
                    )
                    self.root.after(0, lambda: self.on_analyze_complete(results, buy_threshold, sell_threshold))
                except ValueError as e:
                    self.root.after(0, lambda: self.update_status(f"⚠️ 参数错误: {e}"))
                    self.root.after(0, self.on_analyze_error)
                except Exception as e:
                    self.root.after(0, lambda: self.update_status(f"⚠️ 分析出错: {e}"))
                    self.root.after(0, self.on_analyze_error)
            
            # 启动分析线程
            thread = threading.Thread(target=analyze_thread)
            thread.daemon = True
            thread.start()
            
        except ValueError:
            self.update_status("⚠️ 请输入有效的整数阈值")
        except Exception as e:
            self.update_status(f"⚠️ 分析出错: {e}")
    
    def on_analyze_complete(self, results, buy_threshold, sell_threshold):
        """分析完成后的回调"""
        self.display_results(results)
        self.update_status(f"✅ 分析完成 (买:{buy_threshold}/卖:{sell_threshold})")
        self.analyze_btn.config(state=tk.NORMAL)
        self.load_btn.config(state=tk.NORMAL)
    
    def on_analyze_error(self):
        """分析出错后的回调"""
        self.analyze_btn.config(state=tk.NORMAL)
        self.load_btn.config(state=tk.NORMAL)
    
    def display_results(self, results):
        """将结果显示在表格中，支持二级列表查看详细交易"""
        for market, tree in self.tables.items():
            # 清空表格
            for item in tree.get_children():
                tree.delete(item)
            
            if market in results:
                for i, stock in enumerate(results[market]):
                    # 计算大单买卖比 (买入总金额 / 卖出总金额)
                    ratio = "N/A"
                    if stock['大卖单总金额'] > 0:
                        ratio = f"{stock['大买单总金额'] / stock['大卖单总金额']:.2f}"
                    elif stock['大买单总金额'] > 0:
                        ratio = "∞"
                    
                    # 计算大单总额和大单净额
                    total_amount = stock['大买单总金额'] + stock['大卖单总金额']
                    net_amount = stock['大买单总金额'] - stock['大卖单总金额']
                    
                    tag = 'evenrow' if i % 2 == 0 else 'oddrow'
                    
                    # 插入主节点（股票汇总信息）
                    main_item = tree.insert('', tk.END, values=(
                        stock['股票代码'],
                        stock['股票名称'],
                        stock['大买单笔数'],
                        f"{stock['大买单总手数']:,.0f}",
                        f"{stock['大买单总金额']:,.0f}万元",
                        stock['大卖单笔数'],
                        f"{stock['大卖单总手数']:,.0f}",
                        f"{stock['大卖单总金额']:,.0f}万元",
                        f"{stock['总成交手数']:,.0f}",
                        f"{total_amount:,.0f}万元",
                        f"{net_amount:,.0f}万元",
                        ratio
                    ), tags=(tag, 'buy_amount', 'sell_amount'))
                    
                    # 插入子节点（详细买单）
                    if stock['big_trades']['buys']:
                        # 买单汇总节点
                        buy_summary_item = tree.insert(main_item, tk.END, values=(
                            '', '买单详情', f"共{len(stock['big_trades']['buys'])}笔", '', '', '', '', '', '', '', '', ''
                        ), tags=('buy_summary',))
                        
                        # 买单明细节点
                        for trade in stock['big_trades']['buys']:
                            # 计算交易金额（万元）
                            trade_amount = (trade['Price'] * trade['Volume']) / 10000
                            tree.insert(buy_summary_item, tk.END, values=(
                                '', f"{trade['DealTime']}", f"手数: {trade['Volume_Hand']:.0f}", 
                                f"价格: {trade['Price']:.2f}", f"金额: {trade_amount:,.0f}万元", 
                                '', '', '', '', '', '', ''
                            ), tags=('trade_detail', 'buy_amount'))
                    
                    # 插入子节点（详细卖单）
                    if stock['big_trades']['sells']:
                        # 卖单汇总节点
                        sell_summary_item = tree.insert(main_item, tk.END, values=(
                            '', '卖单详情', f"共{len(stock['big_trades']['sells'])}笔", '', '', '', '', '', '', '', '', ''
                        ), tags=('sell_summary',))
                        
                        # 卖单明细节点
                        for trade in stock['big_trades']['sells']:
                            # 计算交易金额（万元）
                            trade_amount = (trade['Price'] * trade['Volume']) / 10000
                            tree.insert(sell_summary_item, tk.END, values=(
                                '', f"{trade['DealTime']}", f"手数: {trade['Volume_Hand']:.0f}", 
                                f"价格: {trade['Price']:.2f}", f"金额: {trade_amount:,.0f}万元", 
                                '', '', '', '', '', '', ''
                            ), tags=('trade_detail', 'sell_amount'))
                    
                    # 设置主节点的交替行颜色
                    tree.item(main_item, tags=(tag,))
                    
                    # 获取当前主题的颜色配置
                    theme = 'dark' if self.dark_mode else 'light'
                    c = self.colors[theme]
                    
                    # 为大买单总金额和大卖单总金额列应用颜色
                    # 注意：Treeview的标签是应用于整行的，我们需要创建一个自定义渲染方法来为单个单元格着色
                    # 这里我们使用一个技巧：将大买单和大卖单金额分别放在不同的行中，或者使用自定义标签
                    # 由于Treeview的限制，我们只能通过修改单元格的文本颜色来实现
                    # 这里我们将使用tag_configure来设置颜色，并在insert时应用标签
                    
                    # 重新配置tree的标签，确保颜色正确
                    self.refresh_tree_tags(tree)

if __name__ == "__main__":
    import argparse
    
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description="A股大买卖单分析系统")
    parser.add_argument("--random-sample", type=int, default=0, help="随机选取的股票总数，0表示选取所有股票")
    
    # 解析参数
    args = parser.parse_args()
    
    # 设置 DPI 感知以保证在 Windows 高分屏下不模糊
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
        
    root = tk.Tk()
    app = BigTradeUI(root, random_sample=args.random_sample)
    
    # 窗口标题美化
    root.title("A股顶级机构大单异动监控系统")
    
    root.mainloop()

