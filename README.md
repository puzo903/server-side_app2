# Практическая работа №2 — Вариант 18

## 1. Общее описание
Данный проект представляет собой серверную часть веб-приложения на базе фреймворка **Bottle** с поддержкой **HTTP API** и интеграцией с реляционной СУБД **SQLite** для управления вычислительными задачами в рамках курсовой работы по теме: **«Веб-приложение с HTTP API для асинхронного преобразования файлов из формата WAV в формат MP3»**.

Проект разработан в строгом соответствии с академическими правилами оформления кода РТУ МИРЭА:
* Отсутствие служебных комментариев `#` (используются исключительно документирующие строки `"""docstring"""`).
* Ограничение длины строк до 79 символов (PEP8).
* Ограничение объёма функций (не более 40 строк кода) и числа аргументов (не более 7 параметров).
* Отсутствие «магических» числовых литералов в операциях сравнения (все граничные и служебные значения вынесены в модуль именованных констант).
* Полное покрытие всех ветвей исполнения кода (100% Branch Coverage).

Разработка выполнена в три этапа:
1. **Этап 1 (Преобразование данных):** Консольная утилита транскодирования аудиоданных из формата WAV в формат MP3, принимающая входной файл с аудиопараметрами/WAV-потоком и выводящая результаты преобразования и метрики сжатия в стандартный вывод в формате JSON.
2. **Этап 2 (HTTP API):** Полнофункциональное веб-приложение на базе Bottle, реализующее 11 маршрутов управления сущностями (`Member`, `Instruction`, `Response`) и отчётом по формуле (18), авторизацию по стандарту RFC 7617 HTTP Basic Auth, асинхронный запуск вычислительных задач транскодирования через модуль `subprocess` (с поддержкой безопасного флага `--test-mode`), клиентский класс с соглашением именования методов `действие_таблица` и модель-ориентированное тестирование (Model-Based Testing, MBT) на базе библиотеки `hypothesis`.
3. **Этап 3 (Подключение реляционной СУБД SQLite):** Чистый SQL-слой персистентности данных (без ORM) на основе встроенного модуля `sqlite3`, создание таблиц по ER-диаграмме, реализация отчёта по Формуле (18) с использованием оператора `RIGHT OUTER JOIN` и обеспечение 100% покрытия ветвей кода автоматическими тестами `coverage`.

---

## 2. Описание всех функций и настроек

### 2.1. Консольная утилита аудиоконвертации (src/cli.py)
* **Назначение:** Асинхронное преобразование аудиоданных из формата WAV в формат MP3 с вычислением характеристик PCM-потока, фреймов MPEG-1 Layer III, объёмов данных и коэффициента компрессии.
* **Параметры запуска:**
  `python src/cli.py <путь_к_входному_файлу>`
* **Входные данные:** Поддерживает как бинарные файлы с заголовком RIFF/WAVE, так и текстовые конфигурации параметров аудио (ключ: значение или JSON), содержащие:
  * `sample_rate`: Частота дискретизации в Гц (от 8000 до 96000).
  * `channels`: Число каналов (1 — моно, 2 — стерео).
  * `bitrate_kbps`: Целевой битрейт MP3 в кбит/с (от 32 до 320).
  * `duration_sec`: Длительность аудиозаписи в секундах.
* **Выходные данные:** Объект JSON в `stdout`, содержащий:
  * `status`: Статус выполнения (`SUCCESS` или `ERROR`).
  * `source_format`: Исходный формат (`WAV`).
  * `target_format`: Целевой формат (`MP3`).
  * `sample_rate_hz`: Частота дискретизации аудиопотока.
  * `channels`: Число каналов (1 или 2).
  * `channel_mode`: Режим каналов (`MONO` или `STEREO`).
  * `bitrate_kbps`: Битрейт сжатого MP3.
  * `duration_seconds`: Длительность аудиозаписи.
  * `total_samples`: Общее число аудиосэмплов.
  * `wav_size_bytes`: Размер несжатого WAV-файла с RIFF-заголовком.
  * `mp3_frames_count`: Количество сформированных фреймов MP3 (по 1152 сэмпла).
  * `mp3_size_bytes`: Расчётный размер выходного MP3-файла.
  * `compression_ratio`: Итоговый коэффициент сжатия.

