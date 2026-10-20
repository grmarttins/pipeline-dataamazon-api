FROM apache/airflow:3.3.2-python3.12

# dependências do pipeline (src/) por cima da imagem oficial
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
