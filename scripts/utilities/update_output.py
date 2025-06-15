#!/usr/bin/env python3
"""timetable_v4の最新の改良版時間割をtimetable_v5にコピーするスクリプト"""
import shutil
from pathlib import Path
from datetime import datetime

def main():
    """メイン処理"""
    print("=== 時間割更新スクリプト ===\n")
    
    # パスの設定
    v4_dir = Path("/Users/hayashimitsuhiro/Desktop/timetable_v4")
    v5_dir = Path("/Users/hayashimitsuhiro/Desktop/timetable_v5")
    
    # v4の出力ファイルをチェック
    v4_outputs = [
        v4_dir / "data" / "output" / "output_enhanced_filled.csv",
        v4_dir / "data" / "output" / "output_improved.csv",
        v4_dir / "data" / "output" / "output.csv"
    ]
    
    # 最新のファイルを探す
    latest_file = None
    latest_time = None
    
    for file_path in v4_outputs:
        if file_path.exists():
            mtime = file_path.stat().st_mtime
            if latest_time is None or mtime > latest_time:
                latest_time = mtime
                latest_file = file_path
    
    if latest_file is None:
        print("❌ timetable_v4に出力ファイルが見つかりません")
        return 1
    
    # コピー先
    v5_output = v5_dir / "data" / "output" / "output.csv"
    
    # バックアップを作成
    if v5_output.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = v5_output.with_suffix(f".backup_{timestamp}.csv")
        shutil.copy2(v5_output, backup_path)
        print(f"✅ 既存ファイルをバックアップ: {backup_path.name}")
    
    # コピー実行
    v5_output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(latest_file, v5_output)
    
    print(f"✅ コピー完了:")
    print(f"   FROM: {latest_file.relative_to(latest_file.parent.parent.parent)}")
    print(f"   TO:   {v5_output.relative_to(v5_dir)}")
    print(f"   更新時刻: {datetime.fromtimestamp(latest_time).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 空きコマが埋められたバージョンも存在する場合はコピー
    if "enhanced_filled" in latest_file.name:
        v5_filled = v5_dir / "data" / "output" / "output_enhanced_filled.csv"
        shutil.copy2(latest_file, v5_filled)
        print(f"\n✅ 空きコマ埋め版もコピー: {v5_filled.name}")
    
    print("\n=== 更新完了 ===")
    return 0


if __name__ == "__main__":
    exit(main())