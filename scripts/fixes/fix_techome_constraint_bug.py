#!/usr/bin/env python3
"""技家制約のバグを修正"""

import logging
from pathlib import Path

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def fix_techome_constraint():
    """TechHomeFeasibilityConstraintのcheckメソッドをcheck_before_assignmentに変更"""
    
    file_path = Path("src/domain/constraints/techome_feasibility_constraint.py")
    
    logger.info(f"=== {file_path} の修正 ===")
    
    # ファイルを読み込む
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # checkメソッドをcheck_before_assignmentに変更
    # このメソッドはbooleanを返すべき
    
    new_method = '''    def check_before_assignment(
        self, 
        schedule: Schedule, 
        school: School, 
        time_slot: TimeSlot,
        assignment: Assignment
    ) -> bool:
        """配置前チェック: 技家の配置が可能かどうか判定"""
        # 技家以外の科目は常に許可
        if assignment.subject.name != "技家":
            return True
            
        return self.can_satisfy(
            schedule, school, time_slot, 
            assignment.class_ref, assignment.subject, assignment.teacher
        )
    
    def check('''
    
    # checkメソッドの定義を見つけて、その前にcheck_before_assignmentを追加
    import re
    
    # def check( の位置を見つける
    check_pattern = r'(\s+def check\()'
    match = re.search(check_pattern, content)
    
    if match:
        # checkメソッドの前に新しいメソッドを挿入
        insert_pos = match.start()
        new_content = content[:insert_pos] + new_method + content[insert_pos:]
        
        # ファイルに書き戻す
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        logger.info("✓ check_before_assignmentメソッドを追加しました")
        logger.info("  - 技家以外の科目は常にTrueを返すようになりました")
        logger.info("  - 技家の場合はcan_satisfyメソッドを呼び出します")
    else:
        logger.error("checkメソッドが見つかりませんでした")

def main():
    """メイン処理"""
    logger.info("技家制約のバグ修正を開始")
    fix_techome_constraint()
    logger.info("\n修正完了！")
    logger.info("これで3年生の6限に授業を配置できるようになるはずです。")

if __name__ == "__main__":
    main()