#!/bin/bash

# Script to apply database schema to PostgreSQL
# IoT Waste Platform - Database Setup

echo "========================================="
echo "IoT Waste Platform - Database Setup"
echo "========================================="
echo ""

# Configuration
DB_CONTAINER="waste_db"
DB_USER="admin"
DB_NAME="wastedb"
DB_PASSWORD="rootpassword"
SCHEMA_FILE="schema.sql"

# Check if schema file exists
if [ ! -f "$SCHEMA_FILE" ]; then
    echo "❌ Error: $SCHEMA_FILE not found!"
    echo "Please run this script from the database directory."
    exit 1
fi

# Check if container is running
if ! sudo docker ps | grep -q $DB_CONTAINER; then
    echo "❌ Error: Container $DB_CONTAINER is not running!"
    echo "Please start the container first:"
    echo "  sudo docker compose up -d"
    exit 1
fi

echo "✅ Container $DB_CONTAINER is running"
echo ""

# Copy schema file to container
echo "📋 Copying schema file to container..."
sudo docker cp $SCHEMA_FILE $DB_CONTAINER:/tmp/$SCHEMA_FILE

if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to copy schema file"
    exit 1
fi

echo "✅ Schema file copied successfully"
echo ""

# Apply schema
echo "🔧 Applying database schema..."
sudo docker exec -it $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -f /tmp/$SCHEMA_FILE

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Error: Failed to apply schema"
    exit 1
fi

echo ""
echo "========================================="
echo "✅ Database schema applied successfully!"
echo "========================================="
echo ""

# Verify installation
echo "📊 Verifying installation..."
sudo docker exec -it $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;"

echo ""
echo "Sample data:"
sudo docker exec -it $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "SELECT bin_code, location, bin_type, status FROM waste_bins;"

echo ""
echo "========================================="
echo "🎉 Setup complete!"
echo "========================================="
echo ""
echo "Access the database:"
echo "  • pgAdmin: http://localhost:5050"
echo "  • Email: admin@admin.com"
echo "  • Password: rootpassword"
echo ""
echo "Or use psql:"
echo "  PGPASSWORD=rootpassword psql -h localhost -U admin -d wastedb"
echo ""