### 2.2. Сервер и параметры командной строки (src/server.py)
Веб-приложение запускается через командный интерфейс со следующими аргументами:
* `-u`, `--username`: Имя пользователя для HTTP Basic Auth (по умолчанию: `admin`).
* `-p`, `--password`: Пароль для HTTP Basic Auth (по умолчанию: `secret`).
* `--host`: Хост для привязки сокета (по умолчанию: `127.0.0.1`).
* `--port`: Порт HTTP-сервера (по умолчанию: `8000`).
* `--test-mode`: Флаг включения тестового режима (пропуск реального вызова subprocess).
* `--db-path`: Путь к файлу базы данных SQLite (по умолчанию: `app.db`).

### 2.3. Авторизация RFC 7617 (HTTP Basic Auth)
Все 11 эндпоинтов защищены авторизацией по стандарту RFC 7617.
* Запрос должен содержать заголовок `Authorization: Basic <base64(username:password)>`.
* При отсутствии заголовка, некорректном формате или неверных учётных данных возвращается HTTP статус **401 Unauthorized** с заголовком ответа `WWW-Authenticate: Basic realm="Restricted API"`.
* При успешной аутентификации запрос обрабатывается и возвращается HTTP статус **200 OK** с телом ответа в формате JSON.

### 2.4. Обработчики HTTP API (Таблица 18)
Все обработчики возвращают JSON-ответы. Реализовано 11 маршрутов:

| № | Метод | Маршрут | Параметры запроса | Описание |
|---|---|---|---|---|
| **1.1** | `PUT` | `/public/api/v2/member/store/:id` | Путь (`:id`), JSON-тело (`ip`, `user_agent`) | Создание/сохранение записи участника |
| **1.2** | `GET` | `/public/api/v2/member/show` | Query params (фильтр по полям) | Получение списка участников |
| **1.3** | `GET` | `/public/api/v2/member/find` | Query params (фильтр по полям) | Поиск участников по атрибутам |
| **1.4** | `PATCH` | `/public/api/v2/member/correct/:id` | Путь (`:id`), JSON-тело | Корректировка записи участника |
| **2.1** | `PUT` | `/public/api/v2/instruction/store/:id` | Путь (`:id`), JSON-тело (`argument`, `member`, `description`, `state`) | Сохранение задачи и запуск вычислений через `subprocess` |
| **2.2** | `GET` | `/public/api/v2/instruction/show/:member` | Путь (`:member`), Query params | Получение инструкций конкретного участника |
| **2.3** | `GET` | `/public/api/v2/instruction/find` | Query params | Поиск инструкций по атрибутам |
| **2.4** | `PATCH` | `/public/api/v2/instruction/correct/:id` | Путь (`:id`), JSON-тело | Корректировка полей инструкции |
| **3.1** | `GET` | `/public/api/v2/response/show/:instruction` | Путь (`:instruction`), Query params | Получение ответов для конкретной инструкции |
| **3.2** | `GET` | `/public/api/v2/response/find` | Query params | Поиск записей ответов по атрибутам |
| **4.1** | `GET` | `/public/api/v2/report/show` | Нет | Формирование сводного отчёта по формуле (18) |

### 2.5. Выполнение задач через Subprocess (Метод 2.1)
При вызове `PUT /public/api/v2/instruction/store/:id`:
1. Инструкция сохраняется в таблице `Instruction`.
2. Если веб-приложение запущено без флага `--test-mode`, поле `argument` передается в утилиту `src/cli.py` через стандартный модуль `subprocess.run()`.
3. Результаты работы утилиты (`stdout`, `stderr`, время выполнения `duration`, статус завершения) автоматически сохраняются в связанной таблице `Response`.
4. В режиме `--test-mode` реальный вызов внешнего процесса не осуществляется, а создаётся эмулированная запись ответа, что обеспечивает высокую скорость и детерминированность тестов.

