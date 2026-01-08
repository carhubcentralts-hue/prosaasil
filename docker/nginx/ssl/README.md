# SSL Certificates Directory

This directory should contain the SSL certificates for the ProSaaS application.

## Required Files

Place the following files in this directory:

- `prosaas-origin.crt` - SSL certificate file
- `prosaas-origin.key` - SSL private key file

## Important Notes

1. **Do NOT commit actual certificate files to the repository** - they contain sensitive information
2. The certificate files are already listed in `.gitignore` to prevent accidental commits
3. These files must be present on the server before starting the containers with SSL enabled

## Obtaining Certificates

For production, obtain SSL certificates from:
- Cloudflare Origin Certificate (recommended for sites behind Cloudflare)
- Let's Encrypt
- Your SSL certificate provider

## Testing Locally

For local development without SSL:
- Use `docker-compose.yml` only (default configuration, HTTP only)
- SSL is only required when using `docker-compose.prod.yml`

## Production Deployment

1. Obtain your SSL certificates
2. Copy them to this directory on your production server
3. Ensure file permissions are secure (readable by nginx process only)
4. Deploy using: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`

The nginx container will mount this directory to `/etc/nginx/ssl/` inside the container.
