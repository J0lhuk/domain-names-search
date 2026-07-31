# Domain Availability Checker

CLI для проверки списка имён в нескольких доменных зонах. Он не подменяет отсутствие ответа записью «свободен»: отдельно хранит состояние реестра, ответ регистратора и исторические следы.

## Режим `names.txt` → `result.txt`

Если запускать команду из корня проекта без параметра `--input`, она построчно читает `names.txt`. Пустые строки пропускаются. В корне проекта создаётся или полностью перезаписывается `result.txt`: туда попадают только домены со статусом `availability_status=available`, по одному домену на строку. Премиальные, занятые, зарезервированные и неопределённые варианты в этот файл не попадают.

```powershell
python -m domain_checker.cli check
```

Зоны по умолчанию: `ru,com`. Их можно изменить: `python -m domain_checker.cli check --zones ru,com,net,io`.

## Что именно означает результат

| Поле | Значение |
| --- | --- |
| `registry_status=not_found` | Авторитетный RDAP/WHOIS не нашёл текущую запись. Это ещё не гарантия регистрации. |
| `availability_status=available` | Настроенный API регистратора подтвердил возможность покупки. |
| `premium_available` | Регистрация возможна, но по премиальной цене. |
| `history_status=confirmed_registration_history` | Исторический WHOIS-провайдер подтвердил прежнюю регистрацию. |
| `web_or_dns_history_only` | Найден архив, сертификат или passive DNS; это не дата первой регистрации. |

Для gTLD адрес RDAP выбирается из [IANA RDAP Bootstrap](https://data.iana.org/rdap/dns.json), а для `.ru`/`.рф` при отсутствии RDAP предусмотрен официальный WHOIS TCI. RDAP `404` не считается подтверждением покупки. DNS вообще не используется в качестве критерия доступности.

## Быстрый старт

Требуется Python 3.12+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item config.example.yaml config.yaml
python -m domain_checker.cli check --input examples\names.txt --zones ru,com --output results --config config.yaml --offline-fixtures examples\offline-fixtures.json
```

Офлайн-режим воспроизводим: он не выполняет запросов к регистраторам, RDAP или историческим источникам. После команды появятся:

- `results/results.sqlite3` — checkpoint и результаты для `resume`;
- `results/results.jsonl` — потоковый журнал завершённых проверок;
- `results/results.csv` — UTF-8 BOM, пригодный для Excel;
- `results/results.json` — полный структурированный экспорт.

Проверить только вход без записи файлов:

```powershell
python -m domain_checker.cli check --input examples\names.txt --zones ru,com --dry-run
```

Продолжить прерванный запуск и не проверять уже сохранённые домены:

```powershell
python -m domain_checker.cli resume --input examples\names.txt --zones ru,com --output results --config config.yaml
```

## Реальные запросы

Без настроенного registrar API итоговая возможность покупки будет `unknown`; это корректное безопасное поведение. Укажите endpoint и имена переменных окружения в `config.yaml`, а сами значения поместите в пользовательские environment variables:

```powershell
$env:DOMAIN_CHECKER_REGISTRAR_URL = 'https://registrar.example/api/domain-check'
$env:DOMAIN_CHECKER_REGISTRAR_TOKEN = '...'
```

Поддерживаемый контракт адаптера: POST `{"domain":"example.com"}`, ответ `{"status":"available|premium|registered|reserved|unsupported_tld","price":12.0,"currency":"USD"}`. Перед подключением конкретного регистратора нужно сверить этот маппинг с его актуальной официальной документацией. Скрипт не создаёт регистрацию и не выполняет платные действия.

История подключается независимо. Wayback включён по умолчанию, Certificate Transparency отключён, historical WHOIS работает только при легальном API-источнике и его ключе. Самая ранняя web/CT/DNS дата — лишь наблюдение, а не «первая регистрация».

## Команды

```text
domain-checker check                         # names.txt -> result.txt
domain-checker check --input NAMES --zones ru,com
domain-checker resume --input NAMES --zones ru,com
domain-checker export --output results
domain-checker providers --config config.yaml
domain-checker validate-config --config config.yaml
```

Полные домены во входном файле (например, `chat.com`) также допустимы и не комбинируются с `--zones`. CSV-вход обязан содержать колонку `name`.

## Проверки

```powershell
python -m pytest
python -m ruff check .
python -m mypy domain_checker
```

Тесты работают на локальных фикстурах и mock-транспорте, не расходуют квоты внешних сервисов.
