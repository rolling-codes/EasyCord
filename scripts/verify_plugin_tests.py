import ast
import sys
from pathlib import Path

def count_test_functions(filepath: Path) -> int:
    try:
        content = filepath.read_text(encoding="utf-8")
        tree = ast.parse(content)
        count = 0
        for node in ast.walk(tree):
            # async def test_... is ast.AsyncFunctionDef, not ast.FunctionDef —
            # count both or every async test goes uncounted.
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
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

    # Some plugins keep their tests in a file that does not match test_<plugin>.py.
    # Map plugin -> actual test filename stem (without the "test_" prefix / ".py").
    test_file_aliases = {
        "levels": "levels_plugin",
        "reminders": "reminder",
    }

    complex_threshold = 20
    simple_threshold = 20

    failed = False

    print("Checking plugin test coverage thresholds...")

    def test_file_for(plugin: str) -> Path:
        stem = test_file_aliases.get(plugin, plugin)
        return tests_dir / f"test_{stem}.py"

    for plugin in complex_plugins:
        test_file = test_file_for(plugin)
        count = count_test_functions(test_file) if test_file.exists() else 0
        if count < complex_threshold:
            print(f"[FAIL] {plugin} plugin requires at least {complex_threshold} tests, found {count}")
            failed = True
        else:
            print(f"[PASS] {plugin} plugin has {count} tests (>= {complex_threshold})")

    for plugin in simple_plugins:
        test_file = test_file_for(plugin)
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
