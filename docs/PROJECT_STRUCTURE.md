# プロジェクト構造

```
timetable_v4/
├── main.py                    # メインエントリーポイント
├── CLAUDE.md                  # Claude用の指示書
├── README.md                  # プロジェクト説明書
├── IMPROVEMENTS_v4.md         # v4での改善内容
├── requirements.txt           # 依存パッケージ（将来用）
├── .gitignore                 # Git除外設定
│
├── data/                      # データファイル
│   ├── config/               # 設定ファイル
│   │   ├── base_timetable.csv      # 標準時数
│   │   ├── basics.csv              # 基本制約
│   │   ├── meeting_members.csv     # 会議メンバー
│   │   └── ...                     # その他設定
│   ├── input/                # 入力ファイル
│   │   ├── input.csv              # 初期時間割
│   │   └── Follow-up.csv          # 週次調整
│   └── output/               # 出力ファイル
│       └── output.csv             # 生成結果
│
├── src/                       # ソースコード
│   ├── domain/               # ビジネスロジック
│   │   ├── entities/         # エンティティ
│   │   ├── services/         # ドメインサービス
│   │   ├── constraints/      # 制約定義
│   │   └── value_objects/    # 値オブジェクト
│   ├── application/          # アプリケーション層
│   │   ├── services/         # アプリケーションサービス
│   │   └── use_cases/        # ユースケース
│   ├── infrastructure/       # インフラ層
│   │   ├── repositories/     # リポジトリ実装
│   │   ├── parsers/          # パーサー
│   │   └── documentation/    # ドキュメント管理
│   └── presentation/         # プレゼンテーション層
│       └── cli/              # CLIインターフェース
│
├── scripts/                   # 補助スクリプト
│   ├── debug/                # デバッグツール
│   │   ├── trace_generation.py
│   │   ├── trace_subject_change.py
│   │   └── trace_thursday_error.py
│   └── README.md
│
├── logs/                      # ログファイル
│   └── .gitkeep
│
├── docs/                      # ドキュメント
│   └── analysis/             # 分析資料
│       └── timetable_comparison_analysis.md
│
└── tests/                     # テストコード（将来用）
```

## ファイル整理の内容

### ルートフォルダに残すファイル
- `main.py` - プログラムのエントリーポイント
- `CLAUDE.md` - Claude用の指示書
- `README.md` - プロジェクトの説明
- 設定ファイル（`.gitignore`, `requirements.txt`など）

### 移動したファイル
1. **ログファイル** → `/logs/`
   - `*.log` ファイルはすべて logs ディレクトリへ

2. **デバッグスクリプト** → `/scripts/debug/`
   - `trace_*.py` スクリプト
   - インポートパスも修正済み

3. **分析ドキュメント** → `/docs/analysis/`
   - `timetable_comparison_analysis.md`

## 実行方法

### メインプログラム
```bash
python3 main.py --data-dir data/ generate
```

### デバッグスクリプト
```bash
# プロジェクトルートから実行
python3 scripts/debug/trace_generation.py
```

すべてのスクリプトはプロジェクトルートからの相対パスで動作するよう修正されています。