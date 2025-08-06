FROM python:3.10

# Install system dependencies
RUN apt-get update && \
    apt-get install -y build-essential python3-dev gcc

# Set workdir and copy files
WORKDIR /app
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Run the app
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]
