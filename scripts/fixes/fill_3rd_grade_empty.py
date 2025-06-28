"""3年生の空きスロットを埋めるスクリプト"""
import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict

def fill_3rd_grade_empty():
    """3年生の空きスロットを埋める"""
    # ファイルパス
    input_path = Path("data/output/output_fixed.csv")
    output_path = Path("data/output/output_final.csv")
    
    # 標準時数を読み込み
    base_hours = pd.read_csv("data/config/base_timetable.csv")
    
    # CSVを読み込み
    df = pd.read_csv(input_path, header=None)
    
    # ヘッダー行をスキップ
    header_rows = 2
    df_data = df.iloc[header_rows:].copy()
    
    # 3年生クラスのインデックスを取得
    third_grade_indices = []
    for i, class_name in enumerate(df_data[0].values):
        if isinstance(class_name, str) and '3年' in class_name and '5組' not in class_name:
            third_grade_indices.append((i + header_rows, class_name))
    
    print("3年生クラス:")
    for idx, name in third_grade_indices:
        print(f"  {idx}: {name}")
    
    # 各クラスの空きスロットを埋める
    filled_count = 0
    
    for class_idx, class_name in third_grade_indices:
        # このクラスの現在の配置数をカウント
        subject_count = defaultdict(int)
        empty_slots = []
        
        for col in range(1, len(df.columns)):
            val = df.iloc[class_idx, col]
            if pd.isna(val) or val == '':
                time_info = f"{df.iloc[0, col]}{df.iloc[1, col]}限"
                empty_slots.append((col, time_info))
            elif isinstance(val, str) and val not in ['欠', 'YT', '道', '学総', '総', '行']:
                subject_count[val] += 1
        
        if not empty_slots:
            continue
        
        print(f"\n{class_name}の空きスロット: {len(empty_slots)}個")
        
        # 標準時数と比較して不足している教科を見つける
        # base_timetable.csvから該当クラスの行を探す
        class_row = None
        for _, row in base_hours.iterrows():
            if row[0] == class_name:  # 最初の列がクラス名
                class_row = row
                break
        
        if class_row is not None:
            shortage = []
            # 科目名は2行目（インデックス1）にある
            subject_names = base_hours.iloc[1, 1:].values
            
            for i, subject in enumerate(subject_names):
                if pd.isna(subject) or subject == '':
                    continue
                if subject in ['欠', 'YT', '道', '道徳', '学', '学活', '学総', '総', '総合', '行', '行事']:
                    continue
                
                try:
                    required = float(class_row.iloc[i + 1])
                    current = subject_count.get(subject, 0)
                    if required > current:
                        shortage.append((subject, required - current))
                except:
                    continue
            
            # 不足数の多い順にソート
            shortage.sort(key=lambda x: x[1], reverse=True)
            
            print(f"不足教科: {shortage}")
            
            # 空きスロットに配置
            for col, time_info in empty_slots:
                if shortage:
                    subject, _ = shortage[0]
                    df.iloc[class_idx, col] = subject
                    subject_count[subject] += 1
                    print(f"  {time_info} → {subject}")
                    filled_count += 1
                    
                    # 不足数を更新
                    new_shortage = []
                    for subj, short in shortage:
                        if subj == subject:
                            if short > 1:
                                new_shortage.append((subj, short - 1))
                        else:
                            new_shortage.append((subj, short))
                    shortage = new_shortage
                    shortage.sort(key=lambda x: x[1], reverse=True)
    
    # 保存
    df.to_csv(output_path, index=False, header=False)
    print(f"\n修正完了: {filled_count}箇所")
    print(f"出力ファイル: {output_path}")
    
    return filled_count

if __name__ == "__main__":
    fill_3rd_grade_empty()