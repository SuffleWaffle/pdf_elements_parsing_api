# --- Base Debian 12 Bookworm (Ubuntu-family) Python 3.11.4 image
FROM python:3.11.4-bookworm

# --- Install basic required Linux packages
RUN apt-get clean && apt-get update && apt-get upgrade -y && \
    apt-get install -y software-properties-common build-essential

# --- Install Linux packages required for Python, OpenCV, and PyTesseract
RUN apt-get clean && apt-get update && apt-get upgrade -y && \
    apt-get install -y python3-dev python3-pip && \
    apt-get install -y libgl1-mesa-glx && \
    apt-get install -y tesseract-ocr &&\
    apt-get install -y tesseract-ocr-eng

# --- Install Linux packages needed for SciPy Python Library
RUN apt-get clean && apt-get update && apt-get install -y && \
    apt-get install -y gfortran &&  \
    apt-get install -y libatlas-base-dev && \
    apt-get install -y libopenblas-dev && \
    apt-get update --fix-missing
RUN apt-get update && apt-get install -y  \
    libpq-dev \
    gcc \
    libblas-dev \
    liblapack-dev \
    libsm6 \
    libxext6 \
    libxrender-dev
# --- SET THE WORKING DIRECTORY ---
WORKDIR /app

# --- Install Python dependencies and packages ---
COPY requirements.txt /app
RUN pip install --upgrade pip && \
    pip install --upgrade setuptools
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# --- Clean up the system from unused packages
RUN apt-get autoremove --purge -y build-essential gfortran libatlas-base-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# - Copy the APP code to the APP source directory
COPY . /app
