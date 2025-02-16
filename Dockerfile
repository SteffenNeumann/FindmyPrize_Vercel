FROM mcr.microsoft.com/playwright:v1.40.0-focal

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

ENV DATABASE_URL=postgresql://user:password@host:port/dbname
ENV SECRET_KEY=your_secret_key

CMD ["python", "main.py"]