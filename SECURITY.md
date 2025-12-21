# Security Configuration Guide

This document outlines the security improvements implemented in the IoT Waste Management Platform and provides guidance for secure deployment.

## 🔒 Security Features Implemented

### 1. Environment-Based Configuration

All sensitive credentials and configuration are now managed through environment variables instead of hardcoded values.

**Files:**
- `.env.example` - Template for configuration
- `.env` - Actual credentials (git-ignored)

**Why it matters:**
- Prevents accidental credential leaks in version control
- Allows different configurations per environment (dev/staging/prod)
- Makes credential rotation easier

**Setup:**
```bash
# Copy template
cp .env.example .env

# Edit with your secure values
nano .env

# Never commit .env to git!
git check-ignore .env  # Should show: .gitignore:41:.env
```

---

### 2. MQTT Authentication & Authorization

**Location:** `mosquitto_secure/`

#### 2.1 Authentication (Username/Password)

MQTT broker now requires authentication. Anonymous access is disabled.

**Configuration:** `mosquitto_secure/config/mosquitto.conf`
```conf
allow_anonymous false
password_file /mosquitto/config/passwd
```

**User Accounts:**
| Username | Role | Permissions |
|----------|------|-------------|
| `mqtt_admin` | Administrator | Full access to all topics |
| `iot_device` | IoT Device | Publish sensor data only |
| `backend_service` | Backend | Subscribe to all sensor data |
| `dashboard_service` | Dashboard | Read data + send commands |

#### 2.2 Access Control List (ACL)

**Configuration:** `mosquitto_secure/config/acl.conf`

Each user has specific topic permissions:

```conf
# IoT devices can only publish to their sensor topics
user iot_device
topic write waste/bins/+/sensors

# Backend can read all waste data
user backend_service
topic read waste/#
```

**Setup MQTT Authentication:**
```bash
# Using Docker (recommended)
cd mosquitto_secure
./setup_mqtt_auth_docker.sh

# Or manually with mosquitto_passwd
mosquitto_passwd -c config/passwd mqtt_admin
mosquitto_passwd config/passwd iot_device
```

---

### 3. Database Security

**Configuration:** Environment variables in `.env`

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=wastedb
POSTGRES_USER=admin
POSTGRES_PASSWORD=CHANGE_THIS_PASSWORD
```

**Security Checklist:**
- ✅ Use strong passwords (min 16 chars, mixed case, numbers, symbols)
- ✅ Change default credentials
- ✅ Restrict database network access (firewall rules)
- ✅ Regular backups
- ⚠️ Consider PostgreSQL SSL/TLS for production
- ⚠️ Implement database user roles (read-only, read-write)

---

### 4. API Security

**File:** `dashboard/api/main.py`

#### 4.1 CORS Policy

**Before:**
```python
allow_origins=["*"]  # ⚠️ Allows any origin
```

**After:**
```python
allow_origins=CORS_ORIGINS  # ✅ Restricted to configured origins
```

**Configuration in `.env`:**
```env
# Only allow specific origins (comma-separated, no spaces)
API_CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
```

For production, add your domain:
```env
API_CORS_ORIGINS=https://dashboard.yourdomain.com,https://www.yourdomain.com
```

#### 4.2 Security Headers

Automatically added to all API responses:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME-type sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `X-XSS-Protection` | `1; mode=block` | Enable XSS filter |
| `Strict-Transport-Security` | `max-age=31536000` | Force HTTPS (production) |

#### 4.3 Documentation Endpoints

API documentation (`/docs`, `/redoc`) is automatically disabled in production:

```python
docs_url="/docs" if ENVIRONMENT == 'development' else None
```

Set in `.env`:
```env
ENVIRONMENT=production  # Disables docs
```

#### 4.4 Request Logging

All API requests are logged with:
- HTTP method
- Request path
- Response status code
- Processing time

**Example:**
```
GET /api/bins - Status: 200 - Time: 0.042s
```

---

### 5. Docker Compose Security

**File:** `docker-compose.yml`

All services now use environment variables:

```yaml
services:
  db:
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-admin}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-rootpassword}
```

**Benefits:**
- No hardcoded credentials in docker-compose.yml
- Easy credential rotation
- Safe to commit docker-compose.yml to git

---

## 🔐 Production Security Checklist

### Before Deployment

- [ ] **Change ALL default passwords**
  - PostgreSQL admin password
  - pgAdmin password
  - MQTT user passwords

- [ ] **Generate secure secrets**
  ```bash
  # Generate random password
  openssl rand -base64 32

  # Generate API secret key
  openssl rand -hex 32
  ```

- [ ] **Update `.env` file**
  - Set `ENVIRONMENT=production`
  - Set `DEBUG=false`
  - Update all passwords
  - Set correct CORS origins

- [ ] **MQTT Security**
  - Regenerate all MQTT passwords
  - Review ACL permissions
  - Consider enabling TLS/SSL

- [ ] **Database Security**
  - Use strong password (16+ chars)
  - Enable SSL/TLS connections
  - Restrict network access
  - Set up regular backups

- [ ] **Network Security**
  - Configure firewall rules
  - Close unused ports
  - Use reverse proxy (nginx/traefik)
  - Enable HTTPS/TLS

- [ ] **API Security**
  - Set restrictive CORS origins
  - Enable rate limiting (future enhancement)
  - Consider adding API key authentication
  - Review and test all endpoints

### Additional Recommendations

#### 1. HTTPS/TLS Setup

Use a reverse proxy like nginx:

```nginx
server {
    listen 443 ssl http2;
    server_name dashboard.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8080;
    }

    location /api {
        proxy_pass http://localhost:8000;
    }
}
```

#### 2. Firewall Rules

```bash
# Allow only necessary ports
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw deny 5432      # Block external DB access
sudo ufw deny 1883      # Block external MQTT access
sudo ufw enable
```

#### 3. Regular Updates

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Update Docker images
docker compose pull
docker compose up -d

# Update Python dependencies
pip install --upgrade -r requirements.txt
```

