#!/usr/bin/env python3
"""インポートパスのテスト"""

import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_ultrathink_imports():
    """ultrathinkモジュールのインポートテスト"""
    print("=== Ultrathinkインポートテスト ===\n")
    
    # 1. optimizer
    try:
        from src.application.services.ultrathink.optimizer.intelligent_schedule_optimizer import IntelligentScheduleOptimizer
        print("✓ IntelligentScheduleOptimizer imported successfully")
    except ImportError as e:
        print(f"✗ IntelligentScheduleOptimizer import failed: {e}")
    
    # 2. parallel
    try:
        from src.application.services.ultrathink.parallel.parallel_optimization_engine import ParallelOptimizationEngine
        print("✓ ParallelOptimizationEngine imported successfully")
    except ImportError as e:
        print(f"✗ ParallelOptimizationEngine import failed: {e}")
    
    # 3. preference
    try:
        from src.application.services.ultrathink.preference.teacher_preference_learning_system import TeacherPreferenceLearningSystem
        print("✓ TeacherPreferenceLearningSystem imported successfully")
    except ImportError as e:
        print(f"✗ TeacherPreferenceLearningSystem import failed: {e}")
    
    # 4. hybrid_schedule_generator
    try:
        from src.application.services.ultrathink.hybrid_schedule_generator import HybridScheduleGenerator
        print("✓ HybridScheduleGenerator imported successfully")
    except ImportError as e:
        print(f"✗ HybridScheduleGenerator import failed: {e}")
    
    # 5. hybrid_schedule_generator_v8
    try:
        from src.application.services.ultrathink.hybrid_schedule_generator_v8 import HybridScheduleGeneratorV8
        print("✓ HybridScheduleGeneratorV8 imported successfully")
    except ImportError as e:
        print(f"✗ HybridScheduleGeneratorV8 import failed: {e}")
    
    # 6. ultrathink package
    try:
        import src.application.services.ultrathink
        print("✓ ultrathink package imported successfully")
    except ImportError as e:
        print(f"✗ ultrathink package import failed: {e}")
    
    print("\n=== 共有ユーティリティインポートテスト ===\n")
    
    # shared utilities
    try:
        from src.shared.utils.csv_operations import CSVOperations
        from src.shared.mixins.logging_mixin import LoggingMixin
        from src.shared.utils.path_utils import PathUtils
        from src.shared.utils.validation_utils import ValidationUtils
        print("✓ All shared utilities imported successfully")
    except ImportError as e:
        print(f"✗ Shared utilities import failed: {e}")
    
    print()

if __name__ == "__main__":
    test_ultrathink_imports()
    print("インポートテスト完了")