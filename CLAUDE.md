# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🔨 最重要ルール - 新しいルールの追加プロセス

ユーザーから今回限りではなく常に対応が必要だと思われる指示を受けた場合：
1. 「これを標準のルールにしますか？」と質問する
2. YESの回答を得た場合、CLAUDE.mdに追加ルールとして記載する
3. 以降は標準ルールとして常に適用する

## ⚠️ 絶対に守るべきルール - 固定科目の保護

**以下の科目は絶対に変更してはいけません（システムで自動保護されています）：**
- 欠（欠課）
- YT（特別活動）
- 学、学活（学級活動）
- 総、総合（総合的な学習の時間）
- 道、道徳（道徳）
- 学総（学年総合）
- 行、行事（行事）

これらの科目は学校運営上の固定された時間であり、`FixedSubjectProtectionPolicy`により自動的に保護されます。
空きスロットを埋める際も、これらの科目が既に配置されている場合は変更できないようシステムレベルでブロックされています。

## 📋 システムの主要機能（2025年6月リファクタリング版）

### 1. 固定科目の完全保護
- 上記の固定科目は一度配置されると変更不可
- `Schedule.assign()`メソッドで自動的にチェック
- 変更を試みると`ValueError`例外が発生

### 2. テスト期間の自動保護（部分実装）
- Follow-up.csvからテスト期間を自動読み取り
- テスト期間中は「行」以外の科目配置を制限
- 現在は違反検出のみ（配置阻止は未完成）

### 3. 入力データの自動修正
- 全角スペース、特殊文字の自動除去
- 科目略称の正式名称への自動変換
- CSVファイルの前処理機能

### 4. 高度な制約管理
- 制約優先度: CRITICAL > HIGH > MEDIUM > LOW
- 配置前チェックと事後検証の分離
- 21種類の制約を統一システムで管理

### 5. 自然言語解析
- Follow-up.csvの自然言語を解析
- 教員不在、会議、テスト期間を自動抽出


## ⚠️ 既知の問題と対処法

### テスト期間保護が完全でない
現在、テスト期間の制約は違反を検出しますが、配置を完全に阻止できていません。
Follow-up.csvに「テストなので時間割の変更をしないでください」と記載されている期間でも、
通常科目が配置される場合があります。

**暫定対処法：**
1. 生成後に`check_violations.py`でテスト期間違反を確認
2. 違反がある場合は手動で「行」に変更
3. または、input.csvに事前に「行」を配置してから生成

「テスト」科目は固定科目として登録済みで、一度配置されると変更不可となります。

## Quick Start

To generate a complete timetable in one command:
```bash
python3 main.py generate
```

This will:
1. Generate a timetable using the advanced CSP algorithm
2. Automatically fill all empty slots
3. Output a complete timetable to `data/output/output.csv`

## Commands

### Running the Timetable Generator (v3.0)
```bash
# Generate a complete timetable with advanced CSP algorithm and automatic empty slot filling (default)
python3 main.py generate

# Generate with legacy algorithm (if needed)
python3 main.py generate --use-legacy

# Generate with custom parameters
python3 main.py generate --max-iterations 200 --soft-constraints

# Generate with all optimizations enabled
python3 main.py generate --enable-all-optimizations

# Generate with specific optimizations
python3 main.py generate --optimize-meeting-times  # 会議時間最適化
python3 main.py generate --optimize-gym-usage      # 体育館使用最適化
python3 main.py generate --optimize-workload       # 教師負担最適化
python3 main.py generate --use-support-hours       # 5組時数表記

# Validate an existing timetable
python3 main.py validate data/output/output.csv

# Check violations
python3 check_violations.py

# Clean up project files
python3 cleanup_project.py --force

# Note: Use python3 instead of python on macOS
```

### Key Command Options
- `--max-iterations`: Number of optimization iterations (default: 100)
- `--soft-constraints`: Enable soft constraint checking
- `--use-legacy`: Use legacy generation algorithm (default: advanced CSP)
- `--enable-all-optimizations`: Enable all optimization features
- `--optimize-meeting-times`: Enable meeting time optimization (会議時間最適化)
- `--optimize-gym-usage`: Enable gym usage optimization (体育館使用最適化)
- `--optimize-workload`: Enable teacher workload balance optimization (教師負担最適化)
- `--use-support-hours`: Enable special support class hour notation (5組時数表記)
- `--verbose/-v`: Enable detailed logging
- `--quiet/-q`: Show only warnings and errors

