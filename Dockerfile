FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY pave/ pave/
COPY ranker_v4_best_epoch1.pt .
COPY wdc_pave_test_products.json .

# Expose port
EXPOSE 8000

# Run API
CMD ["python", "-m", "uvicorn", "pave.api:app", "--host", "0.0.0.0", "--port", "8000"]
