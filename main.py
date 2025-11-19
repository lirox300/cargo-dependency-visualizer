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
        help='URL-адрес пакета на crates.io или путь к файлу в test-mode'
    )
    parser.add_argument(
        '--test-mode',
        action='store_true',
        help='Режим работы с локальным тестовым файлом графа зависимостей'
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
    if not package:
        errors.append("Имя пакета не может быть пустым")
    if args.test_mode:
        if not repo_url:
            errors.append("Путь к файлу графа не может быть пустым")
        elif not os.path.isfile(repo_url):
             errors.append(f"Файл не найден: {repo_url}")
    else:
        if not repo_url:
            errors.append("URL репозитория не может быть пустым")
        elif not repo_url.startswith("https://crates.io/crates/"):
            errors.append("Ссылка должна быть вида https://crates.io/crates/<имя_пакета>")
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
    req = urllib.request.Request(
        api_url,
        headers={'User-Agent': 'cargo-dependency-visualizer'}
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
    except Exception as e:
        raise ValueError(f"Не удалось получить информацию о крейте {crate_name}: {e}")
    crate_info = data.get("crate", {})
    version = crate_info.get("max_stable_version") or crate_info.get("max_version")
    if not version:
        raise ValueError(f"Не удалось определить последнюю версию крейта {crate_name}")
    return version

def download_and_unpack(crate_name, version, dest_dir):
    download_url = f"https://crates.io/api/v1/crates/{crate_name}/{version}/download"
    req = urllib.request.Request(
        download_url,
        headers={'User-Agent': 'cargo-dependency-visualizer'}
    )
    crate_file = os.path.join(dest_dir, f"{crate_name}-{version}.crate")
    try:
        with urllib.request.urlopen(req) as resp, open(crate_file, "wb") as f:
            shutil.copyfileobj(resp, f)
    except Exception as e:
        raise ValueError(f"Не удалось скачать крейт {crate_name} {version}: {e}")
    try:
        with tarfile.open(crate_file, "r:gz") as tar:
            tar.extractall(dest_dir)
    except Exception as e:
        raise ValueError(f"Не удалось распаковать архив {crate_file}: {e}")
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

def load_test_graph(file_path):
    graph = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split(':')
                if len(parts) == 2:
                    package = parts[0].strip()
                    deps_str = parts[1].strip()
                    if deps_str:
                        deps = [d.strip() for d in deps_str.split()]
                        graph[package] = deps
                    else:
                        graph[package] = []
    except Exception as e:
        print(f"Ошибка при чтении файла графа: {e}", file=sys.stderr)
        sys.exit(1)
    return graph

def get_dependencies_from_crates_io(package_name, temp_root, cache):
    if package_name in cache:
        return cache[package_name]
    try:
        version = get_latest_version(package_name)
        work_dir = download_and_unpack(package_name, version, temp_root)
        cargo_file = find_cargo_toml(package_name, work_dir)
        if not cargo_file:
            cache[package_name] = []
            return []
        dependencies = extract_dependencies(cargo_file)
        cache[package_name] = dependencies
        return dependencies
    except Exception as e:
        cache[package_name] = []
        return []

def build_dependency_graph_dfs(start_package, get_deps_func, filter_substr=''):
    graph = {}
    visited = set()
    cycles = []
    stack = [(start_package, [start_package])]
    while stack:
        node, path = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        deps = get_deps_func(node)
        if filter_substr:
            deps = [d for d in deps if filter_substr not in d]
        graph[node] = deps
        for dep in deps:
            if dep in path:
                cycles.append((node, dep))
            elif dep not in visited:
                stack.append((dep, path + [dep]))
    return graph, cycles

def main():
    args = parse_arguments()
    if not validate_arguments(args):
        sys.exit(1)
    package_name = args.package
    filter_substr = args.filter
    if filter_substr and filter_substr in package_name:
        print(
            f"Ошибка: стартовый пакет '{package_name}' содержит "
            f"фильтр-подстроку '{filter_substr}'.",
            file=sys.stderr
        )
        sys.exit(1)
    if args.test_mode:
        test_graph = load_test_graph(args.repo_url)
        if package_name not in test_graph:
            print(f"Ошибка: пакет '{package_name}' не найден в тестовом графе", file=sys.stderr)
            sys.exit(1)
        graph, cycles = build_dependency_graph_dfs(
            package_name,
            lambda pkg: test_graph.get(pkg, []),
            filter_substr
        )
    else:
        temp_root = tempfile.mkdtemp(prefix="crate_download_")
        cache = {}
        try:
            try:
                get_latest_version(package_name)
            except Exception as e:
                print(e, file=sys.stderr,)
                sys.exit(1)
            graph, cycles = build_dependency_graph_dfs(
                package_name,
                lambda pkg: get_dependencies_from_crates_io(pkg, temp_root, cache),
                filter_substr
            )
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)
    print(f"Граф зависимостей для пакета '{package_name}':")
    if filter_substr:
        print(f"(из графа исключены все пакеты, имя которых содержит подстроку '{filter_substr}')")
    for pkg in sorted(graph.keys()):
        deps = graph[pkg]
        if deps:
            print(f"{pkg}: {', '.join(deps)}")
        else:
            print(f"{pkg}: (нет зависимостей)")
    if cycles:
        print("Обнаружены циклические зависимости:")
        for pkg_from, pkg_to in cycles:
            print(f"{pkg_from} <-> {pkg_to}")

if __name__ == "__main__":
    main()