import os
import pandas as pd
import glob
import random
import tkinter as tk
from tkinter import ttk
import threading
from datetime import datetime
import akshare as ak
import sqlite3

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
        
        # 初始化SQLite数据库
        self.db_path = 'stock_names.db'
        self.init_database()
        self.load_stock_names_from_db()
    
    def init_database(self):
        """初始化数据库，创建股票名称表和自选股表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建股票名称表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_names (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建自选股表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_name TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                FOREIGN KEY (stock_code) REFERENCES stock_names(code),
                UNIQUE(portfolio_name, stock_code)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def load_stock_names_from_db(self):
        """从数据库加载股票名称到缓存"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT code, name FROM stock_names')
        rows = cursor.fetchall()
        
        # 更新缓存
        for code, name in rows:
            self.stock_name_cache[code] = name
        
        conn.close()
    
    def import_portfolio(self, portfolio_name, file_path):
        """从xls文件导入自选股到数据库"""
        try:
            # 检查文件扩展名，只允许xls格式
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext != '.xls':
                return False, "只支持.xls格式文件导入"
            
            stock_codes = []
            
            # 读取文件，支持多种编码格式
            encodings = ['utf-8', 'gbk', 'gb2312', 'ansi']
            file_content = None
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        file_content = f.readlines()
                    break
                except UnicodeDecodeError:
                    continue
            
            if file_content is None:
                return False, "无法识别文件编码"
            
            # 解析文件内容
            for line in file_content:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # 按制表符分割，取第一列作为股票代码
                parts = line.split('\t')
                if parts:
                    stock_code = parts[0].strip()
                    if stock_code:
                        # 确保代码是6位数字
                        stock_code = stock_code[-6:] if len(stock_code) > 6 else stock_code
                        try:
                            # 验证是否为数字代码
                            int(stock_code)
                            stock_codes.append(stock_code)
                        except:
                            continue
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 清空该自选股组的旧数据
            cursor.execute('DELETE FROM portfolios WHERE portfolio_name = ?', (portfolio_name,))
            
            # 插入新数据
            for code in stock_codes:
                cursor.execute('INSERT OR IGNORE INTO portfolios (portfolio_name, stock_code) VALUES (?, ?)', (portfolio_name, code))
            
            conn.commit()
            conn.close()
            
            return True, f"成功导入{len(stock_codes)}只股票到{portfolio_name}"
        except Exception as e:
            return False, f"导入失败: {e}"
    
    def get_portfolio_stocks(self, portfolio_name):
        """从数据库获取自选股列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT p.stock_code, s.name 
            FROM portfolios p 
            LEFT JOIN stock_names s ON p.stock_code = s.code 
            WHERE p.portfolio_name = ?
        ''', (portfolio_name,))
        
        stocks = cursor.fetchall()
        conn.close()
        
        # 转换为列表，确保名称不为空
        result = []
        for code, name in stocks:
            result.append({
                '股票代码': code,
                '股票名称': name if name else code
            })
        
        return result
    
    def add_stock_to_portfolio(self, portfolio_name, stock_code):
        """将股票添加到自选股组"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 确保代码是6位数字
            stock_code = stock_code[-6:] if len(stock_code) > 6 else stock_code
            
            # 插入或忽略，如果已存在则不操作
            cursor.execute('INSERT OR IGNORE INTO portfolios (portfolio_name, stock_code) VALUES (?, ?)', 
                         (portfolio_name, stock_code))
            
            conn.commit()
            conn.close()
            
            return True, f"成功将{stock_code}添加到{portfolio_name}"
        except Exception as e:
            return False, f"添加失败: {e}"
    
    def remove_stock_from_portfolio(self, portfolio_name, stock_code):
        """从自选股组删除股票"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 确保代码是6位数字
            stock_code = stock_code[-6:] if len(stock_code) > 6 else stock_code
            
            # 删除指定股票
            cursor.execute('DELETE FROM portfolios WHERE portfolio_name = ? AND stock_code = ?', 
                         (portfolio_name, stock_code))
            
            conn.commit()
            conn.close()
            
            return True, f"成功从{portfolio_name}删除{stock_code}"
        except Exception as e:
            return False, f"删除失败: {e}"
    
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
        
        # 提取成交数据日期（从文件名中获取，假设格式为deal_20251231_000882.csv）
        self.trade_date = "未知"
        if csv_files:
            # 从第一个文件中提取日期
            first_file = os.path.basename(csv_files[0])
            parts = first_file.replace('.csv', '').split('_')
            if len(parts) >= 2 and len(parts[1]) == 8:
                try:
                    # 转换为YYYY-MM-DD格式
                    date_str = parts[1]
                    self.trade_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                except:
                    self.trade_date = parts[1] if len(parts) >= 2 else "未知"

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
        """从缓存或数据库获取股票名称，只使用6位数字代码"""
        # 确保使用6位数字代码
        stock_code = stock_code[-6:] if len(stock_code) > 6 else stock_code
        
        # 优先从缓存获取
        if stock_code in self.stock_name_cache:
            return self.stock_name_cache[stock_code]
        
        # 从数据库获取
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM stock_names WHERE code = ?', (stock_code,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            name = result[0]
            self.stock_name_cache[stock_code] = name
            return name
        
        # 如果数据库中没有，返回代码
        return stock_code
    
    def update_stock_names(self, progress_callback=None):
        """更新A股股票名称到数据库"""
        try:
            if progress_callback:
                progress_callback("🔄 开始更新A股股票名称...")
            
            # 使用akshare获取所有A股代码和名称
            stock_info = ak.stock_info_a_code_name()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 清空旧数据
            cursor.execute('DELETE FROM stock_names')
            
            # 批量插入新数据
            stocks = []
            for index, row in stock_info.iterrows():
                # 确保代码是6位数字
                code = row['code'][-6:] if len(row['code']) > 6 else row['code']
                name = row['name']
                stocks.append((code, name))
                
                # 更新进度
                if progress_callback and index % 100 == 0:
                    progress = (index + 1) / len(stock_info) * 100
                    progress_callback(f"🔄 更新中: {progress:.1f}% ({index+1}/{len(stock_info)})")
            
            # 批量插入
            cursor.executemany('INSERT OR REPLACE INTO stock_names (code, name) VALUES (?, ?)', stocks)
            conn.commit()
            conn.close()
            
            # 更新缓存
            self.load_stock_names_from_db()
            
            if progress_callback:
                progress_callback(f"✅ A股股票名称更新完成，共 {len(stock_info)} 只股票")
            
            return True
        except Exception as e:
            error_msg = f"⚠️ 更新A股股票名称失败: {e}"
            if progress_callback:
                progress_callback(error_msg)
            print(error_msg)
            return False
    
    def analyze_big_trades(self, buy_threshold, sell_threshold, buy_amount_threshold=0, sell_amount_threshold=0, 
                          buy_logic='不考虑', sell_logic='不考虑', progress_callback=None):
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
                
                # 分析单只股票
                stock_result = self.analyze_single_stock(stock_code, df, buy_threshold, sell_threshold, 
                                                        buy_amount_threshold, sell_amount_threshold, 
                                                        buy_logic, sell_logic)
                
                # 如果有分析结果，添加到市场结果中
                if stock_result:
                    market_results.append(stock_result)
            
            # 按大买单总手数降序排序
            market_results.sort(key=lambda x: (x['大买单总手数'], x['大卖单总手数']), reverse=True)
            results[market] = market_results
        
        return results
    
    def analyze_single_stock(self, stock_code, df=None, buy_threshold=None, sell_threshold=None, 
                           buy_amount_threshold=0, sell_amount_threshold=0, 
                           buy_logic='不考虑', sell_logic='不考虑'):
        """单独分析一只股票的大买卖单"""
        # 如果没有提供数据，尝试从已加载的数据中获取
        if df is None:
            # 尝试从stock_data中获取
            if stock_code in self.stock_data:
                df = self.stock_data[stock_code]
            else:
                # 尝试从market_data中获取
                for market in self.market_data.values():
                    if stock_code in market:
                        df = market[stock_code]
                        break
                else:
                    # 股票数据未加载
                    return None
        
        # 计算每笔交易的金额
        df['Amount'] = df['Price'] * df['Volume']
        
        # 统计大买单（Side=0 表示主动买入）
        buy_mask = (df['Side'] == 0)
        
        if buy_logic == '与and':
            buy_mask &= (df['Volume_Hand'] >= buy_threshold) & (df['Amount'] >= buy_amount_threshold)
        elif buy_logic == '或or':
            buy_mask &= ((df['Volume_Hand'] >= buy_threshold) | (df['Amount'] >= buy_amount_threshold))
        elif buy_logic == '不考虑':
            buy_mask &= (df['Volume_Hand'] >= buy_threshold)
        elif buy_logic == '只考虑':
            buy_mask &= (df['Amount'] >= buy_amount_threshold)
        
        big_buys = df[buy_mask]
        
        # 统计大卖单（Side=1 表示主动卖出）
        sell_mask = (df['Side'] == 1)
        
        if sell_logic == '与and':
            sell_mask &= (df['Volume_Hand'] >= sell_threshold) & (df['Amount'] >= sell_amount_threshold)
        elif sell_logic == '或or':
            sell_mask &= ((df['Volume_Hand'] >= sell_threshold) | (df['Amount'] >= sell_amount_threshold))
        elif sell_logic == '不考虑':
            sell_mask &= (df['Volume_Hand'] >= sell_threshold)
        elif sell_logic == '只考虑':
            sell_mask &= (df['Amount'] >= sell_amount_threshold)
        
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
        
        # 只有当有大买单或大卖单时，才返回结果
        if count_big_buy > 0 or count_big_sell > 0:
            # 获取股票名称，默认使用代码
            stock_name = self.get_stock_name(stock_code)
            
            # 保存详细的大单交易记录
            big_trades = {
                'buys': big_buys.to_dict('records'),
                'sells': big_sells.to_dict('records')
            }
            
            return {
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
            }
        else:
            return None

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
            },
            "TCheckbutton": {
                "background": c['bg'],
                "foreground": c['fg'],
                "padding": 5
            },
            "TRadiobutton": {
                "background": c['bg'],
                "foreground": c['fg'],
                "padding": 5
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

        self.style.map("TCheckbutton",
            background=[('active', c['bg'])],
            foreground=[('active', c['accent'])],
            indicatorcolor=[('selected', c['accent']), ('active', c['accent_hover'])])

        self.style.map("TRadiobutton",
            background=[('active', c['bg'])],
            foreground=[('active', c['accent'])],
            indicatorcolor=[('selected', c['accent']), ('active', c['accent_hover'])])

        # 更新标题和状态标签
        if hasattr(self, 'title_label'):
            self.title_label.configure(bg=c['bg'], fg=c['accent'])
        if hasattr(self, 'status_label'):
            self.status_label.configure(foreground=c['status_blue'] if self.dark_mode else c['accent'])
        if hasattr(self, 'trade_date_label'):
            self.trade_date_label.configure(bg=c['bg'], fg=c['status_green'])
        
        # 刷新所有表格标签颜色
        if hasattr(self, 'tables'):
            for tree in self.tables.values():
                self.refresh_tree_tags(tree)

    def toggle_theme(self):
        """切换深色/浅色模式"""
        self.dark_mode = not self.dark_mode
        self.theme_btn.config(text="🌙 深色模式" if not self.dark_mode else "☀️ 浅色模式")
        self.update_theme_colors()
    
    def import_portfolio(self):
        """导入自选股"""
        try:
            # 获取选择的自选股组
            portfolio = self.selected_portfolio.get()
            
            # 创建文件选择对话框
            from tkinter import filedialog
            file_path = filedialog.askopenfilename(
                title="选择自选股文件",
                filetypes=[("Excel文件", "*.xls")]
            )
            
            if not file_path:
                return  # 用户取消选择
            
            self.update_status(f"📥 开始导入{portfolio}...")
            
            # 调用分析器的导入方法
            success, message = self.analyzer.import_portfolio(portfolio, file_path)
            
            if success:
                self.update_status(f"✅ {message}")
                # 更新自选股标签页显示
                self.refresh_portfolio_display()
            else:
                self.update_status(f"⚠️ {message}")
        except Exception as e:
            self.update_status(f"⚠️ 导入失败: {e}")
    
    def export_portfolio(self):
        """导出自选股到xls/txt文件（制表符分隔）"""
        try:
            # 获取选择的自选股组
            portfolio = self.selected_portfolio.get()
            
            # 获取自选股列表
            stocks = self.analyzer.get_portfolio_stocks(portfolio)
            
            if not stocks:
                self.update_status(f"⚠️ {portfolio}中没有股票可导出")
                return
            
            # 创建文件保存对话框
            from tkinter import filedialog
            file_path = filedialog.asksaveasfilename(
                title="保存自选股文件",
                defaultextension=".xls",
                filetypes=[("Excel文件", "*.xls"), ("文本文件", "*.txt"), ("所有文件", "*.*")],
                initialfile=f"{portfolio}_{datetime.now().strftime('%Y%m%d')}.xls"
            )
            
            if not file_path:
                return  # 用户取消选择
            
            self.update_status(f"📤 开始导出{portfolio}...")
            
            # 将股票代码和名称写入文件，使用制表符分隔，GBK编码兼容Excel
            with open(file_path, 'w', encoding='gbk') as f:
                # 写入标题行
                f.write(f"股票代码\t股票名称\n")
                for stock in stocks:
                    f.write(f"{stock['股票代码']}\t{stock['股票名称']}\n")
            
            self.update_status(f"✅ {portfolio}导出成功，共{len(stocks)}只股票")
        except Exception as e:
            self.update_status(f"⚠️ 导出失败: {e}")
    
    def update_stock_names(self):
        """更新A股股票名称（后台线程）"""
        # 禁用按钮防止重复点击
        self.update_names_btn.config(state=tk.DISABLED)
        
        def update_thread():
            """更新股票名称的线程函数"""
            success = self.analyzer.update_stock_names(progress_callback=self.update_status)
            # 更新按钮状态
            self.root.after(0, lambda: self.update_names_btn.config(state=tk.NORMAL))
            # 更新自选股标签页显示
            self.root.after(0, self.refresh_portfolio_display)
        
        # 启动后台线程
        thread = threading.Thread(target=update_thread)
        thread.daemon = True
        thread.start()
    
    def refresh_portfolio_display(self):
        """刷新自选股标签页显示"""
        try:
            for portfolio_name in ["自选1", "自选2", "自选3"]:
                # 获取自选股列表
                stocks = self.analyzer.get_portfolio_stocks(portfolio_name)
                
                # 如果表格存在，更新显示
                if portfolio_name in self.tables:
                    tree = self.tables[portfolio_name]
                    # 清空表格
                    for item in tree.get_children():
                        tree.delete(item)
                    
                    # 添加自选股数据
                    for i, stock in enumerate(stocks):
                        tag = 'evenrow' if i % 2 == 0 else 'oddrow'
                        # 插入主节点（股票信息）
                        tree.insert('', tk.END, values=(
                            stock['股票代码'],
                            stock['股票名称'],
                            '', '', '', '', '', '', '', '', '', ''
                        ), tags=(tag,))
        except Exception as e:
            self.update_status(f"⚠️ 刷新自选股显示失败: {e}")

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
    
    def update_portfolio_with_analysis(self, results):
        """将分析结果与自选股数据合并显示"""
        try:
            # 构建分析结果字典，以股票代码为键
            analysis_dict = {}
            for market_results in results.values():
                for stock in market_results:
                    analysis_dict[stock['股票代码']] = stock
            
            # 遍历所有自选股组
            for portfolio_name in ["自选1", "自选2", "自选3"]:
                # 获取自选股列表
                portfolio_stocks = self.analyzer.get_portfolio_stocks(portfolio_name)
                
                # 如果表格存在，更新显示
                if portfolio_name in self.tables:
                    tree = self.tables[portfolio_name]
                    # 清空表格
                    for item in tree.get_children():
                        tree.delete(item)
                    
                    # 添加自选股数据，合并分析结果
                    for i, portfolio_stock in enumerate(portfolio_stocks):
                        stock_code = portfolio_stock['股票代码']
                        stock_name = portfolio_stock['股票名称']
                        
                        tag = 'evenrow' if i % 2 == 0 else 'oddrow'
                        
                        if stock_code in analysis_dict:
                            # 股票在分析结果中，显示完整的分析数据
                            stock = analysis_dict[stock_code]
                            
                            # 计算大单买卖比
                            ratio = "N/A"
                            if stock['大卖单总金额'] > 0:
                                ratio = f"{stock['大买单总金额'] / stock['大卖单总金额']:.2f}"
                            elif stock['大买单总金额'] > 0:
                                ratio = "∞"
                            
                            # 计算大单总额和大单净额
                            total_amount = stock['大买单总金额'] + stock['大卖单总金额']
                            net_amount = stock['大买单总金额'] - stock['大卖单总金额']
                            
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
                        else:
                            # 股票不在分析结果中，只显示基本信息
                            tree.insert('', tk.END, values=(
                                stock_code,
                                stock_name,
                                '', '', '', '', '', '', '', '', '', ''
                            ), tags=(tag,))
        except Exception as e:
            self.update_status(f"⚠️ 更新自选股分析结果失败: {e}")
    
    def show_context_menu(self, event, tree):
        """显示右键菜单"""
        # 获取当前选中的项
        selected_item = tree.focus()
        if not selected_item:
            return
        
        # 获取股票代码
        stock_code = tree.item(selected_item, 'values')[0]
        if not stock_code:
            return
        
        # 记录当前选中的表格和股票
        self.current_tree = tree
        self.selected_stock = stock_code
        
        # 显示右键菜单
        self.context_menu.post(event.x_root, event.y_root)
    
    def add_to_specific_portfolio(self, portfolio_name):
        """将股票添加到特定的自选股组"""
        if not self.selected_stock:
            return
        
        # 添加到自选股
        success, message = self.analyzer.add_stock_to_portfolio(portfolio_name, self.selected_stock)
        
        # 更新状态
        self.update_status(f"✅ {message}" if success else f"⚠️ {message}")
        
        # 如果数据已加载，立即分析该股票的大单情况
        if self.analyzer.is_loaded:
            try:
                # 获取当前的分析参数
                buy_threshold = int(self.buy_threshold.get())
                sell_threshold = int(self.sell_threshold.get())
                buy_amount_threshold = float(self.buy_amount_threshold.get()) * 10000
                sell_amount_threshold = float(self.sell_amount_threshold.get()) * 10000
                buy_logic = self.buy_logic.get()
                sell_logic = self.sell_logic.get()
                
                # 单独分析该股票
                stock_result = self.analyzer.analyze_single_stock(
                    self.selected_stock, None, buy_threshold, sell_threshold,
                    buy_amount_threshold, sell_amount_threshold,
                    buy_logic, sell_logic
                )
                
                # 如果有分析结果，更新自选股标签页
                if stock_result:
                    # 构建包含该股票的临时结果字典
                    temp_results = {}
                    # 将结果添加到所有市场（确保在自选股分析中能找到）
                    for market in self.analyzer.market_data:
                        temp_results[market] = []
                    temp_results['全部股票'] = [stock_result]
                    
                    # 更新自选股显示
                    self.update_portfolio_with_analysis(temp_results)
                else:
                    # 刷新自选股显示（显示基本信息）
                    self.refresh_portfolio_display()
            except Exception as e:
                # 如果分析出错，仅刷新显示基本信息
                self.refresh_portfolio_display()
        else:
            # 刷新自选股显示（显示基本信息）
            self.refresh_portfolio_display()
    
    def add_to_portfolio(self):
        """将股票添加到自选"""
        # 兼容旧的调用，默认使用当前选择的自选股组
        if not self.selected_stock:
            return
        
        # 获取选择的自选股组
        portfolio_name = self.selected_portfolio.get()
        
        # 添加到自选股
        success, message = self.analyzer.add_stock_to_portfolio(portfolio_name, self.selected_stock)
        
        # 更新状态
        self.update_status(f"✅ {message}" if success else f"⚠️ {message}")
        
        # 如果数据已加载，立即分析该股票的大单情况
        if self.analyzer.is_loaded:
            try:
                # 获取当前的分析参数
                buy_threshold = int(self.buy_threshold.get())
                sell_threshold = int(self.sell_threshold.get())
                buy_amount_threshold = float(self.buy_amount_threshold.get()) * 10000
                sell_amount_threshold = float(self.sell_amount_threshold.get()) * 10000
                buy_logic = self.buy_logic.get()
                sell_logic = self.sell_logic.get()
                
                # 单独分析该股票
                stock_result = self.analyzer.analyze_single_stock(
                    self.selected_stock, None, buy_threshold, sell_threshold,
                    buy_amount_threshold, sell_amount_threshold,
                    buy_logic, sell_logic
                )
                
                # 如果有分析结果，更新自选股标签页
                if stock_result:
                    # 构建包含该股票的临时结果字典
                    temp_results = {}
                    # 将结果添加到所有市场（确保在自选股分析中能找到）
                    for market in self.analyzer.market_data:
                        temp_results[market] = []
                    temp_results['全部股票'] = [stock_result]
                    
                    # 更新自选股显示
                    self.update_portfolio_with_analysis(temp_results)
                else:
                    # 刷新自选股显示（显示基本信息）
                    self.refresh_portfolio_display()
            except Exception as e:
                # 如果分析出错，仅刷新显示基本信息
                self.refresh_portfolio_display()
        else:
            # 刷新自选股显示（显示基本信息）
            self.refresh_portfolio_display()
    
    def remove_from_portfolio(self):
        """从自选删除股票"""
        if not self.selected_stock:
            return
        
        # 获取当前表格对应的市场名称
        # 遍历所有表格，找到当前选中的表格
        current_market = None
        for market, tree in self.tables.items():
            if tree == self.current_tree:
                current_market = market
                break
        
        # 只有在自选股标签页中才能删除
        if current_market in ["自选1", "自选2", "自选3"]:
            # 从自选股删除
            success, message = self.analyzer.remove_stock_from_portfolio(current_market, self.selected_stock)
            
            # 更新状态
            self.update_status(f"✅ {message}" if success else f"⚠️ {message}")
            
            # 刷新自选股显示
            self.refresh_portfolio_display()
        else:
            self.update_status(f"⚠️ 请在自选股标签页中删除股票")

    def on_check_toggle(self):
        """根据勾选状态启用/禁用输入框并同步逻辑"""
        # 更新输入框启用状态
        self.buy_entry.config(state=tk.NORMAL if self.buy_type.get() else tk.DISABLED)
        self.sell_entry.config(state=tk.NORMAL if self.sell_type.get() else tk.DISABLED)
        self.buy_amount_entry.config(state=tk.NORMAL if self.buy_amt_type.get() else tk.DISABLED)
        self.sell_amount_entry.config(state=tk.NORMAL if self.sell_amt_type.get() else tk.DISABLED)
        
        # 自动同步买入逻辑
        if self.buy_type.get() and self.buy_amt_type.get():
            if self.buy_logic.get() not in ["与and", "或or"]:
                self.buy_logic.set("与and")
        elif self.buy_type.get():
            self.buy_logic.set("不考虑")
        elif self.buy_amt_type.get():
            self.buy_logic.set("只考虑")
            
        # 自动同步卖出逻辑
        if self.sell_type.get() and self.sell_amt_type.get():
            if self.sell_logic.get() not in ["与and", "或or"]:
                self.sell_logic.set("与and")
        elif self.sell_type.get():
            self.sell_logic.set("不考虑")
        elif self.sell_amt_type.get():
            self.sell_logic.set("只考虑")


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
        
        # 成交数据日期显示
        self.trade_date_var = tk.StringVar(value="")
        trade_date_label = tk.Label(header_frame, textvariable=self.trade_date_var, 
                                  font=("Microsoft YaHei", 16, "bold"), 
                                  bg=self.colors['dark']['bg'], fg=self.colors['dark']['status_green'])
        trade_date_label.pack(side=tk.LEFT, padx=(20, 0))
        self.trade_date_label = trade_date_label # 保存引用以便更新颜色
        
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
        
        # 更新A股股票名称按钮
        self.update_names_btn = ttk.Button(load_frame, text="📋 更新A股股票名称", command=self.update_stock_names)
        self.update_names_btn.pack(pady=5)
        
        self.status_var = tk.StringVar(value="准备就绪")
        self.status_label = ttk.Label(load_frame, textvariable=self.status_var, wraplength=200)
        self.status_label.pack(pady=5)
        
        # 参数设置面板
        params_frame = ttk.LabelFrame(top_panels, text="分析参数设置", padding="15")
        params_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 分析参数设置
        grid_frame = ttk.Frame(params_frame)
        grid_frame.pack(expand=True)
        
        # 定义模式变量
        self.buy_type = tk.IntVar(value=1)
        self.buy_amt_type = tk.IntVar(value=0)
        self.sell_type = tk.IntVar(value=1)
        self.sell_amt_type = tk.IntVar(value=0)

        # Row 0: Buy Threshold & Sell Threshold
        ttk.Checkbutton(grid_frame, variable=self.buy_type, command=self.on_check_toggle).grid(row=0, column=0, padx=(10, 0), pady=5)
        ttk.Label(grid_frame, text="买入阈值 (手):").grid(row=0, column=1, padx=(0, 10), pady=5, sticky=tk.E)
        self.buy_threshold = tk.StringVar(value="5000")
        self.buy_entry = ttk.Entry(grid_frame, textvariable=self.buy_threshold, width=15)
        self.buy_entry.grid(row=0, column=2, padx=10, pady=5)
        
        ttk.Checkbutton(grid_frame, variable=self.sell_type, command=self.on_check_toggle).grid(row=0, column=3, padx=(20, 0), pady=5)
        ttk.Label(grid_frame, text="卖出阈值 (手):").grid(row=0, column=4, padx=(0, 10), pady=5, sticky=tk.E)
        self.sell_threshold = tk.StringVar(value="5000")
        self.sell_entry = ttk.Entry(grid_frame, textvariable=self.sell_threshold, width=15)
        self.sell_entry.grid(row=0, column=5, padx=10, pady=5)
        
        # Row 1: Buy Amount & Sell Amount
        ttk.Checkbutton(grid_frame, variable=self.buy_amt_type, command=self.on_check_toggle).grid(row=1, column=0, padx=(10, 0), pady=5)
        ttk.Label(grid_frame, text="买入金额阈值 (万元):").grid(row=1, column=1, padx=(0, 10), pady=5, sticky=tk.E)
        self.buy_amount_threshold = tk.StringVar(value="0")
        self.buy_amount_entry = ttk.Entry(grid_frame, textvariable=self.buy_amount_threshold, width=15)
        self.buy_amount_entry.grid(row=1, column=2, padx=10, pady=5)
        
        ttk.Checkbutton(grid_frame, variable=self.sell_amt_type, command=self.on_check_toggle).grid(row=1, column=3, padx=(20, 0), pady=5)
        ttk.Label(grid_frame, text="卖出金额阈值 (万元):").grid(row=1, column=4, padx=(0, 10), pady=5, sticky=tk.E)
        self.sell_amount_threshold = tk.StringVar(value="0")
        self.sell_amount_entry = ttk.Entry(grid_frame, textvariable=self.sell_amount_threshold, width=15)
        self.sell_amount_entry.grid(row=1, column=5, padx=10, pady=5)
        
        # Row 2: Buy Logic & Sell Logic
        ttk.Label(grid_frame, text="考虑买入金额:").grid(row=2, column=1, padx=(0, 10), pady=5, sticky=tk.E)
        self.buy_logic = tk.StringVar(value="不考虑")
        buy_logic_combo = ttk.Combobox(grid_frame, textvariable=self.buy_logic, values=["不考虑", "与and", "或or", "只考虑"], width=13, state="readonly")
        buy_logic_combo.grid(row=2, column=2, padx=10, pady=5)
        
        ttk.Label(grid_frame, text="考虑卖出金额:").grid(row=2, column=4, padx=(0, 10), pady=5, sticky=tk.E)
        self.sell_logic = tk.StringVar(value="不考虑")
        sell_logic_combo = ttk.Combobox(grid_frame, textvariable=self.sell_logic, values=["不考虑", "与and", "或or", "只考虑"], width=13, state="readonly")
        sell_logic_combo.grid(row=2, column=5, padx=10, pady=5)
        
        self.analyze_btn = ttk.Button(grid_frame, text="🚀 开始扫描分析", command=self.analyze_data, style="Accent.TButton")
        self.analyze_btn.grid(row=0, column=6, padx=20, pady=5, rowspan=3)
        
        # 初始化输入框的状态
        self.on_check_toggle()
        
        # 自选股操作面板
        portfolio_frame = ttk.LabelFrame(top_panels, text="自选股操作", padding="15")
        portfolio_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0))
        
        # 选择自选几
        self.selected_portfolio = tk.StringVar(value="自选1")
        portfolio_combo = ttk.Combobox(portfolio_frame, textvariable=self.selected_portfolio, values=["自选1", "自选2", "自选3"], width=15, state="readonly")
        portfolio_combo.pack(pady=(0, 10))
        
        # 导入按钮
        import_btn = ttk.Button(portfolio_frame, text="📥 导入自选股", command=self.import_portfolio)
        import_btn.pack(pady=5, fill=tk.X)
        
        # 导出按钮
        export_btn = ttk.Button(portfolio_frame, text="📤 导出自选股", command=self.export_portfolio)
        export_btn.pack(pady=5, fill=tk.X)
        
        # 结果显示区域
        result_frame = ttk.LabelFrame(self.main_frame, text="多维度分析结果", padding="5")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=(15, 0))
        
        # 创建标签页控件
        self.notebook = ttk.Notebook(result_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 创建表格容器
        self.tables = {}
        markets = [('全部股票', '🌐'), ('沪市主板', '🏛️'), ('深市主板', '🏙️'), ('创业板', '🚀'), ('科创板', '🔬'), ('自选1', '⭐'), ('自选2', '⭐'), ('自选3', '⭐')]
        
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
            
            # 为表格添加右键菜单支持
            tree.bind("<Button-3>", lambda event, tree=tree: self.show_context_menu(event, tree))
        
        # 创建完所有表格后，加载自选股数据
        self.refresh_portfolio_display()
        
        # 创建右键菜单
        self.context_menu = tk.Menu(self.root, tearoff=0)
        # 添加到自选1, 2, 3的选项
        self.context_menu.add_command(label="添加到自选1", command=lambda: self.add_to_specific_portfolio("自选1"))
        self.context_menu.add_command(label="添加到自选2", command=lambda: self.add_to_specific_portfolio("自选2"))
        self.context_menu.add_command(label="添加到自选3", command=lambda: self.add_to_specific_portfolio("自选3"))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="从自选删除", command=self.remove_from_portfolio)
        
        # 记录当前选中的表格和股票
        self.current_tree = None
        self.selected_stock = None

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
        
        # 让用户选择数据文件夹
        from tkinter import filedialog
        data_dir = filedialog.askdirectory(
            title="选择成交数据文件夹",
            initialdir="."
        )
        
        if not data_dir:
            self.load_btn.config(state=tk.NORMAL)
            self.analyze_btn.config(state=tk.NORMAL)
            return  # 用户取消选择
        
        def load_thread():
            # 更新analyzer的数据目录
            self.analyzer.data_dir = data_dir
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
            # 显示成交数据日期
            if hasattr(self.analyzer, 'trade_date'):
                self.trade_date_var.set(f"📅 成交数据日期: {self.analyzer.trade_date}")
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
            if market in results:
                # 清空表格，显示分析结果
                for item in tree.get_children():
                    tree.delete(item)
                
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
                    
                    # 重新配置tree的标签，确保颜色正确
                    self.refresh_tree_tags(tree)
        
        # 处理自选股表格，合并分析结果和自选股数据
        self.update_portfolio_with_analysis(results)

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

