import argparse
import sys
import os
import tempfile
import shutil
import tarfile
import urllib.request
import json

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
        help='URL-адрес пакета на crates.io'
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
    repo_url = args.repo_url.strip()
    package = args.package.strip()
    if not repo_url:
        errors.append("URL репозитория не может быть пустым")
    elif not repo_url.startswith("https://crates.io/crates/"):
        errors.append("Ссылка должна быть вида https://crates.io/crates/<имя_пакета>")
    if not package:
        errors.append("Имя пакета не может быть пустым")
    if repo_url and package and repo_url.startswith("https://crates.io/crates/"):
        crate_name_from_url = repo_url.rstrip('/').split('/')[-1]
        if crate_name_from_url != package:
            errors.append(
                f"Имя пакета в URL ({crate_name_from_url}) "
                f"не совпадает с --package ({package})"
            )
    if errors:
        print("Ошибки валидации:")
        for error in errors:
            print(f"  - {error}")
        return False
    return True

def get_latest_version(crate_name):
    api_url = f"https://crates.io/api/v1/crates/{crate_name}"
    try:
        with urllib.request.urlopen(api_url) as resp:
            data = json.load(resp)
    except Exception as e:
        print(f"Не удалось получить информацию о крейте {crate_name}: {e}",
              file=sys.stderr)
        sys.exit(1)
    crate_info = data.get("crate", {})
    version = crate_info.get("max_stable_version") or crate_info.get("max_version")
    if not version:
        print(f"Не удалось определить последнюю версию крейта {crate_name}",
              file=sys.stderr)
        sys.exit(1)
    return version

def download_and_unpack(crate_name, version, dest_dir):
    download_url = f"https://crates.io/api/v1/crates/{crate_name}/{version}/download"
    crate_file = os.path.join(dest_dir, f"{crate_name}-{version}.crate")
    try:
        with urllib.request.urlopen(download_url) as resp, open(crate_file, "wb") as f:
            shutil.copyfileobj(resp, f)
    except Exception as e:
        print(f"Не удалось скачать крейт {crate_name} {version}: {e}",
              file=sys.stderr)
        sys.exit(1)
    try:
        with tarfile.open(crate_file, "r:gz") as tar:
            tar.extractall(dest_dir)
    except Exception as e:
        print(f"Не удалось распаковать архив {crate_file}: {e}",
              file=sys.stderr)
        sys.exit(1)
    return dest_dir

def find_cargo_toml(package_name, start_path):
    for root, dirs, files in os.walk(start_path):
        if 'Cargo.toml' not in files:
            continue
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
                    if in_package and line.startswith('name'):
                        if '=' in line:
                            _, value = line.split('=', 1)
                            name_val = value.strip().strip('"\'')
                            if name_val == package_name:
                                return cargo_path
                        break
        except Exception:
            continue
    return None

def extract_dependencies(cargo_path):
    deps = set()
    try:
        with open(cargo_path, 'r', encoding='utf-8') as f:
            in_deps_block = False
            for raw in f:
                line = raw.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('[') and line.endswith(']'):
                    section = line[1:-1].strip()
                    if section == 'dependencies':
                        in_deps_block = True
                    else:
                        dep_name = ''
                        if section.startswith('dependencies.'):
                            dep_name = section[len('dependencies.'):].strip()
                        elif '.dependencies.' in section:
                            dep_name = section.split('.dependencies.', 1)[1].strip()
                        if dep_name:
                            deps.add(dep_name)
                        in_deps_block = False
                    continue
                if in_deps_block:
                    if '=' in line:
                        dep_name = line.split('=', 1)[0].strip()
                        if dep_name:
                            deps.add(dep_name)
    except Exception as e:
        print(f"Ошибка при чтении {cargo_path}: {e}", file=sys.stderr)
    return sorted(deps)

def main():
    args = parse_arguments()
    if not validate_arguments(args):
        sys.exit(1)
    crate_name = args.package
    temp_root = tempfile.mkdtemp(prefix="crate_download_")
    try:
        version = get_latest_version(crate_name)
        work_dir = download_and_unpack(crate_name, version, temp_root)
        cargo_file = find_cargo_toml(crate_name, work_dir)
        if not cargo_file:
            print(f"Cargo.toml с пакетом '{crate_name}' не найден в распакованном крейте.",
                  file=sys.stderr)
            sys.exit(1)
        dependencies = extract_dependencies(cargo_file)
        if dependencies:
            for name in dependencies:
                print(name)
        else:
            print("Не найдено прямых зависимостей пакета.")
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

if __name__ == "__main__":
    main()