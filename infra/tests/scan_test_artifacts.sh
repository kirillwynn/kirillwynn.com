#!/bin/sh
set -eu

remove_unsafe=0
if [ "${1:-}" = "--remove-unsafe" ]; then
    remove_unsafe=1
    shift
fi

artifact_root=${1:-}
if [ -z "$artifact_root" ] || [ ! -d "$artifact_root" ]; then
    exit 0
fi

denylist='django sentinel|postgres sentinel|s3-only-integration-secret|google-only-integration-secret|github-only-integration-secret|revalidation sentinel|production-check-only|https?://(django|postgres|db|minio|worker|outbox|next|edge)(:[0-9]+)?|authorization[[:space:]]*:[[:space:]]*bearer|(set-)?cookie[[:space:]]*:|sessionid=|csrftoken=|kw_preview_credential=|e2e_provider=|deterministic-test-csrf|e2e-(preview|confirm|unsubscribe)|(DJANGO_SECRET_KEY|DJANGO_API_URL|REVALIDATION_SECRET|RESEND_API_KEY|RESEND_WEBHOOK_SECRET|SUBSCRIPTION_SIGNING_SECRET|POSTGRES_PASSWORD|S3_MEDIA_SECRET_ACCESS_KEY|OAUTH_CLIENT_SECRET)[[:space:]]*[:=]'

find "$artifact_root" -type f | while IFS= read -r artifact; do
    unsafe=0
    case "$artifact" in
        *.zip)
            if unzip -p "$artifact" 2>/dev/null | grep -aEiq "$denylist"; then
                unsafe=1
            fi
            ;;
        *)
            if grep -aEiq "$denylist" "$artifact"; then
                unsafe=1
            fi
            ;;
    esac

    if [ "$unsafe" -eq 1 ] && [ "$remove_unsafe" -eq 1 ]; then
        echo "Removing unsafe retained artifact before upload: $artifact" >&2
        rm -- "$artifact"
    elif [ "$unsafe" -eq 1 ]; then
        echo "Retained artifact contains a forbidden secret or internal origin: $artifact" >&2
        exit 1
    fi
done
