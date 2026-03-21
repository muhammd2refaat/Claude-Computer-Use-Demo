# Logging System Guide

## 📍 Where Logger Data is Stored

### Log File Locations

**Production (Docker):**
```
/data/logs/
├── app.log         # General application logs
├── api.log         # HTTP requests/responses
├── database.log    # Database queries and pool metrics
└── tools.log       # Tool execution logs
```

**Development (Local):**
```
computer-use-demo/logs/
├── app.log
├── api.log
├── database.log
└── tools.log
```

The location is controlled by the `LOG_DIR` environment variable (default: `/data/logs`).

### Log Format

Logs are stored in **JSON format** (one JSON object per line) for easy parsing and analysis:

```json
{
  "timestamp": "2026-03-21T20:57:10.767542+00:00",
  "logger": "computer_use_demo.api.middleware",
  "level": "INFO",
  "correlation_id": "a7b3c9d1-4e5f-6789-0abc-def123456789",
  "session_id": "abc123",
  "message": "HTTP Request",
  "method": "POST",
  "url": "/api/sessions",
  "duration_ms": 1234.56
}
```

---

## 🔍 How to Explore Logs

### Method 1: Interactive Log Explorer (Recommended)

We've created a script to make exploration easy:

```bash
cd computer-use-demo

# Set log directory (if not using default)
export LOG_DIR="./logs"

# Run the explorer
./explore_logs.sh
```

**Menu Options:**
1. Show all log files
2. Tail app.log (real-time)
3. Search by correlation ID
4. Show all errors
5. Show API requests
6. Show tool executions
7. Show database queries
8. Show recent logs (last 20)
9. Show logs with timing > 1000ms
10. Count logs by level

### Method 2: Manual Commands

#### View Logs (Human-Readable)

```bash
# View all logs
cat logs/app.log | python3 -m json.tool

# View last 20 entries
tail -20 logs/app.log | while read line; do echo "$line" | python3 -m json.tool; done

# View in real-time
tail -f logs/app.log | while read line; do echo "$line" | python3 -m json.tool; done
```

#### Search Logs

```bash
# Search by correlation ID
grep "a7b3c9d1" logs/*.log

# Search by session ID
grep "abc123" logs/*.log

# Search by message
grep "Tool execution" logs/tools.log

# Search for errors
grep '"level":"ERROR"' logs/*.log
```

#### Filter with jq (Better JSON Parsing)

Install jq first:
```bash
# macOS
brew install jq

# Ubuntu/Debian
sudo apt-get install jq
```

Then use it:
```bash
# Show only ERROR level logs
cat logs/app.log | jq 'select(.level == "ERROR")'

# Show logs with specific correlation ID
cat logs/*.log | jq 'select(.correlation_id == "a7b3c9d1-4e5f-6789-0abc-def123456789")'

# Show API requests > 1000ms
cat logs/api.log | jq 'select(.duration_ms > 1000)'

# Show tool executions with errors
cat logs/tools.log | jq 'select(.has_error == true)'

# Extract specific fields
cat logs/app.log | jq '{time: .timestamp, level: .level, message: .message}'
```

---

## 📊 Common Analysis Tasks

### 1. Track a Request End-to-End

```bash
# Get correlation ID from response header
CORR_ID=$(curl -sI http://localhost:8000/api/sessions | grep -i x-correlation-id | cut -d' ' -f2 | tr -d '\r')

# Trace through all layers
echo "=== API Layer ==="
cat logs/api.log | jq --arg id "$CORR_ID" 'select(.correlation_id == $id)'

echo "=== Tool Execution ==="
cat logs/tools.log | jq --arg id "$CORR_ID" 'select(.correlation_id == $id)'

echo "=== Database ==="
cat logs/database.log | jq --arg id "$CORR_ID" 'select(.correlation_id == $id)'
```

### 2. Performance Analysis

```bash
# Average API response time
cat logs/api.log | jq -r 'select(.duration_ms) | .duration_ms' | \
  awk '{sum+=$1; count++} END {print "Average:", sum/count, "ms"}'

# Slowest operations
cat logs/*.log | jq -r 'select(.duration_ms) | "\(.duration_ms)ms - \(.message)"' | \
  sort -rn | head -10

# Tool execution stats
cat logs/tools.log | jq -r 'select(.tool_name) | "\(.tool_name): \(.duration_ms)ms"' | \
  sort | uniq -c
```

### 3. Error Analysis

```bash
# All errors
cat logs/*.log | jq 'select(.level == "ERROR")'

# Errors with context
cat logs/*.log | jq 'select(.level == "ERROR") | {
  time: .timestamp,
  logger: .logger,
  message: .message,
  error: .error,
  correlation_id: .correlation_id
}'

# Error count by type
cat logs/*.log | jq -r 'select(.level == "ERROR") | .message' | sort | uniq -c
```

