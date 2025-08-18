# Rolling Riches Leads API Plugin

This WordPress plugin exposes your sweeprewards signups data via REST API, allowing you to extract leads programmatically.

## Installation

1. **Upload the Plugin:**
   - Compress the `rolling-riches-leads-api` folder into a ZIP file
   - Go to WordPress Admin ’ Plugins ’ Add New ’ Upload Plugin
   - Choose the ZIP file and click "Install Now"
   - Activate the plugin

   OR

   - Upload the `rolling-riches-leads-api` folder to `/wp-content/plugins/` via FTP
   - Go to WordPress Admin ’ Plugins
   - Find "Rolling Riches Leads API" and click "Activate"

2. **Verify Installation:**
   - The plugin adds new REST API endpoints
   - No configuration needed - it works immediately after activation

## API Endpoints

### Get Leads
```
GET https://www.welcomebonushunter.com/wp-json/rolling-riches/v1/leads
```

**Parameters:**
- `since` (optional): Get leads since this date (format: YYYY-MM-DD)
- `limit` (optional): Maximum number of leads to return (default: 100)
- `offset` (optional): Offset for pagination (default: 0)

**Example:**
```
https://www.welcomebonushunter.com/wp-json/rolling-riches/v1/leads?since=2024-01-01&limit=50
```

### Get Statistics
```
GET https://www.welcomebonushunter.com/wp-json/rolling-riches/v1/leads/stats
```

Returns information about available tables and lead counts.

## Authentication

The API requires authentication using your WordPress Application Password:

```python
import requests
import base64

username = "admin_6797"
password = "H2it UYw9 O9hh QpD5 4LMr QU0e"  # Your app password

credentials = base64.b64encode(f"{username}:{password}".encode()).decode('ascii')
headers = {'Authorization': f'Basic {credentials}'}

response = requests.get(
    "https://www.welcomebonushunter.com/wp-json/rolling-riches/v1/leads",
    headers=headers
)

leads = response.json()
```

## What This Plugin Does

1. **Searches for sweeprewards data** in various possible locations:
   - Custom database tables (wp_sweeprewards_signups, etc.)
   - Custom post types
   - WordPress options table

2. **Exposes data via REST API** with proper authentication

3. **Formats data consistently** regardless of source

4. **Provides statistics** about available data sources

## Security

- Requires authentication (WordPress user must be logged in)
- Only administrators and editors can access the API
- No data is modified - read-only access

## Troubleshooting

If no leads are found:
1. Check the stats endpoint to see which tables were searched
2. The actual table name might be different than expected
3. Contact support with the output from the stats endpoint

## Uninstallation

1. Deactivate the plugin in WordPress Admin ’ Plugins
2. Delete the plugin if desired
3. No database changes are made by this plugin