## Architecture Overview

This is version 3.0 of the school timetable generation system using Clean Architecture principles with an advanced CSP (Constraint Satisfaction Problem) algorithm as the default generation method.

### Major Changes in v3.0
1. **Advanced CSP as Default**: The high-performance CSP algorithm is now the standard generation method
2. **Automatic Empty Slot Filling**: Timetables are always generated complete in one step
3. **Streamlined Codebase**: Removed 112 unused/backup files and legacy algorithms
4. **Optimized Performance**: Refactored core algorithms for better efficiency
5. **Simplified Architecture**: Cleaner structure with only essential components
6. **Centralized Logging**: New LoggingConfig system for unified log management
7. **Service-Oriented Refactoring**: Modular services with clear responsibilities

### Key Features
1. **Advanced CSP Algorithm**: 
   - Prioritizes jiritsu (自立活動) constraints
   - Uses backtracking for optimal solutions
   - Local search optimization
   - Typically achieves 0 constraint violations

2. **Unified Constraint System**: All constraints managed centrally with priority levels
3. **Path Management**: Centralized path configuration
4. **Exchange Class Support**: Proper PE hour allocation for support classes

### Layer Structure
1. **Presentation Layer** (`src/presentation/`): CLI interface
2. **Application Layer** (`src/application/`): Use cases and service orchestration
3. **Domain Layer** (`src/domain/`): Core business logic, entities, and constraints
4. **Infrastructure Layer** (`src/infrastructure/`): File I/O, parsers, and external integrations

### Core Domain Concepts

#### Entity Relationships
- **School**: Central entity managing classes, teachers, subjects
- **Schedule**: The timetable being generated
- **Grade5Unit**: Special synchronized unit for Grade 5 classes (1-5, 2-5, 3-5)

#### Constraint Priority Levels
- **CRITICAL**: Must never be violated (e.g., Monday 6th period "欠")
- **HIGH**: Very important constraints (e.g., teacher conflicts, jiritsu requirements)
- **MEDIUM**: Important but can be relaxed if necessary
- **LOW**: Preferences and soft constraints

#### Special Rules
1. **Jiritsu Constraint**: When exchange classes (支援学級) have 自立, parent classes MUST have 数 or 英
2. **Grade 5 Synchronization**: Classes 1-5, 2-5, and 3-5 must have identical subjects
   - **重要**: 5組（1年5組、2年5組、3年5組）は合同授業として3クラスが一緒に授業を受けるため、1人の教員が3クラスを同時に担当することは正常な運用です。これは制約違反ではありません。
3. **Exchange Classes**: Paired classes must coordinate specific subjects
4. **Fixed Periods**: 
   - Monday 6th: "欠" (absence) for all classes
   - Tuesday/Wednesday/Friday 6th: "YT"
5. **Gym Limitation**: Only 1 PE class at a time due to single gym

### Key Services

#### AdvancedCSPScheduleGenerator (Default)
The main generation algorithm that:
1. Analyzes and places jiritsu activities first
2. Synchronizes Grade 5 classes
3. Places remaining subjects using CSP techniques
4. Optimizes with local search
5. Ensures all constraints are satisfied

#### ScheduleGenerationService
Orchestrates the generation process:
- Uses AdvancedCSPScheduleGenerator by default
- Automatically fills empty slots using SmartEmptySlotFiller
- Falls back to legacy algorithm with --use-legacy flag
- Manages statistics and logging

#### Supporting Services
- **SmartEmptySlotFiller**: Intelligent empty slot filling with multiple strategies (integrated into main generation)
- **ExchangeClassSynchronizer**: Manages exchange class coordination
- **Grade5SynchronizerRefactored**: Handles Grade 5 synchronization

### Data File Organization

All data files are under `timetable_v5/data/`:

#### Configuration (`data/config/`)
- `base_timetable.csv`: Standard hours per subject per class
- `basics.csv`: Constraint definitions
- `default_teacher_mapping.csv`: Teacher assignments
- `exchange_class_pairs.csv`: Exchange class relationships
- Other configuration files...

