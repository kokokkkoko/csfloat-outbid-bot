# Инструкция по установке CSFloat Outbid Bot

## Требования
- Docker Desktop (скачать: https://www.docker.com/products/docker-desktop/)
- Git (скачать: https://git-scm.com/downloads)

---

## Шаг 1: Скачать проект

Открой **командную строку** (CMD) или **PowerShell** и выполни:

```bash
git clone https://github.com/kokokkkoko/csfloat-outbid-bot.git
```

Затем перейди в папку проекта:

```bash
cd csfloat-outbid-bot
```

---

## Шаг 2: Создать файл настроек

Скопируй файл примера:

**Windows (CMD):**
```bash
copy .env.example .env
```

**Windows (PowerShell):**
```bash
Copy-Item .env.example .env
```

---

## Шаг 3: Настроить секретный ключ

Открой файл `.env` в блокноте:

```bash
notepad .env
```

Найди строку:
```
JWT_SECRET_KEY=your-super-secret-key-change-in-production-123
```

Замени её на свой секретный ключ (любая длинная случайная строка):
```
JWT_SECRET_KEY=мой-супер-секретный-ключ-12345-abcdef-67890
```

**Сохрани файл и закрой.**

---

## Шаг 4: Запустить бота

Убедись что **Docker Desktop запущен** (иконка кита в трее).

Выполни команду:

```bash
docker-compose up -d
```

Подожди пока скачаются образы и запустится контейнер (1-3 минуты в первый раз).

---

## Шаг 5: Открыть бота

Открой в браузере:

```
http://localhost:8000
```

---

## Шаг 6: Зарегистрироваться

1. Нажми **"Register"** (или перейди на http://localhost:8000/register)
2. Введи логин, email и пароль
3. Войди в систему

---

## Шаг 7: Добавить CSFloat аккаунт

1. В разделе **"Accounts"** нажми **"Add Account"**
2. Введи:
   - **Name:** любое имя (например "Main")
   - **API Key:** твой CSFloat API ключ (получить на https://csfloat.com/api-key)
   - **Proxy:** оставь пустым (или введи прокси если есть)
3. Нажми **"Save"**
4. Нажми **"Test"** чтобы проверить подключение
5. Нажми **"Sync"** чтобы загрузить твои buy orders

---

## Шаг 8: Запустить бота

Нажми кнопку **"Start Bot"** в верхней части страницы.

Готово! Бот будет автоматически перебивать конкурентов.

---

## Полезные команды

### Остановить бота:
```bash
docker-compose down
```

### Перезапустить бота:
```bash
docker-compose restart
```

### Посмотреть логи:
```bash
docker-compose logs -f
```

### Обновить до новой версии:
```bash
git pull
docker-compose down
docker-compose up -d --build
```

---

## Проблемы?

### "Cannot connect to the Docker daemon"
→ Убедись что Docker Desktop запущен

### "Port 8000 already in use"
→ Измени порт в docker-compose.yml: `"8001:8000"` вместо `"8000:8000"`

### "Connection refused" при тесте аккаунта
→ Проверь правильность API ключа CSFloat

### Забыл пароль
→ Удали файл `bot.db` и зарегистрируйся заново:
```bash
del bot.db
docker-compose restart
```

---

## Контакты

Если что-то не работает — пиши мне!
