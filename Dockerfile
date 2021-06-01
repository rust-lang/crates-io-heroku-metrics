FROM ubuntu:focal

ARG VECTOR_RELEASE=0.13.1
ARG VECTOR_SHA256=a22054398c06538541764754f0f547e2d841b01067e8ee3515f78c706cf5ca55

# Install system dependencies
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    apache2-utils \
    ca-certificates \
    curl \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install Vector
RUN curl -Lo /tmp/vector.tar.gz https://github.com/timberio/vector/releases/download/v${VECTOR_RELEASE}/vector-${VECTOR_RELEASE}-x86_64-unknown-linux-gnu.tar.gz && \
    echo "${VECTOR_SHA256}  /tmp/vector.tar.gz" | sha256sum -c && \
    tar xf /tmp/vector.tar.gz -C /usr/local/bin --strip-components 3 ./vector-x86_64-unknown-linux-gnu/bin/vector && \
    mkdir /var/lib/vector && \
    rm /tmp/vector.tar.gz

# Copy the startup script
COPY src/start.sh /usr/local/bin/start-container

# Copy configuration files
COPY src/vector.toml /etc/vector/vector.toml
COPY src/nginx.conf /etc/nginx/nginx.conf
COPY src/supervisord.conf /etc/supervisor/supervisord.conf

EXPOSE 80
CMD ["/usr/local/bin/start-container"]