### 2.6. Отчёт по Формуле (18)
Реализует операцию реляционной алгебры:
$$\pi_{I.\text{description}, R.\text{cache\_hit}, R.\text{response}} (\sigma_{I.\text{created} \ge \text{now} - 9\,\text{min}} (I \mathbin{⟖}_{I.\text{id} = R.\text{instruction}} R))$$
* В качестве правого отношения выступает таблица `Response`, в качестве левого — отфильтрованная выборка таблицы `Instruction` за последние 9 минут (`created >= now - 540` секунд).
* Запрос сформирован на чистом диалекте SQLite:
  ```sql
  SELECT Instruction.description, Response.cache_hit, Response.response
  FROM (
      SELECT id, description FROM Instruction WHERE created >= ?
  ) AS Instruction
  RIGHT JOIN Response ON Instruction.id = Response.instruction;
  ```

### 2.7. API-клиент (src/client.py)
Класс `ApiClient` инкапсулирует вызовы всех 11 методов API с именами согласно требованию `действие_таблица`:
* `store_member(uid, data)`
* `show_member(query=None)`
* `find_member(query=None)`
* `correct_member(uid, data)`
* `store_instruction(iid, data)`
* `show_instruction(member_id, query=None)`
* `find_instruction(query=None)`
* `correct_instruction(iid, data)`
* `show_response(instruction_id, query=None)`
* `find_response(query=None)`
* `show_report()`

Клиент поддерживает как работу через сетевой HTTP-транспорт (`urllib.request`), так и прямое тестирование через интерфейс WSGI (`wsgiref`), обеспечивая максимальное быстродействие.

---

## 3. Описание команд для сборки проекта и запуска тестов

### 3.1. Установка зависимостей
Для работы приложения и запуска тестов требуются: `bottle`, `pytest`, `hypothesis`, `coverage`, `flake8`.
```bash
pip install bottle pytest hypothesis coverage flake8
```

### 3.2. Запуск утилиты транскодирования (CLI)
```bash
# Windows
py -m src.cli examples/input1.txt

# Linux / macOS
python3 -m src.cli examples/input1.txt
```

### 3.3. Запуск веб-сервера HTTP API
```bash
# Боевой режим с реальным выполнением задач:
py -m src.server -u admin -p secret --host 127.0.0.1 --port 8000 --db-path app.db

# Тестовый режим (без выполнения subprocess):
py -m src.server --test-mode
```

### 3.4. Автоматический запуск тестов и замер покрытия
Для запуска полного набора тестов на основе модели (MBT) и формирования отчёта о 100% покрытии ветвей кода:

**В среде Linux / macOS (bash):**
```bash
bash run.sh
```

**В среде Windows (cmd / powershell):**
```cmd
run.bat
```

Или прямым вызовом:
```bash
coverage run --branch -m pytest tests/
coverage report -m
```

### 3.5. Проверка соответствия стандартам (PEP8, лимиты, docstrings)
```bash
# Проверка стиля flake8
flake8 --max-line-length=79 src tests
```

---

## 4. Примеры использования

### 4.1. Примеры работы CLI-инструмента
В папке `examples/` подготовлены 3 демонстрационных входных файла:
* `examples/input1.txt` (WAV Mono 44.1 кГц, 128 кбит/с MP3, 10 секунд):
  ```bash
  py -m src.cli examples/input1.txt
  ```
  Вывод:
  ```json
  {"status": "SUCCESS", "source_format": "WAV", "target_format": "MP3", "sample_rate_hz": 44100, "channels": 1, "channel_mode": "MONO", "bitrate_kbps": 128, "duration_seconds": 10.0, "total_samples": 441000, "wav_size_bytes": 882044, "mp3_frames_count": 383, "mp3_size_bytes": 159711, "compression_ratio": 5.52}
  ```
