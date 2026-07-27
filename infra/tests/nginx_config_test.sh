#!/bin/sh
set -eu

image=${1:?edge image is required}
test_root=$(mktemp -d)
trap 'rm -rf "$test_root"' EXIT HUP INT TERM

mkdir -p \
    "$test_root/letsencrypt/live/kirillwynn.com" \
    "$test_root/letsencrypt/live/staging.kirillwynn.com" \
    "$test_root/certbot" \
    "$test_root/auth"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=kirillwynn.com \
    -keyout "$test_root/key.pem" -out "$test_root/cert.pem" >/dev/null 2>&1
for site in kirillwynn.com staging.kirillwynn.com; do
    cp "$test_root/key.pem" "$test_root/letsencrypt/live/$site/privkey.pem"
    cp "$test_root/cert.pem" "$test_root/letsencrypt/live/$site/fullchain.pem"
done
printf 'staging:%s\n' 'ci-placeholder-not-a-secret' > "$test_root/auth/staging.htpasswd"

docker run --rm \
    --add-host production-django:127.0.0.1 \
    --add-host production-next:127.0.0.1 \
    --add-host staging-django:127.0.0.1 \
    --add-host staging-next:127.0.0.1 \
    -v "$test_root/letsencrypt:/etc/letsencrypt:ro" \
    -v "$test_root/certbot:/var/www/certbot:ro" \
    -v "$test_root/auth/staging.htpasswd:/etc/nginx/auth/staging.htpasswd:ro" \
    "$image" nginx -t
