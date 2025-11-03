import argparse
import sys

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
    if errors:
        print("Ошибки валидации:")
        for error in errors:
            print(f"  - {error}")
        return False
    return True

def print_configuration(args):
    print("=" * 60)
    print("Конфигурация визуализатора зависимостей Cargo")
    print("=" * 60)
    print(f"Имя пакета:           {args.package}")
    print(f"URL репозитория:      {args.repo_url}")
    print(f"Тестовый режим:       {'Да' if args.test_mode else 'Нет'}")
    print(f"Режим ASCII-дерева:   {'Да' if args.ascii_tree else 'Нет'}")
    print(f"Фильтр пакетов:       {args.filter if args.filter else '(не задан)'}")
    print("=" * 60)

def main():
    args = parse_arguments()
    if not validate_arguments(args):
        sys.exit(1)
    print_configuration(args)

if __name__ == "__main__":
    main()