#### Input (`data/input/`)
- `input.csv`: Initial/desired timetable (optional)
- `Follow-up.csv`: Weekly adjustments and teacher absences

#### Output (`data/output/`)
- `output.csv`: Generated timetable (main output)

### Important Implementation Notes

1. **Default Algorithm**: Advanced CSP is now the default - no flag needed
2. **One-Step Generation**: Empty slot filling is always integrated into the main generation process
3. **Performance**: Typical generation completes in < 10 seconds
4. **Constraint Satisfaction**: Usually achieves 0 violations
5. **Path Management**: All paths managed through path_config module
6. **Teacher Absences**: Loaded from Follow-up.csv
7. **Meeting Times**: 
   - Default: HF(火4), 企画(火3), 特会(水2), 生指(木3)
   - Only meeting participants are marked unavailable
   - Meeting times do NOT display "行" in the timetable

### Logging Configuration

The system uses a centralized logging configuration (`src/infrastructure/config/logging_config.py`):

1. **Production Mode** (default): Shows only warnings and errors
2. **Development Mode** (`--verbose`): Shows detailed debug information
3. **Quiet Mode** (`--quiet`): Shows only errors

Module-specific logging levels are configured to reduce noise:
- Application and domain services: INFO level
- Infrastructure (parsers, repositories): WARNING level
- Constraint checks: WARNING level (only violations shown)

### Running Tests and Checks

```bash
# Check for constraint violations
python3 check_violations.py

# Fill empty slots (if needed)
python3 fill_empty_slots.py

# Other analysis and fix scripts are available in scripts/
```

### Project Cleanup

A cleanup script is available to remove unnecessary files:
```bash
python3 cleanup_project.py --force
```

This removes:
- Backup files (*.backup*, *.bak, etc.)
- Unused algorithm implementations
- Old output files
- Temporary files


### スクリプトの整理

ルートディレクトリのスクリプトは以下のように整理されています：

#### scripts/
- **fixes/**: 各種修正スクリプト（fix_*.py）
- **analysis/**: 分析・チェックスクリプト（analyze_*.py, check_*.py）
- **utilities/**: ユーティリティスクリプト（cleanup_project.py等）

よく使うスクリプトはルートに残してあります：
- `main.py`: メインエントリーポイント
- `fill_empty_slots.py`: 空きコマ埋めスクリプト

### Directory Structure (After Refactoring)
```
timetable_v5/
├── main.py                    # Entry point
├── check_violations.py        # Violation checker (symlink to scripts/analysis/)
├── fill_empty_slots.py        # Empty slot filler (symlink to scripts/utilities/)
├── setup.py                   # Package setup
├── requirements.txt           # Production dependencies
├── requirements-dev.txt       # Development dependencies
├── README.md                  # Project documentation
├── CLAUDE.md                  # This file
├── .gitignore                # Git exclusions
│
├── src/                       # Source code (Clean Architecture)
│   ├── application/          # Use cases and services
│   │   ├── services/        # Application services
│   │   └── use_cases/       # Use cases
│   ├── domain/              # Core business logic
│   │   ├── constraints/     # Constraint implementations
│   │   ├── entities/        # Domain entities
│   │   ├── services/        # Domain services (including generators)
│   │   └── value_objects/   # Value objects
│   ├── infrastructure/      # External interfaces
│   │   ├── config/         # Configuration
│   │   ├── parsers/        # File parsers
│   │   └── repositories/   # Data access
│   └── presentation/        # CLI interface
│       └── cli/            # Command line interface
│
├── scripts/                   # Utility scripts
│   ├── analysis/            # Analysis scripts
│   ├── checks/             # Check scripts
│   ├── fixes/              # Fix scripts
│   └── utilities/          # Other utilities
│
├── data/
│   ├── config/             # Configuration files
│   ├── input/              # Input files
│   └── output/             # Generated timetables
│
├── tests/                    # Test code
└── docs/                     # Documentation
```

### Version History
- **v1.0**: Initial implementation with basic constraints
- **v2.0**: Added unified constraint system and enhanced architecture
- **v3.0**: Advanced CSP as default, major refactoring and cleanup (current)