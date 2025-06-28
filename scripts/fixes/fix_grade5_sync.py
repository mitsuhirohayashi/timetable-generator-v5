"""5組の同期を修正するスクリプト"""
import pandas as pd
import numpy as np
from pathlib import Path

def fix_grade5_sync():
    """5組の同期を修正"""
    # ファイルパス
    input_path = Path("data/output/output.csv")
    output_path = Path("data/output/output_fixed.csv")
    
    # CSVを読み込み
    df = pd.read_csv(input_path, header=None)
    
    # ヘッダー行をスキップ
    header_rows = 2
    df_data = df.iloc[header_rows:].copy()
    
    # クラス名の列（0列目）を取得
    class_names = df_data[0].values
    
    # 5組のインデックスを見つける
    grade5_indices = []
    for i, class_name in enumerate(class_names):
        if isinstance(class_name, str) and '5組' in class_name:
            grade5_indices.append(i + header_rows)
    
    print(f"5組のインデックス: {grade5_indices}")
    print(f"5組のクラス: {[df.iloc[i, 0] for i in grade5_indices]}")
    
    # 各時限（列）をチェック
    fixed_count = 0
    for col in range(1, len(df.columns)):
        # この時限の5組の値を取得
        grade5_values = []
        for idx in grade5_indices:
            val = df.iloc[idx, col]
            grade5_values.append(val)
        
        # 空欄がある場合
        empty_indices = []
        non_empty_value = None
        for i, val in enumerate(grade5_values):
            if pd.isna(val) or val == '':
                empty_indices.append(i)
            elif non_empty_value is None:
                non_empty_value = val
        
        # 空欄があり、非空欄の値がある場合は同期
        if empty_indices and non_empty_value is not None:
            time_info = f"{df.iloc[0, col]}{df.iloc[1, col]}限"
            for i in empty_indices:
                df.iloc[grade5_indices[i], col] = non_empty_value
                class_name = df.iloc[grade5_indices[i], 0]
                print(f"修正: {class_name} {time_info} → {non_empty_value}")
                fixed_count += 1
    
    # 保存
    df.to_csv(output_path, index=False, header=False)
    print(f"\n修正完了: {fixed_count}箇所")
    print(f"出力ファイル: {output_path}")
    
    return fixed_count

if __name__ == "__main__":
    fix_grade5_sync()