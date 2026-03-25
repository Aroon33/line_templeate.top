# line-platform deploy notes

## Created
- Nginx vhost: /etc/nginx/sites-available/line-platform
- Enabled: /etc/nginx/sites-enabled/line-platform
- SSL cert: /etc/letsencrypt/live/line.sns-template.com/
- Env template: /var/www/line-platform/.env.example
- Service templates:
  - /var/www/line-platform/ops/line-platform-api.service.example
  - /var/www/line-platform/ops/line-platform-ui.service.example

## Ports reserved
- UI: 127.0.0.1:3101
- API: 127.0.0.1:8101

## Health check
- https://line.sns-template.com
- https://api.sns-template.com

If API/UI are not running yet, nginx returns 502 for that endpoint.
