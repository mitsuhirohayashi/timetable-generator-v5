#!/usr/bin/env python3
"""「非」制約のデバッグスクリプト - 制約の登録と違反を詳細に分析"""

import sys
from pathlib import Path
import csv
from typing import Dict, List, Tuple, Set
import logging

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.domain.value_objects.time_slot import TimeSlot
from src.domain.entities.school import School
from src.domain.entities.schedule import Schedule
from src.infrastructure.repositories.csv_repository import CSVSchoolRepository, CSVScheduleRepository
from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
from src.domain.services.core.unified_constraint_system import UnifiedConstraintSystem
from src.application.services.constraint_registration_service import ConstraintRegistrationService
from src.infrastructure.config.path_config import path_config

# ロギング設定
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def analyze_forbidden_constraints():
    """「非」制約の登録と違反を分析"""
    logger.info("=== 「非」制約のデバッグ分析を開始 ===\n")
    
    # 1. input.csvから「非」制約を読み取る
    logger.info("1. input.csvから「非」制約を読み取り中...")
    reader = CSVScheduleReader()
    input_path = path_config.data_dir / "input" / "input.csv"
    
    with open(input_path, 'r', encoding='utf-8-sig') as f:
        csv_data = list(csv.reader(f))
    
    # 「非」制約を手動で抽出
    forbidden_constraints = {}
    days = ["月", "火", "水", "木", "金"]
    
    for row_idx, row in enumerate(csv_data[2:], 2):  # ヘッダー2行をスキップ
        if not row or not row[0]:
            continue
        
        class_name = row[0]
        
        for col_idx, cell in enumerate(row[1:], 1):
            if cell.startswith("非"):
                day_idx = (col_idx - 1) // 6
                period = (col_idx - 1) % 6 + 1
                
                if day_idx < len(days):
                    time_slot = f"{days[day_idx]}{period}限"
                    forbidden_subject = cell[1:]  # "非数" → "数"
                    
                    if class_name not in forbidden_constraints:
                        forbidden_constraints[class_name] = []
                    
                    forbidden_constraints[class_name].append({
                        'time_slot': time_slot,
                        'day': days[day_idx],
                        'period': period,
                        'forbidden_subject': forbidden_subject,
                        'cell_value': cell
                    })
    
    # 制約を表示
    logger.info("\n発見された「非」制約:")
    for class_name, constraints in forbidden_constraints.items():
        logger.info(f"\n{class_name}:")
        for c in constraints:
            logger.info(f"  - {c['time_slot']}: {c['cell_value']} (→ {c['forbidden_subject']}を配置禁止)")
    
    # 2. output.csvで違反をチェック
    logger.info("\n\n2. output.csvで違反をチェック中...")
    output_path = path_config.data_dir / "output" / "output.csv"
    
    if not output_path.exists():
        logger.error(f"出力ファイルが存在しません: {output_path}")
        return
    
    with open(output_path, 'r', encoding='utf-8-sig') as f:
        output_data = list(csv.reader(f))
    
    # 違反を検出
    violations = []
    
    for class_name, constraints in forbidden_constraints.items():
        # 出力データで該当クラスの行を探す
        class_row_idx = None
        for idx, row in enumerate(output_data):
            if row and row[0] == class_name:
                class_row_idx = idx
                break
        
        if class_row_idx is None:
            logger.warning(f"クラス {class_name} が出力に見つかりません")
            continue
        
        # 各制約をチェック
        for constraint in constraints:
            col_idx = (days.index(constraint['day']) * 6) + constraint['period']
            
            if col_idx < len(output_data[class_row_idx]):
                actual_subject = output_data[class_row_idx][col_idx]
                
                # 違反チェック
                if actual_subject == constraint['forbidden_subject']:
                    violations.append({
                        'class': class_name,
                        'time_slot': constraint['time_slot'],
                        'forbidden': constraint['forbidden_subject'],
                        'actual': actual_subject,
                        'input_cell': constraint['cell_value']
                    })
    
    # 違反を表示
    if violations:
        logger.error(f"\n\n=== 発見された違反: {len(violations)}件 ===")
        for v in violations:
            logger.error(
                f"❌ {v['class']} {v['time_slot']}: "
                f"「{v['input_cell']}」なのに「{v['actual']}」が配置されています！"
            )
    else:
        logger.info("\n\n✅ 「非」制約の違反は発見されませんでした")
    
    # 3. 制約システムの状態を確認
    logger.info("\n\n3. 制約システムの状態を確認中...")
    
    # 学校データとスケジュールを読み込む
    school_repo = CSVSchoolRepository(path_config.data_dir)
    schedule_repo = CSVScheduleRepository(path_config.data_dir)
    
    school = school_repo.load_school_data("config/base_timetable.csv")
    
    # input.csvを読み込んで forbidden_cells を取得
    input_schedule = schedule_repo.load_desired_schedule(str(input_path), school)
    
    # CSVScheduleReaderのforbidden_cellsを確認
    logger.info("\nCSVScheduleReaderのforbidden_cells:")
    reader_instance = schedule_repo._create_csv_reader()
    
    # 実際に読み込んでforbidden_cellsを確認
    with open(input_path, 'r', encoding='utf-8-sig') as f:
        _, forbidden_cells = reader_instance.read(f, school)
    
    if forbidden_cells:
        logger.info(f"登録された forbidden_cells: {len(forbidden_cells)}件")
        for (time_slot, class_ref), subjects in list(forbidden_cells.items())[:5]:
            logger.info(f"  - {class_ref} {time_slot}: {subjects}")
    else:
        logger.warning("forbidden_cells が空です！")
    
    return violations


def check_constraint_registration():
    """制約登録プロセスをチェック"""
    logger.info("\n\n=== 制約登録プロセスのチェック ===")
    
    # 制約システムを初期化
    constraint_system = UnifiedConstraintSystem()
    
    # 学校データを読み込む
    school_repo = CSVSchoolRepository(path_config.data_dir)
    school = school_repo.load_school_data("config/base_timetable.csv")
    constraint_system.school = school
    
    # 制約登録サービスを使用
    registration_service = ConstraintRegistrationService()
    
    # 制約を登録
    logger.info("\n制約を登録中...")
    registration_service.register_all_constraints(
        constraint_system,
        path_config.data_dir,
        teacher_absences=None
    )
    
    # 登録された制約を確認
    logger.info("\n登録された制約:")
    for priority, constraints in constraint_system.constraints.items():
        logger.info(f"\n{priority.name} (優先度 {priority.value}):")
        for constraint in constraints:
            logger.info(f"  - {constraint.name}: {constraint.description}")
            if "CellForbiddenSubject" in constraint.name:
                logger.info(f"    → 「非」制約が登録されています！")


def main():
    """メイン処理"""
    violations = analyze_forbidden_constraints()
    check_constraint_registration()
    
    if violations:
        logger.error(f"\n\n❌ 結論: {len(violations)}件の「非」制約違反が存在します")
        logger.error("システムは制約を正しく処理していない可能性があります")
    else:
        logger.info("\n\n✅ 結論: 「非」制約は正しく処理されています")


if __name__ == "__main__":
    main()