* `examples/input2.txt` (WAV Stereo 48 кГц, 192 кбит/с MP3, 30 секунд):
  ```bash
  py -m src.cli examples/input2.txt
  ```
  Вывод:
  ```json
  {"status": "SUCCESS", "source_format": "WAV", "target_format": "MP3", "sample_rate_hz": 48000, "channels": 2, "channel_mode": "STEREO", "bitrate_kbps": 192, "duration_seconds": 30.0, "total_samples": 2880000, "wav_size_bytes": 5760044, "mp3_frames_count": 1250, "mp3_size_bytes": 720000, "compression_ratio": 8.0}
  ```
* `examples/input3.txt` (WAV Mono 22.05 кГц, 64 кбит/с MP3, 5.5 секунд):
  ```bash
  py -m src.cli examples/input3.txt
  ```
  Вывод:
  ```json
  {"status": "SUCCESS", "source_format": "WAV", "target_format": "MP3", "sample_rate_hz": 22050, "channels": 1, "channel_mode": "MONO", "bitrate_kbps": 64, "duration_seconds": 5.5, "total_samples": 121275, "wav_size_bytes": 242594, "mp3_frames_count": 106, "mp3_size_bytes": 44202, "compression_ratio": 5.49}
  ```

### 4.2. Использование HTTP API через ApiClient
```python
from src.client import ApiClient

# Инициализация клиента с Basic Auth
client = ApiClient(
    base_url="http://127.0.0.1:8000",
    username="admin",
    password="secret",
)

# 1. Создание участника (Member)
member = client.store_member(1, {"ip": "192.168.1.10", "user_agent": "AudioClient"})
print("Member:", member)

# 2. Создание и запуск инструкции транскодирования (Instruction)
instruction = client.store_instruction(
    1,
    {
        "argument": "examples/input1.txt",
        "member": 1,
        "description": "Convert audio track 1",
        "state": "active",
    },
)
print("Instruction:", instruction)

# 3. Просмотр ответа вычислений (Response)
response = client.show_response(1)
print("Response:", response)

# 4. Получение отчёта по Формуле (18)
report = client.show_report()
print("Report:", report)
```

### 4.3. Вывод отчёта coverage со 100% покрытием ветвей
```
Name                  Stmts   Miss Branch BrPart  Cover   Missing
-----------------------------------------------------------------
src\__init__.py           0      0      0      0   100%
src\app.py              145      0      8      0   100%
src\cli.py               93      0     28      0   100%
src\client.py            82      0      4      0   100%
src\constants.py         45      0      0      0   100%
src\storage.py          187      0     18      0   100%
tests\__init__.py         0      0      0      0   100%
tests\test_model.py     274      0      2      0   100%
-----------------------------------------------------------------
TOTAL                   826      0     60      0   100%
```

---

## 5. Рекомендуемая история коммитов (Conventional/Scoped Commits)

В соответствии с правилом С6 («Коммиты не соответствуют спецификации Conventional/Scoped Commits») для оформления этапов в репозитории рекомендуется следующая последовательность коммитов:

1. `chore: initialize repository structure and configuration`
   *(добавление `.gitignore`, `run.sh`, `run.bat`)*
2. `feat(cli): implement wav to mp3 audio conversion computational utility`
   *(добавление `src/constants.py`, `src/cli.py`, `examples/`)*
3. `test(cli): add demonstration examples for audio transcoding stage 1`
   *(проверка и фиксация работы на `examples/input1.txt` ... `input3.txt`)*
4. `feat(api): create bottle application with rfc 7617 basic auth and subprocess runner`
   *(добавление `src/app.py`, `src/server.py`)*
5. `feat(client): implement api client with action_table method naming`
   *(добавление `src/client.py`)*
6. `feat(storage): implement pure sqlite persistence layer and formula 18 query`
   *(добавление `src/storage.py`)*
7. `test(mbt): implement model-based testing with hypothesis rulebasedstatemachine`
   *(добавление `tests/test_model.py` с обеспечением 100% branch coverage)*
8. `docs: add comprehensive readme documentation for all stages`
   *(добавление `README.md`)*
