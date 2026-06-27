import os
from pathlib import Path

pyright_header = "# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportMissingTypeArgument=false, reportOptionalCall=false, reportOperatorIssue=false, reportCallIssue=false, reportGeneralTypeIssues=false, reportOptionalMemberAccess=false\n"

def process_tests():
    tests_dir = Path("tests")
    for file in tests_dir.rglob("test_*.py"):
        content = file.read_text(encoding="utf-8")
        if not content.startswith("# pyright:"):
            # Insert after docstring if present, or just at the top
            file.write_text(pyright_header + content, encoding="utf-8")
            print(f"Patched {file}")

if __name__ == "__main__":
    process_tests()
