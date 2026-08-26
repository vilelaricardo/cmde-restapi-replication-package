# Usar imagem oficial do Java 8
FROM openjdk:8-jdk-slim

# Instalar Python e ferramentas necessárias
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    rm -rf /var/lib/apt/lists/*

# Definir diretório de trabalho
WORKDIR /app

# Copiar primeiro os requirements para aproveitar o cache do Docker
COPY tool/requirements.txt .

# Instalar dependências Python
RUN pip3 install --no-cache-dir -r requirements.txt

# Copiar todo o projeto
COPY . .

# Criar diretório para dados gerados com permissões de escrita
RUN mkdir -p /app/tool/data_generated && \
    chmod -R a+rwx /app/tool/data_generated

# Definir diretório de trabalho para a pasta tool
WORKDIR /app/tool

# Garantir que o script de entrada seja executável
RUN chmod +x main.py

# Definir o entrypoint para executar seu script principal
ENTRYPOINT ["python", "main.py"]