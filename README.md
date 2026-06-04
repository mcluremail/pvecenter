# PVE Center

Дашборд для мониторинга кластеров Proxmox VE. Десктопное приложение на PySide6.

## Возможности

- **Дерево объектов** — кластеры, хосты, пулы, ВМ/CT, хранилища с иконками и индикацией статуса
- **Мониторинг** — графики ЦП, RAM, сети, диска (RRD данные из PVE)
- **Оборудование ВМ** — конфигурация, параметры, история задач
- **Хранилища** — сводка по всем storage, детализация по нодам, график заполнения
- **Содержимое storage** — бекапы, диски ВМ, ISO, шаблоны (динамические вкладки)
- **Сеть, сервисы, диски хоста** — физические интерфейсы, сервисы, диски с дедупликацией FC multipath
- **Снапшоты ВМ** — все снапшоты на хосте в одной таблице
- **Статусные индикаторы** — иконки с цветными кружками (зелёный/красный/жёлтый)
- **Soft refresh** — фоновое обновление данных без потери выделения
- **Шифрование токенов** — master-пароль + PBKDF2 + Fernet (AES)

## Требования

- Python 3.12+
- Proxmox VE кластер (или отдельный хост)
- API-токен PVE (read-only, достаточно роли PVEAuditor)

## Установка

```bash
# Клонировать
git clone https://github.com/mcluremail/pvecenter.git
cd pvecenter

# Виртуальное окружение
python -m venv venv
source venv/bin/activate

# Зависимости
pip install PySide6 proxmoxer requests pyqtgraph cryptography
```

## Настройка

Скопируйте `nodes.json.example` в `nodes.json`:

```json
[
  {
    "name": "pve-node-1",
    "host": "pve-node-1.local",
    "cluster": "Production",
    "cluster_rep": true,
    "user": "monitor@pve",
    "token_name": "dashboard",
    "token_value": "ваш-токен"
  },
  {
    "name": "hv01",
    "host": "hv01.local",
    "cluster_rep": false,
    "user": "monitor@pve",
    "token_name": "dashboard",
    "token_value": "ваш-токен"
  }
]
```

Параметры:
- `cluster_rep: true` — узел-представитель кластера (сканирует весь кластер через `cluster.resources`)
- `cluster_rep: false` или не указан — отдельностоящий хост (подключается напрямую)
- `skip: true` — пропустить узел при загрузке (если токен кластера уже обслуживает его)
- `cluster` — имя кластера для группировки в дереве. Если не указан — хост попадает в "Отдельные хосты"

Если токены не вписаны в `nodes.json`, при запуске будет запрошен master-пароль для расшифровки `nodes.enc`.

## Запуск

```bash
./run.py
```

Или:

```bash
python -m pve_center.main
```

## Скриншоты

*(тут будут скриншоты, когда доделаем)*

## Лицензия

MIT