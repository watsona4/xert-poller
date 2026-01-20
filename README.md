# Xert Poller

Standalone Xert API poller that sends webhooks to Home Assistant when data changes.

## Features

- Polls Xert API for training info and activities outside of Home Assistant's async loop
- OAuth2 token management with automatic refresh
- Change detection via SHA256 hashing - only sends webhooks when data actually changes
- Token persistence across restarts
- Fetches fitness signature, training load, and activity data

## Setup

### 1. Get Xert Credentials

You need your Xert account username (email) and password.

### 2. Configure Environment Variables

```bash
# Required
XERT_USERNAME=your@email.com
XERT_PASSWORD=your-password
XERT_HA_WEBHOOK_ID=your-webhook-id

# Optional
XERT_HA_URL=http://homeassistant:8123
XERT_TRAINING_INFO_INTERVAL=900  # 15 minutes
XERT_ACTIVITIES_INTERVAL=900     # 15 minutes
XERT_LOOKBACK_DAYS=90            # How many days of activities to fetch
XERT_LOG_LEVEL=INFO
```

### 3. Configure Home Assistant

Copy `homeassistant/xert_webhook.yaml` to your Home Assistant packages directory and add to configuration.yaml:

```yaml
homeassistant:
  packages:
    xert_webhook: !include packages/xert_webhook.yaml
```

Generate a webhook ID and add to secrets.yaml:
```yaml
xert_webhook_id: "your-random-webhook-id-here"
```

### 4. Run with Docker

```bash
docker compose up -d
```

## Events Sent to Home Assistant

- `xert_training_info_update` - Fitness signature, training status, training load
- `xert_activity_list_update` - List of recent activities

## Data Available

### Training Info
- Fitness Signature: FTP, LTP (Lower Threshold Power), Peak Power, HIE (High Intensity Energy)
- Training Status: Fresh, Tired, Very Tired, etc.
- Training Load: Low, High, Peak strain values
- Target XSS (Xert Strain Score) recommendations

### Activities
- Activity list with XSS, duration, focus type
- Activity details including power data
