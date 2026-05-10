FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ src/

EXPOSE 5353/udp
CMD ["python", "-m", "src.server", "--bind", "0.0.0.0", "--port", "5353", "--upstream", "1.1.1.1"]
