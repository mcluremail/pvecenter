# PVE Center — Устранение проблем с подключением хостов

## Типовые ошибки и их причины

### 1. DNS / Name Resolution (`gaierror: Unknown name or service`)

**Симптом**: `Failed to resolve 'host.domain'`

**Причины**:
- Хост не прописан в DNS зоне, доступной с машины пользователя
- Временный сбой DNS-сервера
- Неправильно указан FQDN в конфиге

**Решение**:
```bash
# Проверить резолв с ПК
nslookup host.domain
```

При ошибках DNS приложение корректно помечает хост как `error` и **не блокирует загрузку остальных** — дерево обновляется по мере ответов.

---

### 2. 596 TLS / Certificate Error (`tls_process_server_certificate: certificate verify failed`)

**Симптом**: `596 Server Error: tls_process_server_certificate: certificate verify failed`

**Причина**: PVE proxy при проксировании запроса к `/nodes/{fqdn}/...` не находит SSL-сертификат для полного FQDN ноды. Нода называется коротко (например `host01`), а запрос идёт на `host01.domain.grp` → pveproxy ищет `/etc/pve/nodes/host01.domain.grp/pve-ssl.pem` и не находит.

**Диагностика на сервере**:
```bash
sudo journalctl -u pveproxy -f
ls -la /etc/pve/nodes/host01.domain.grp/pve-ssl.pem
```

**Решение на сервере**:
```bash
sudo cp /etc/pve/local/pve-ssl.pem /etc/pve/nodes/host01.domain.grp/pve-ssl.pem
sudo cp /etc/pve/local/pve-ssl.key /etc/pve/nodes/host01.domain.grp/pve-ssl.key
sudo systemctl restart pveproxy
```

---

### 3. 500 Proxy Loop (`proxy loop detected`)

**Симптом**: `500 Server Error: proxy loop detected for url: https://host:8006/api2/json/nodes/{fqdn}/services`

**Причина**: PVE нода не узнаёт себя по FQDN. Когда в URL пути `/nodes/{fqdn}/...` имя не совпадает с коротким именем ноды, pveproxy пытается проксировать запрос на другую ноду кластера, но это та же нода → бесконечный цикл.

**Как решено в коде**:
- `FetchWorker` для standalone хостов получает реальное короткое имя ноды через `proxmox.nodes.get()` перед API-вызовами
- Все последующие запросы идут с коротким именем: `/nodes/host01/...`
- В дереве отображается `_display_name` (FQDN из конфига) — пользователь видит полное имя

---

### 4. 403 Permission errors (`Permission check failed`)

**Симптом**: `403 Client Error: Permission check failed (/nodes/{node}, Sys.Audit)`

**Причины**:
- Токен создан с `privsep=1` (по умолчанию) — изоляция привилегий включена
- Пользователь не имеет прав на запрашиваемый эндпоинт

**Решение**:
```bash
# Проверить отключение изоляции привилегий
pveum user token list pvecenter@pve

# Если privsep=1 — пересоздать
pveum user token remove pvecenter@pve pvecenter-main
pveum user token add pvecenter@pve pvecenter-main --privsep 0 --comment "PVE Center dashboard"
```

**Или пересоздать через диалог "+" в приложении** — он создаёт токен с `privsep=0`.

---

### 5. 401 / Ticket Auth failures

**Симптом**: `401 {"data":null}` при попытке получить тикет

**Причины**:
- Неверный пароль
- Неверный realm (например `user@pve` вместо `user@ipa`)
- Пользователь заблокирован

**Диагностика**:
```bash
curl -k -X POST https://host:8006/api2/json/access/ticket \
  -d 'username=user@realm&password=secret'
```

---

### 6. Connection refused / Timeout

**Симптом**: `Remote end closed connection without response` | `Connection aborted`

**Причины**:
- PVE служба не запущена на сервере
- Порт 8006 закрыт файрволлом
- Хост выключен

**Решение на сервере**:
```bash
sudo systemctl restart pveproxy
```

В приложении таймаут 15 секунд. Недоступные хосты не блокируют загрузку — дерево обновляется по мере ответов.

---

### 7. PUT vs POST — особенности PVE API

При добавлении хоста через диалог приложение использует прямые HTTP-запросы с ticket-аутентификацией:

| Операция | HTTP метод | Endpoint |
|----------|-----------|----------|
| Создание пользователя | **POST** | `/access/users` |
| Назначение ACL | **PUT** | `/access/acl` |
| Создание токена | **PUT** | `/access/users/{user}/token/{id}` |

Ошибка метода приводит к `501` или `500` с пустым `{"data":null}`.

---

## Архитектурные заметки

### Standalone vs Кластер

PVE технически не различает standalone и кластер. Но pveproxy на standalone ноде не умеет проксировать запросы по FQDN, если нода локальная (proxy loop). Поэтому:

- **Standalone**: получаем короткое имя через `proxmox.nodes.get()`, используем его в API
- **Кластер**: `/cluster/resources` возвращает все ноды с короткими именами, API-запросы к конкретным нодам работают через прокси кластера

### _display_name

В `nodes` словарь добавлено поле `_display_name`, которое не участвует в API-запросах — только для отображения в дереве и тостах. Это позволяет:
- Обращаться к API по короткому имени (предотвращает proxy loop)
- Показывать пользователю FQDN (для различия одинаковых коротких имён)

### Токены

- При добавлении через диалог создаётся пользователь `pvecenter@pve` с ролью **Administrator** на `/`
- Токен создаётся с `privsep=0` (полные права пользователя)
- Root-пароль **не хранится** — только токен