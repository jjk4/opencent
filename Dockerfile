# Stage 1: Base build stage
FROM python:3.13-slim AS builder
 
# Create the app directory
RUN mkdir /app
 
# Set the working directory
WORKDIR /app
 
# Set environment variables to optimize Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1 
 
# Upgrade pip and install dependencies
RUN pip install --upgrade pip 
 
# Copy the requirements file first (better caching)
COPY requirements.txt /app/
 
# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Downloader stage for static assets
FROM alpine:latest AS downloader
WORKDIR /downloads

# Install wget and unzip for downloading and extracting assets
RUN apk add --no-cache wget unzip

# HTMX
RUN mkdir -p htmx && \
    wget -O htmx/htmx.min.js https://unpkg.com/htmx.org@2.0.7/dist/htmx.min.js

# ApexCharts
RUN mkdir -p apexcharts && \
    wget -O apexcharts/apexcharts.min.js https://cdn.jsdelivr.net/npm/apexcharts@5.10.4/dist/apexcharts.min.js

# Bootstrap Icons
RUN wget -O bs-icons.zip https://github.com/twbs/icons/releases/download/v1.13.1/bootstrap-icons-1.13.1.zip && \
    unzip bs-icons.zip && \
    mv bootstrap-icons-1.13.1 bootstrap-icons

# Bootstrap 5 (CSS & JS Bundle)
RUN mkdir -p bootstrap/css bootstrap/js && \
    wget -O bootstrap/css/bootstrap.min.css https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css && \
    wget -O bootstrap/css/bootstrap.min.css.map https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css.map && \
    wget -O bootstrap/js/bootstrap.bundle.min.js https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js && \
    wget -O bootstrap/js/bootstrap.bundle.min.js.map https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js.map

# SVG.js
RUN mkdir -p svgjs && \
    wget -O svgjs/svg.min.js https://cdn.jsdelivr.net/npm/@svgdotjs/svg.js@3.2.5/dist/svg.min.js

# ApexSankey
RUN mkdir -p apexsankey && \
    wget -O apexsankey/apexsankey.min.js https://cdn.jsdelivr.net/npm/apexsankey@1.3.0

# Jquery
RUN mkdir -p jquery && \
    wget -O jquery/jquery.min.js https://code.jquery.com/jquery-3.7.1.min.js

# Select2
RUN mkdir -p select2 && \
    wget -O select2/select2.min.js https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js && \
    wget -O select2/select2.min.css https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css && \
    wget -O select2/select2-bootstrap-5-theme.min.css https://cdn.jsdelivr.net/npm/select2-bootstrap-5-theme@1.3.0/dist/select2-bootstrap-5-theme.min.css


# Stage 3: Production stage
FROM python:3.13-slim

# Install the runtime library for Postgres
RUN apt-get update && \
    apt-get install -y libpq5 netcat-openbsd gettext && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -m -r appuser && \
   mkdir /app && \
   chown -R appuser /app
 
# Copy the Python dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/
 
# Set the working directory
WORKDIR /app
 
# Copy application code
COPY --chown=appuser:appuser . .

# copy downloaded static assets from downloader stage
COPY --from=downloader --chown=appuser:appuser /downloads/ /app/productionfiles/vendor/

RUN SECRET_KEY="dummy-key-for-build" python manage.py compilemessages

COPY --chown=appuser:appuser docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Set permissions for /app/media directory
RUN mkdir -p /app/media && chown -R appuser:appuser /app/media

# Set environment variables to optimize Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1 
 
# Switch to non-root user
USER appuser
 
# Expose the application port
EXPOSE 8000 

ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Start the application using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "opencent.wsgi:application"]
