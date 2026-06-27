import ast
import sys
from pathlib import Path

def count_test_functions(filepath: Path) -> int:
    try:
        content = filepath.read_text(encoding="utf-8")
        tree = ast.parse(content)
        count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                count += 1
        return count
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return 0

def main():
    base_dir = Path(__file__).parent.parent
    tests_dir = base_dir / "tests"
    
    if not tests_dir.exists():
        print(f"Tests directory not found: {tests_dir}")
        sys.exit(1)
        
    complex_plugins = ["ai_moderator", "tickets", "birthday", "levels", "reminders"]
    simple_plugins = ["suggestions", "tags", "starboard"]
    
    complex_threshold = 20
    simple_threshold = 8
    
    failed = False
    
    print("Checking plugin test coverage thresholds...")
    
    for plugin in complex_plugins:
        test_file = tests_dir / f"test_{plugin}.py"
        count = count_test_functions(test_file) if test_file.exists() else 0
        if count < complex_threshold:
            print(f"[FAIL] {plugin} plugin requires at least {complex_threshold} tests, found {count}")
            failed = True
        else:
            print(f"[PASS] {plugin} plugin has {count} tests (>= {complex_threshold})")
            
    for plugin in simple_plugins:
        test_file = tests_dir / f"test_{plugin}.py"
        count = count_test_functions(test_file) if test_file.exists() else 0
        if count < simple_threshold:
            print(f"[FAIL] {plugin} plugin requires at least {simple_threshold} tests, found {count}")
            failed = True
        else:
            print(f"[PASS] {plugin} plugin has {count} tests (>= {simple_threshold})")
            
    if failed:
        print("\nTest coverage check failed. Please add more tests to the failing plugins.")
        sys.exit(1)
    else:
        print("\nAll plugin test coverage thresholds met! [SUCCESS]")
        sys.exit(0)

if __name__ == "__main__":
    main()