### 4. Monitor Active Sessions

```bash
# Count unique sessions
cat logs/app.log | jq -r 'select(.session_id) | .session_id' | sort -u | wc -l

# Session activity timeline
cat logs/app.log | jq 'select(.session_id) | {
  time: .timestamp,
  session: .session_id,
  message: .message
}'
```

### 5. Database Performance

```bash
# Slow queries (> 100ms)
cat logs/database.log | jq 'select(.duration_ms > 100) | {
  query: .query,
  duration: .duration_ms
}'

# Connection pool stats
cat logs/database.log | jq 'select(.pool_size) | {
  time: .timestamp,
  pool_size: .pool_size,
  available: .available,
  in_use: .in_use
}'
```

---

## 🎯 Quick Reference Commands

### Real-Time Monitoring

```bash
# Watch all logs live
tail -f logs/app.log | jq -C '.'

# Watch errors only
tail -f logs/*.log | grep '"level":"ERROR"' | jq -C '.'

# Watch specific session
tail -f logs/app.log | jq --arg sid "abc123" 'select(.session_id == $sid)' -C
```

### Log Statistics

```bash
# Total log entries
wc -l logs/*.log

# Logs by level
echo "INFO:    $(grep -c '"level":"INFO"' logs/*.log)"
echo "WARNING: $(grep -c '"level":"WARNING"' logs/*.log)"
echo "ERROR:   $(grep -c '"level":"ERROR"' logs/*.log)"

# Logs by component
echo "API:      $(wc -l < logs/api.log)"
echo "Database: $(wc -l < logs/database.log)"
echo "Tools:    $(wc -l < logs/tools.log)"
```

### Log File Management

```bash
# Check log file sizes
du -h logs/*.log

# Find old logs (backups)
ls -lh logs/*.log.*

# Clean up old logs (manually)
rm logs/*.log.1 logs/*.log.2

# Archive logs
tar -czf logs-backup-$(date +%Y%m%d).tar.gz logs/
```

---

## 🚀 Integration with Log Aggregation Tools

### Elasticsearch + Kibana

```bash
# Use Filebeat to ship logs to Elasticsearch
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /data/logs/*.log
  json.keys_under_root: true
  json.add_error_key: true
```

### Grafana Loki

```bash
# Use Promtail to ship logs to Loki
- job_name: computer-use-demo
  static_configs:
  - targets:
      - localhost
    labels:
      job: computer-use-demo
      __path__: /data/logs/*.log
```

### Datadog

```bash
# Configure Datadog agent
logs:
  - type: file
    path: /data/logs/*.log
    service: computer-use-demo
    source: python
    sourcecategory: sourcecode
```

---

## 🔧 Configuration

Control logging behavior with environment variables:

```bash
# Log level
LOG_LEVEL=INFO              # DEBUG, INFO, WARNING, ERROR

# Log format
LOG_FORMAT=dual             # console, json, or dual

# Log directory
LOG_DIR=/data/logs

# Rotation settings
LOG_MAX_SIZE_MB=10          # Rotate at 10MB
LOG_BACKUP_COUNT=5          # Keep 5 backups

# Feature flags
ENABLE_PERFORMANCE_LOGGING=true
ENABLE_DATABASE_QUERY_LOGGING=true
ENABLE_API_REQUEST_LOGGING=true
ENABLE_TOOL_EXECUTION_LOGGING=true
```

---

## 📝 Testing

Run the test suite to verify logging:

```bash
cd computer-use-demo
export LOG_DIR="./logs"
python3 test_logger.py
```

This will create sample logs in all categories and verify the system works correctly.

---

## 🆘 Troubleshooting

### Logs not being created?

1. Check directory permissions:
   ```bash
   ls -ld /data/logs
   ```

2. Check LOG_DIR setting:
   ```bash
   echo $LOG_DIR
   ```

3. Verify logger is configured:
   ```bash
   python3 -c "from computer_use_demo.config.settings import settings; print(settings.LOG_DIR)"
   ```

### Logs too verbose?

Change log level to reduce output:
```bash
export LOG_LEVEL=WARNING  # or ERROR
```

Or disable specific features:
```bash
export ENABLE_DATABASE_QUERY_LOGGING=false
export ENABLE_TOOL_EXECUTION_LOGGING=false
```

### Can't parse JSON?

Make sure you're using the right tools:
```bash
# Wrong (tries to parse multiple JSON objects as one)
cat logs/app.log | python3 -m json.tool

# Correct (parse each line separately)
cat logs/app.log | while read line; do echo "$line" | python3 -m json.tool; done

# Better (use jq)
cat logs/app.log | jq '.'
```

---

## 📚 Examples

See `test_logger.py` for examples of:
- Basic logging
- Context logging (correlation IDs)
- Component-specific logging
- Decorator-based logging
- Exception logging
- Performance logging
