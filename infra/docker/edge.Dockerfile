FROM nginx:1.29-alpine AS runtime

COPY infra/nginx/nginx.conf /etc/nginx/nginx.conf
COPY infra/nginx/conf.d/ /etc/nginx/conf.d/
COPY infra/nginx/snippets/ /etc/nginx/snippets/
RUN rm -f /etc/nginx/conf.d/default.conf \
    && find /etc/nginx -type d -exec chmod 0555 {} + \
    && find /etc/nginx -type f -exec chmod 0444 {} +

EXPOSE 80 443

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["nginx", "-t"]

CMD ["nginx", "-g", "daemon off;"]
