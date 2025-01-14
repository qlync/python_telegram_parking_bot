# Telegram-бот для бронирования парковочных мест

## Описание

Проект представляет собой **Telegram-бота**, предназначенного для управления бронированием парковочных мест. Бот позволяет пользователям бронировать места на определённые даты, поддерживает как **временные**, так и **перманентные** бронирования, а также предоставляет VIP-пользователям дополнительные привилегии по управлению бронями. Бот использует базу данных SQLite для хранения и обработки данных о бронированиях.

## Функциональные возможности

- **Роли пользователей**:
  - **VIP-пользователи**: могут бронировать любые места, перезаписывать любые типы бронирования других пользователей, а также удалять как временные, так и перманентные брони.
  - **Обычные пользователи**: могут бронировать только свободные места и управлять только своими бронированиями.

- **Типы бронирований**:
  - **Перманентные бронирования**: закрепляются за пользователем на определённый день недели (например, каждый понедельник).
  - **Временные бронирования**: действуют на конкретную дату с возможностью автоматического освобождения места в конце недели.

- **Управление бронированиями**:
  - Просмотр всех забронированных мест на выбранный день.
  - Оформление новых бронирований или отмена существующих.
  - Автоматическое восстановление перманентных броней после завершения временных.

## Установка и настройка

### Требования

- **Python 3.8+**
- **SQLite** (встроен в модуль `sqlite3` Python)
- **Зависимости Python**:
  - `python-telegram-bot` (установка через `pip install python-telegram-bot`)
  - `sqlite3` (встроенный модуль Python)
  - Дополнительные зависимости указаны в `requirements.txt`.

### Установка

**Установите зависимости**

pip install -r requirements.txt

**Создайте бота**:

Бот создается в телеграме. Перейдите по ссылке [BotFather] (https://t.me/BotFather) @BotFather.

Скопируйте `API_TOKEN` созданного бота в `config.py`.

Создайте кнопки для своего бота через команды BotFather:
  - `start - Main Menu`
  - `info - Information`

**Настройте бота**:
- API_TOKEN = 'PLACE_YOUR_API_TOKEN_HERE'
- VIP_USERS = [123456789, 987654321]
- WHITELIST_USERS = [121212121, 232323232, 343434343]

**Запустите бота**:
python bot.py

## TO BE

### 1. Установить в качестве службы

**Cоздаем файл telegram-bot.service**
- touch /etc/systemd/system/telegram-bot.service

**Задаем верные права для файла**
- chmod 664 /etc/systemd/system/telegram-bot.service

**Далее добавляем следующие строчки в файл /etc/systemd/system/telegram-bot.service**:
```ini
[Unit]
Description=Telegram bot
After=network.target
[Service]
ExecStart=/usr/bin/python3 /root/bot.py
[Install]
WantedBy=multi-user.target
```

**Перезагрузим конфигурацию systemd**
- systemctl daemon-reload

**Добавим нашу службу telegram-bot в автозагрузку**
- systemctl enable telegram-bot.service

### 2. Перезапускать telegram-bot.service через cron
crontab -e
10 0 * * * systemctl restart telegram-bot.service

### 3. Мониторить сетевые доступы до api.telegram.org
Необходимо настроить мониторинг сетевых доступов до api.telegram.org.
В случае обрыва соединения, службу необходимо перезапускать.

