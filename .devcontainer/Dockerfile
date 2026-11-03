FROM mcr.microsoft.com/devcontainers/base:trixie AS ca-certs
USER root
COPY *pem /run/ca-certs/sources/

# Split bundle(s) to individual crt (PEM) files
RUN mkdir -p /run/ca-certs/extracts
WORKDIR /run/ca-certs/extracts
RUN openssl storeutl /run/ca-certs/sources/*pem | \
    awk '/BEGIN CERTIFICATE/ { c++; } /BEGIN CERTIFICATE/,/END CERTIFICATE/ {print > c ".crt"}'

FROM mcr.microsoft.com/devcontainers/python:3.15-trixie
USER root
COPY --from=ca-certs /run/ca-certs/extracts/*.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates -v
