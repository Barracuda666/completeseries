FROM php:8.2-fpm-alpine

# Install Nginx
RUN apk add --no-cache nginx

# Configure Nginx Logging
# Redirect access logs to stdout and error logs to stderr
RUN ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log

# Configure Nginx
RUN rm /etc/nginx/http.d/default.conf
COPY nginx.conf /etc/nginx/http.d/default.conf

# Setup Work Dir
WORKDIR /var/www/html

# Copy application files
COPY . /var/www/html/

# Fix permissions
RUN chown -R www-data:www-data /var/www/html/ \
    && chmod -R 755 /var/www/html/

# Expose port 80
EXPOSE 80

# Start Nginx and PHP-FPM
CMD ["/bin/sh", "-c", "php-fpm -D && nginx -g 'daemon off;'"]