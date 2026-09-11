FROM roundcube/roundcubemail:1.7.4-apache@sha256:8a4f88846145c6c8801654d9c3b330071e162f0110b64d08af8e94aca50ffb89
COPY .cache/mcpcube /usr/src/roundcubemail/plugins/mcpcube
RUN cd /usr/src/roundcubemail/plugins/mcpcube && COMPOSER_ALLOW_SUPERUSER=1 composer install --no-dev --no-interaction --no-plugins --no-scripts --prefer-dist
COPY tests/roundcube_dependencies.php /tmp/roundcube_dependencies.php
RUN php /tmp/roundcube_dependencies.php host-first && php /tmp/roundcube_dependencies.php plugin-first && rm /tmp/roundcube_dependencies.php
COPY integrations/mcpcube/apache-routes.conf /tmp/mcp-routes
RUN sed -i "/RewriteEngine On/r /tmp/mcp-routes" /usr/src/roundcubemail/public_html/.htaccess
# Runtime configuration must supply mcpcube_public_url, encryption key and plugin enablement.
# No deployment credentials or mailbox data are baked into this image.
