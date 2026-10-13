FROM python:3.12-slim

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY . /code

RUN useradd --system --create-home app && chown -R app:app /code

USER app

EXPOSE 8080 

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8080/health', timeout=3)" || exit 1

CMD ["fastapi", "run", "app/main.py", "--port", "8080"]
