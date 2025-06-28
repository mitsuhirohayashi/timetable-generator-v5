#!/usr/bin/env python3
"""交流学級ルールを考慮した体育館使用違反の分析"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from collections import defaultdict
from src.infrastructure.config.path_config import path_config

def analyze_gym_violations_with_exchange_rule():
    """交流学級ルールを考慮して体育館使用違反を分析"""
    
    # 交流学級と親学級の対応関係
    exchange_parent_pairs = [
        ((1, 1), (1, 6)),  # 1年1組と1年6組
        ((1, 2), (1, 7)),  # 1年2組と1年7組
        ((2, 3), (2, 6)),  # 2年3組と2年6組
        ((2, 2), (2, 7)),  # 2年2組と2年7組
        ((3, 3), (3, 6)),  # 3年3組と3年6組
        ((3, 2), (3, 7)),  # 3年2組と3年7組
    ]
    
    # テスト期間の定義（Follow-up.csvより）
    test_periods = [
        ('月', '1'), ('月', '2'), ('月', '3'),
        ('火', '1'), ('火', '2'), ('火', '3'),
        ('水', '1'), ('水', '2')
    ]
    
    # 時間割を読み込み
    schedule_df = pd.read_csv(path_config.output_dir / "output.csv", header=None)
    
    # ヘッダー行をスキップして処理
    days = schedule_df.iloc[0, 1:].tolist()
    periods = schedule_df.iloc[1, 1:].tolist()
    
    # 時間ごとの体育授業を収集
    time_pe_classes = defaultdict(list)
    
    for row_idx in range(2, len(schedule_df)):
        row = schedule_df.iloc[row_idx]
        if pd.isna(row[0]) or row[0] == "":
            continue
            
        class_name = row[0]
        if '年' not in class_name or '組' not in class_name:
            continue
            
        # クラス情報を解析
        parts = class_name.split('年')
        grade = int(parts[0])
        class_num = int(parts[1].replace('組', ''))
        
        for col_idx in range(1, len(row)):
            subject = row[col_idx]
            if pd.isna(subject) or subject == "":
                continue
                
            # 体育関連科目かチェック
            if subject in ['保', '保健', '体育', '保健体育']:
                day = days[col_idx - 1]
                period = periods[col_idx - 1]
                
                time_key = (day, period)
                time_pe_classes[time_key].append({
                    'class_name': class_name,
                    'grade': grade,
                    'class_num': class_num
                })
    
    print("=== 交流学級ルールを考慮した体育館使用違反分析 ===\n")
    
    violations = []
    
    for (day, period), classes in time_pe_classes.items():
        if len(classes) > 1:
            is_test_period = (day, period) in test_periods
            
            if is_test_period:
                print(f"{day}曜{period}校時: テスト期間のため除外")
                continue
            
            # 5組合同体育かチェック
            class_nums = [c['class_num'] for c in classes]
            if all(num == 5 for num in class_nums):
                print(f"{day}曜{period}校時: 5組合同体育のため正常")
                continue
            
            # 交流学級と親学級のペアをチェック
            class_tuples = [(c['grade'], c['class_num']) for c in classes]
            
            # ペアになっているクラスを特定
            paired_classes = set()
            for parent, exchange in exchange_parent_pairs:
                if parent in class_tuples and exchange in class_tuples:
                    paired_classes.add(parent)
                    paired_classes.add(exchange)
            
            # ペア以外のクラスを特定
            unpaired_classes = [c for c in classes 
                              if (c['grade'], c['class_num']) not in paired_classes]
            
            # 違反判定
            if len(unpaired_classes) == 0 and len(paired_classes) == len(class_tuples):
                # 全てがペアの場合は正常
                print(f"{day}曜{period}校時: 親学級と交流学級のペアのみなので正常")
                for c in classes:
                    print(f"  - {c['class_name']}")
            else:
                # ペア以外のクラスがある、または複数のペアが重なっている場合は違反
                violations.append({
                    'day': day,
                    'period': period,
                    'all_classes': [c['class_name'] for c in classes],
                    'paired_classes': [c['class_name'] for c in classes 
                                     if (c['grade'], c['class_num']) in paired_classes],
                    'unpaired_classes': [c['class_name'] for c in unpaired_classes],
                    'violation_type': 'ペア以外のクラスあり' if unpaired_classes 
                                    else '複数ペアの重複'
                })
    
    print("\n【実際の体育館使用違反】")
    
    for v in violations:
        print(f"\n{v['day']}曜{v['period']}校時:")
        print(f"  全クラス: {', '.join(v['all_classes'])}")
        if v['paired_classes']:
            print(f"  親学級・交流学級ペア: {', '.join(v['paired_classes'])}")
        if v['unpaired_classes']:
            print(f"  違反クラス: {', '.join(v['unpaired_classes'])}")
        print(f"  違反タイプ: {v['violation_type']}")
    
    print(f"\n=== サマリー ===")
    print(f"実際の体育館使用違反: {len(violations)} 件")
    
    # 具体的な修正提案
    if violations:
        print("\n【修正提案】")
        for v in violations:
            if v['unpaired_classes']:
                print(f"\n{v['day']}曜{v['period']}校時:")
                print(f"  {', '.join(v['unpaired_classes'])}の体育を他の時間に移動")

if __name__ == "__main__":
    analyze_gym_violations_with_exchange_rule()