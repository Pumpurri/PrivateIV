# extract_code.py

from pathlib import Path

# === CONFIG: Add your target file paths here ===
FILES_TO_EXTRACT = [
    # "backend/users/models.py",
    # "backend/users/tests/factories.py",
    # "backend/users/tests/test_users.py",
    
    # "backend/portfolio/models/holding.py",
    # "backend/portfolio/models/portfolio.py",
    # "backend/portfolio/models/transaction.py",
    # "backend/portfolio/services/transaction_service.py",
    # "backend/portfolio/tests/factories.py",
    # "backend/portfolio/tests/conftest.py",
    # "backend/portfolio/tests/models/test_holding.py",
    # "backend/portfolio/tests/models/test_portfolio.py",
    # "backend/portfolio/tests/models/test_transaction.py",
    # "backend/portfolio/tests/models/test_realized_pnl.py",
    # "backend/portfolio/tests/models/test_performance.py",
    # "backend/portfolio/tests/models/test_daily_snapshot.py",
    # "backend/portfolio/tests/services/test_transaction_service.py",
    # "backend/portfolio/tests/services/test_performance_service.py",
    # "backend/portfolio/tests/services/test_snapshot_service.py",
    # "backend/portfolio/tests/tasks/test_snapshot_tasks.py",

    # "backend/portfolio/tasks.py",
    # "backend/portfolio/calculators/returns.py",
    # "backend/portfolio/calculators/risk.py",
    # "backend/portfolio/models/daily_snapshot.py",
    # "backend/portfolio/models/performance.py",
    # "backend/portfolio/models/realized_pnl.py",
    # "backend/portfolio/services/performance_service.py",
    # "backend/portfolio/services/snapshot_service.py",
    # "backend/portfolio/services/transaction_service.py",

    # "backend/portfolio/serializers/transaction_serializers.py",
    # "backend/portfolio/views/transaction_views.py",
    # "backend/portfolio/urls.py",
    # "backend/portfolio/tests/views/test_transaction_views.py",

    # "backend/portfolio/signals.py",
    # "backend/portfolio/apps.py",
    
    # "backend/stocks/models.py",
    # "backend/stocks/tests/factories.py",
    # "backend/stocks/tests/test_stocks.py",

    # "backend/portfolio/__init__.py",
    # "backend/portfolio/models/__init__.py",
    # "backend/portfolio/services/__init__.py",

    "backend/portfolio/models/__init__.py",
    "backend/portfolio/models/portfolio.py", 
    "backend/portfolio/models/holding.py",
    "backend/portfolio/models/transaction.py",
    "backend/portfolio/models/daily_snapshot.py", 
    "backend/portfolio/models/holding_snapshot.py",
    "backend/portfolio/models/performance.py", 
    "backend/portfolio/models/realized_pnl.py",
    "backend/portfolio/models/historical_price.py", 

    "backend/portoflio/services/__init__.py",
    "backend/portfolio/services/transaction_service.py",
    "backend/portfolio/services/performance_service.py",
    "backend/portfolio/services/snapshot_service.py",
    "backend/portfolio/services/historical_valuation.py",

    "backend/portfolio/serializers/transaction_serializers.py",
    "backend/portfolio/views/transaction_views.py",

    "backend/stocks/models.py",
    "backend/users/models.py",

    # "backend/portfolio/tests/services/test_transaction_service.py"
]

OUTPUT_FILE = "code_output.txt"

def extract_files(file_paths, output_path):
    output_lines = []
    
    for filepath in file_paths:
        file_path = Path(filepath)
        output_lines.append(f"{filepath}:\n")
        
        if file_path.exists():
            with open(file_path, "r") as f:
                output_lines.append(f.read())
        else:
            output_lines.append("[File not found]\n")
        
        output_lines.append("\n" + "-" * 80 + "\n\n")
    
    with open(output_path, "w") as out:
        out.writelines(output_lines)
    
    print(f"✅ Code written to '{output_path}'")

if __name__ == "__main__":
    extract_files(FILES_TO_EXTRACT, OUTPUT_FILE)
