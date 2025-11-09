FROM selenium/standalone-chrome:latest

USER root

# Встановлюємо Python
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копіюємо файли
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

# Відкриваємо порт
EXPOSE 5000

# Запускаємо додаток
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "120", "app:app"]
```

---

## 🎯 Або ще простіше - без Docker:

Видаліть `Dockerfile` і `railway.json`, і створіть просто:

### `Procfile`:
```
web: gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120
```

### Оновлений `requirements.txt`:
```
flask==3.0.0
flask-cors==4.0.0
selenium==4.15.2
pillow==10.1.0
requests==2.31.0
gunicorn==21.2.0
webdriver-manager==4.0.1
