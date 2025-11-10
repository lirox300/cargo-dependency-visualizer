import argparse
import sys
import os
import tempfile
import subprocess
import shutil
import re

def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Визуализатор графа зависимостей для Cargo',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--package',
        type=str,
        required=True,
        help='Имя анализируемого пакета'
    )
    parser.add_argument(
        '--repo-url',
        type=str,
        required=True,
        help='URL-адрес репозитория или путь к файлу тестового репозитория'
    )
    parser.add_argument(
        '--test-mode',
        action='store_true',
        help='Режим работы с тестовым репозиторием'
    )
    parser.add_argument(
        '--ascii-tree',
        action='store_true',
        help='Режим вывода зависимостей в формате ASCII-дерева'
    )
    parser.add_argument(
        '--filter',
        type=str,
        default='',
        help='Подстрока для фильтрации пакетов'
    )
    return parser.parse_args()

def validate_arguments(args):
    errors = []
    if not args.package.strip():
        errors.append("Имя пакета не может быть пустым")
    if not args.repo_url.strip():
        errors.append("URL репозитория не может быть пустым")
    elif args.test_mode:
        if not os.path.isdir(args.repo_url):
            errors.append(
                f"В тестовом режиме путь '{args.repo_url}' не существует или не является директорией."
            )
    if errors:
        print("Ошибки валидации:")
        for error in errors:
            print(f"  - {error}")
        return False
    return True

def find_cargo_toml(package_name, start_path):
    name_re = re.compile(r'^\s*name\s*=\s*["\'](.+?)["\']\s*(?:#.*)?$')
    for root, dirs, files in os.walk(start_path):
        if 'Cargo.toml' in files:
            cargo_path = os.path.join(root, 'Cargo.toml')
            try:
                with open(cargo_path, 'r', encoding='utf-8') as f:
                    in_package = False
                    for raw in f:
                        line = raw.strip()
                        if line == '[package]':
                            in_package = True
                            continue
                        if in_package and line.startswith('['):
                            break
                        if in_package:
                            m = name_re.match(line)
                            if m:
                                name_val = m.group(1)
                                if name_val == package_name:
                                    return cargo_path
                                break
            except Exception:
                continue
    return None

def extract_dependencies(cargo_path):
    deps = []
    name_re = re.compile(r'^\s*([^=\s]+)\s*=.*$')
    try:
        with open(cargo_path, 'r', encoding='utf-8') as f:
            in_deps = False
            for raw in f:
                line = raw.strip()
                if not in_deps:
                    if line == '[dependencies]':
                        in_deps = True
                    continue
                if line.startswith('['):
                    break
                if not line or line.startswith('#'):
                    continue
                m = name_re.match(line)
                if m:
                    name = m.group(1).strip()
                    deps.append(name)
    except Exception as e:
        print(f"Ошибка при чтении {cargo_path}: {e}", file=sys.stderr)
    return deps

def main():
    args = parse_arguments()
    if not validate_arguments(args):
        sys.exit(1)
    repo_path = None
    temp_root = None
    try:
        if not args.test_mode:
            temp_root = tempfile.mkdtemp(prefix="repo_clone_")
            repo_path = os.path.join(temp_root, "repo")
            try:
                result = subprocess.run(["git", "clone", args.repo_url, repo_path], capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"Ошибка клонирования репозитория: {result.stderr.strip()}", file=sys.stderr)
                    sys.exit(1)
            except FileNotFoundError:
                print("Git не найден. Установите Git и повторите попытку.", file=sys.stderr)
                sys.exit(1)
        else:
            repo_path = args.repo_url
        cargo_file = find_cargo_toml(args.package, repo_path)
        if not cargo_file:
            print(f"Cargo.toml с пакетом '{args.package}' не найден в репозитории.", file=sys.stderr)
            sys.exit(1)
        dependencies = extract_dependencies(cargo_file)
        if dependencies:
            for name in dependencies:
                print(name)
        else:
            print("Не найдено прямых зависимостей в секции [dependencies].")
    finally:
        if temp_root and os.path.isdir(temp_root):
            shutil.rmtree(temp_root, ignore_errors=True)

if __name__ == "__main__":
    main()