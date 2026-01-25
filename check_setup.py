"""
Скрипт проверки правильности установки
Запустите после установки зависимостей
"""
import sys
import os


def check_python_version():
    """Проверка версии Python"""
    version = sys.version_info
    print(f"✓ Python {version.major}.{version.minor}.{version.micro}")

    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print("  ⚠️  Предупреждение: Рекомендуется Python 3.10+")
        return False
    return True


def check_dependencies():
    """Проверка установленных зависимостей"""
    dependencies = [
        ('fastapi', 'FastAPI'),
        ('uvicorn', 'Uvicorn'),
        ('sqlalchemy', 'SQLAlchemy'),
        ('aiosqlite', 'aiosqlite'),
        ('pydantic', 'Pydantic'),
        ('loguru', 'Loguru'),
        ('httpx', 'HTTPX'),
        ('csfloat', 'csfloat-api'),
    ]

    all_ok = True
    for module_name, display_name in dependencies:
        try:
            __import__(module_name)
            print(f"✓ {display_name}")
        except ImportError:
            print(f"✗ {display_name} - НЕ УСТАНОВЛЕН")
            all_ok = False

    return all_ok


def check_directories():
    """Проверка структуры директорий"""
    directories = ['bot', 'web', 'web/static', 'web/templates']
    all_ok = True

    for directory in directories:
        if os.path.isdir(directory):
            print(f"✓ Директория {directory}/")
        else:
            print(f"✗ Директория {directory}/ - НЕ НАЙДЕНА")
            all_ok = False

    return all_ok


def check_files():
    """Проверка необходимых файлов"""
    files = [
        'main.py',
        'config.py',
        'database.py',
        'accounts.py',
        'bot/__init__.py',
        'bot/manager.py',
        'bot/outbid_logic.py',
        'bot/advanced_api.py',
        'web/__init__.py',
        'web/app.py',
        'web/templates/index.html',
        'web/static/app.js',
        'requirements.txt',
    ]

    all_ok = True
    for file in files:
        if os.path.isfile(file):
            print(f"✓ {file}")
        else:
            print(f"✗ {file} - НЕ НАЙДЕН")
            all_ok = False

    return all_ok


def check_logs_directory():
    """Проверка директории для логов"""
    if not os.path.exists('logs'):
        print("⚠️  Директория logs/ не найдена")
        print("   Создайте её: mkdir logs")
        return False
    else:
        print("✓ Директория logs/")
        return True


def check_env_file():
    """Проверка .env файла"""
    if os.path.exists('.env'):
        print("✓ Файл .env существует")
        return True
    else:
        print("⚠️  Файл .env не найден (необязательно)")
        print("   Можете создать: cp .env.example .env")
        return True  # Не критично


def main():
    """Главная функция проверки"""
    print("=" * 60)
    print("🔍 Проверка установки CSFloat Outbid Bot")
    print("=" * 60)
    print()

    print("📌 Проверка Python:")
    python_ok = check_python_version()
    print()

    print("📦 Проверка зависимостей:")
    deps_ok = check_dependencies()
    print()

    print("📁 Проверка директорий:")
    dirs_ok = check_directories()
    print()

    print("📄 Проверка файлов:")
    files_ok = check_files()
    print()

    print("📝 Проверка дополнительных файлов:")
    logs_ok = check_logs_directory()
    env_ok = check_env_file()
    print()

    print("=" * 60)
    if python_ok and deps_ok and dirs_ok and files_ok and logs_ok:
        print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
        print()
        print("Можете запустить бота:")
        print("  python main.py")
        print()
        print("Затем откройте: http://localhost:8000")
    else:
        print("❌ НЕКОТОРЫЕ ПРОВЕРКИ НЕ ПРОЙДЕНЫ")
        print()
        print("Рекомендации:")
        if not deps_ok:
            print("  1. Установите зависимости: pip install -r requirements.txt")
        if not logs_ok:
            print("  2. Создайте директорию logs: mkdir logs")
        if not dirs_ok or not files_ok:
            print("  3. Убедитесь что все файлы распакованы правильно")

    print("=" * 60)


if __name__ == "__main__":
    main()
