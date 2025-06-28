#!/usr/bin/env python3
"""
UltrathinkPerfectGeneratorの修正スクリプト

AssignmentとScheduleのAPIを正しく使用するように修正します。
"""
import re

def fix_ultrathink_generator():
    """UltrathinkPerfectGeneratorの修正を実行"""
    
    file_path = "/Users/hayashimitsuhiro/Desktop/timetable_v5/src/domain/services/ultrathink_perfect_generator.py"
    
    # ファイルを読み込む
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 修正1: Assignment生成を修正（time_slotとis_lockedを削除）
    # Pattern 1: Assignment with time_slot and is_locked
    pattern1 = r'assignment = Assignment\(\s*class_ref=([^,]+),\s*time_slot=([^,]+),\s*subject=([^,]+),\s*teacher=([^,]+),\s*is_locked=([^)]+)\)'
    def replacement1(match):
        class_ref = match.group(1)
        time_slot = match.group(2)
        subject = match.group(3)
        teacher = match.group(4)
        is_locked = match.group(5)
        
        # Subjectオブジェクトを作成
        return f'''assignment = Assignment(
                            class_ref={class_ref},
                            subject=Subject({subject}),
                            teacher={teacher} if {teacher} else None
                        )'''
    
    content = re.sub(pattern1, replacement1, content, flags=re.MULTILINE | re.DOTALL)
    
    # 修正2: schedule.assignの呼び出しを追加
    # Pattern: schedule.assign(assignment) を schedule.assign(time_slot, assignment) に変更
    pattern2 = r'schedule\.assign\(assignment\)'
    replacement2 = 'schedule.assign(time_slot, assignment)'
    content = re.sub(pattern2, replacement2, content)
    
    # 修正3: new_assignmentの作成も同様に修正
    pattern3 = r'new_assignment = Assignment\(\s*class_ref=([^,]+),\s*time_slot=([^,]+),\s*subject=([^,]+),\s*teacher=([^,]+),\s*is_locked=([^)]+)\)'
    def replacement3(match):
        class_ref = match.group(1)
        time_slot = match.group(2)
        subject = match.group(3)
        teacher = match.group(4)
        is_locked = match.group(5)
        
        return f'''new_assignment = Assignment(
                                    class_ref={class_ref},
                                    subject=Subject({subject}),
                                    teacher={teacher} if {teacher} else None
                                )'''
    
    content = re.sub(pattern3, replacement3, content, flags=re.MULTILINE | re.DOTALL)
    
    # 修正4: Subject importを追加
    if "from ...domain.value_objects.time_slot import Subject" not in content:
        # TimeSlot importの後にSubject importを追加
        content = content.replace(
            "from ...domain.value_objects.time_slot import TimeSlot, ClassReference as ClassRef",
            "from ...domain.value_objects.time_slot import TimeSlot, ClassReference as ClassRef, Subject"
        )
    
    # 修正5: schedule.get_assignmentの呼び出しを修正
    # get_assignment(class_ref, time_slot) -> get_assignment(time_slot, class_ref)
    pattern5 = r'schedule\.get_assignment\(([^,]+), ([^)]+)\)'
    def replacement5(match):
        arg1 = match.group(1).strip()
        arg2 = match.group(2).strip()
        
        # arg1がtime_slotっぽい場合はそのまま、class_refっぽい場合は入れ替える
        if 'time_slot' in arg2 or 'TimeSlot' in arg2:
            return f'schedule.get_assignment({arg2}, {arg1})'
        else:
            return f'schedule.get_assignment({arg1}, {arg2})'
    
    content = re.sub(pattern5, replacement5, content)
    
    # 修正6: assignmentsへのアクセスを修正
    # schedule.assignments -> schedule.get_all_assignments()のキーから取得
    pattern6 = r'for class_ref in schedule\.assignments:'
    replacement6 = '''assignments_by_class = {}
        for (time_slot_iter, class_ref_iter), assignment in schedule.get_all_assignments().items():
            if class_ref_iter not in assignments_by_class:
                assignments_by_class[class_ref_iter] = []
            assignments_by_class[class_ref_iter].append((time_slot_iter, assignment))
        
        for class_ref in assignments_by_class:'''
    
    content = re.sub(pattern6, replacement6, content)
    
    # ファイルを書き戻す
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("UltrathinkPerfectGeneratorの修正が完了しました")
    
    # 修正内容の確認
    print("\n修正内容:")
    print("1. Assignment生成時のtime_slotとis_lockedパラメータを削除")
    print("2. schedule.assign()の呼び出しを修正")
    print("3. Subject importを追加")
    print("4. schedule.get_assignment()の引数順序を修正")
    print("5. schedule.assignmentsへの直接アクセスを修正")

if __name__ == "__main__":
    fix_ultrathink_generator()