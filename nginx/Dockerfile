FROM nginx:alpine

# Remove default nginx configuration
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Create placeholder index.html for frontend
RUN echo '<!DOCTYPE html>\
<html lang="en">\
<head>\
    <meta charset="UTF-8">\
    <meta name="viewport" content="width=device-width, initial-scale=1.0">\
    <title>Cycling Analytics</title>\
    <style>\
        body { font-family: system-ui, -apple-system, sans-serif; display: flex; \
               justify-content: center; align-items: center; height: 100vh; \
               margin: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }\
        .container { text-align: center; color: white; }\
        h1 { font-size: 3rem; margin-bottom: 1rem; }\
        p { font-size: 1.2rem; opacity: 0.9; }\
        a { color: white; text-decoration: underline; }\
    </style>\
</head>\
<body>\
    <div class="container">\
        <h1>🚴 Cycling Analytics</h1>\
        <p>API is running. Visit <a href="/docs">/docs</a> for API documentation.</p>\
    </div>\
</body>\
</html>' > /usr/share/nginx/html/index.html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