#### 4. Monitoring & Logging

- Monitor failed login attempts
- Set up log rotation
- Alert on unusual activity
- Regular security audits

---

## 🚨 Security Incident Response

If credentials are compromised:

1. **Immediate Actions:**
   ```bash
   # Stop all services
   docker compose down

   # Rotate all credentials in .env
   nano .env

   # Regenerate MQTT passwords
   cd mosquitto_secure
   ./setup_mqtt_auth_docker.sh

   # Restart with new credentials
   docker compose up -d
   ```

2. **Update all clients:**
   - Update backend service config
   - Update IoT device credentials
   - Update dashboard API config

3. **Audit access:**
   - Check database logs
   - Review MQTT broker logs
   - Check API access logs

---

## 📋 Environment Variables Reference

### Database
```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=wastedb
POSTGRES_USER=admin
POSTGRES_PASSWORD=<strong-password>
```

### MQTT
```env
MQTT_HOST=localhost
MQTT_PORT=1883
MQTT_USERNAME=iot_device
MQTT_PASSWORD=<strong-password>
MQTT_ADMIN_USERNAME=mqtt_admin
MQTT_ADMIN_PASSWORD=<strong-password>
```

### API
```env
API_HOST=0.0.0.0
API_PORT=8000
API_CORS_ORIGINS=http://localhost:8080
ENVIRONMENT=development
DEBUG=true
```

### Application
```env
ALERT_FILL_LEVEL_HIGH=75
ALERT_FILL_LEVEL_CRITICAL=90
ALERT_BATTERY_LOW=20
ALERT_TEMPERATURE_HIGH=45
```

---

## 🔍 Security Testing

### Test MQTT Authentication

```bash
# Should fail (no credentials)
mosquitto_pub -h localhost -t waste/test -m "test"

# Should succeed (with credentials)
mosquitto_pub -h localhost -u iot_device -P <password> -t waste/bins/BIN001/sensors -m '{"test": true}'
```

### Test API CORS

```bash
# Should be rejected (wrong origin)
curl -H "Origin: https://evil.com" http://localhost:8000/api/bins

# Should work (allowed origin)
curl -H "Origin: http://localhost:8080" http://localhost:8000/api/bins
```

### Test Database Access

```bash
# Should work (correct credentials)
PGPASSWORD=<password> psql -h localhost -U admin -d wastedb -c "SELECT 1"

# Should fail (wrong password)
PGPASSWORD=wrong psql -h localhost -U admin -d wastedb -c "SELECT 1"
```

---

## 📚 Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security Best Practices](https://fastapi.tiangolo.com/tutorial/security/)
- [MQTT Security Fundamentals](https://www.hivemq.com/mqtt-security-fundamentals/)
- [PostgreSQL Security Best Practices](https://www.postgresql.org/docs/current/security.html)

---

## 📞 Support

For security-related questions or to report vulnerabilities, please:
1. Do NOT create a public GitHub issue
2. Contact the development team privately
3. Provide detailed information about the vulnerability

---

**Last Updated:** 2025-12-21
**Security Level:** Enhanced (Development → Production Ready)
