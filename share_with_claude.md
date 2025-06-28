# 時間割生成システムの主要ファイル

以下のファイルをClaude.aiの対話画面に順番にコピー＆ペーストしてください：

## 1. メインエントリーポイント
- `main.py` - システムのエントリーポイント

## 2. 重要な設定ファイル
- `CLAUDE.md` - プロジェクトの詳細説明
- `requirements.txt` - 必要なパッケージ

## 3. コアロジック（優先順位順）
1. `src/application/services/schedule_generation_service.py` - スケジュール生成サービス
2. `src/domain/services/smart_empty_slot_filler_refactored.py` - 空きスロット埋め
3. `src/domain/constraints/base.py` - 制約の基底クラス
4. `src/domain/entities/schedule.py` - スケジュールエンティティ
5. `src/infrastructure/repositories/csv_repository.py` - データ読み込み

## 4. 設定データ（必要に応じて）
- `data/config/basics.csv` - 基本設定
- `data/config/teacher_subject_mapping.csv` - 教師と科目のマッピング
- `data/input/input.csv` - 入力データサンプル
- `data/input/Follow-up.csv` - 週次調整データ

## アップロード手順
1. Claude.aiで新しい会話を開始
2. 「学校時間割生成システムのコードを共有します」と伝える
3. 上記のファイルを順番にコピー＆ペースト
4. 各ファイルの前に「ファイル名: xxx.py」と明記する