cat > user-data.sh << 'EOF'
#!/bin/bash
apt-get update
apt-get install -y python3-pip python3-venv nginx git

# Create a directory for the application
mkdir -p /var/www/destiny
cd /var/www/destiny

# Clone your repository (replace with your actual repository URL)
git clone https://github.com/yourusername/destiny-backend.git .

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install gunicorn

# Set up environment variables
cat > .env << 'ENVEOF'
DEBUG=False
ALLOWED_HOSTS=dev.destinybuilders.africa,localhost,127.0.0.1
DATABASE_URL=sqlite:////var/www/destiny/db.sqlite3
# Add other environment variables as needed
ENVEOF

# Run migrations
python manage.py migrate
python manage.py collectstatic --noinput

# Set up Gunicorn service
cat > /etc/systemd/system/gunicorn.service << 'SERVICEEOF'
[Unit]
Description=gunicorn daemon
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/var/www/destiny
ExecStart=/var/www/destiny/venv/bin/gunicorn --access-logfile - --workers 3 --bind unix:/var/www/destiny/destiny.sock your_project.wsgi:application

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Set up Nginx
cat > /etc/nginx/sites-available/destiny << 'NGINXEOF'
server {
    listen 80;
    server_name dev.destinybuilders.africa;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        root /var/www/destiny;
    }

    location /media/ {
        root /var/www/destiny;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/destiny/destiny.sock;
    }
}
NGINXEOF

# Enable the site
ln -s /etc/nginx/sites-available/destiny /etc/nginx/sites-enabled

# Start services
systemctl start gunicorn
systemctl enable gunicorn
systemctl restart nginx

# Set proper permissions
chown -R ubuntu:www-data /var/www/destiny
chmod -R 775 /var/www/destiny
EOF