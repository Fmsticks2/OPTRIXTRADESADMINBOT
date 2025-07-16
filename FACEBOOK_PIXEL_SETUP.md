# 🎯 Facebook Pixel Setup Guide for OPTRIXTRADES Bot

This guide will help you set up Facebook Pixel tracking for your OPTRIXTRADES bot landing page.

## 📋 Prerequisites

1. **Facebook Business Account**: You need a Facebook Business account
2. **Facebook Pixel**: Create a Facebook Pixel in your Facebook Business Manager
3. **Domain Verification**: Verify your domain `bot.optrixtrades.com` in Facebook Business Manager

## 🚀 Quick Setup

### Step 1: Get Your Facebook Pixel ID

1. Go to [Facebook Business Manager](https://business.facebook.com/)
2. Navigate to **Events Manager**
3. Select your Pixel or create a new one
4. Copy your **Pixel ID** (it looks like: `123456789012345`)

### Step 2: Configure Environment Variables

Set the following environment variables in your Railway deployment:

```bash
# Required: Your Facebook Pixel ID
FACEBOOK_PIXEL_ID=YOUR_ACTUAL_PIXEL_ID

# Optional: Enable/disable tracking (default: true)
FACEBOOK_PIXEL_ENABLED=true

# Optional: Configure tracking events (default: true)
TRACK_PAGE_VIEW=true
TRACK_LEAD_CONVERSION=true
TRACK_ENGAGEMENT=true

# Optional: Configure timing (in seconds)
AUTO_REDIRECT_DELAY=10
ENGAGEMENT_TRACKING_DELAY=5
```

### Step 3: Deploy and Test

1. **Deploy your changes** to Railway
2. **Visit your landing page**: `https://bot.optrixtrades.com`
3. **Check Facebook Events Manager** to see if events are being tracked

## 📊 Tracked Events

Your landing page will automatically track these Facebook Pixel events:

### 1. **PageView** 🔍
- **When**: Immediately when the page loads
- **Purpose**: Track visitors to your landing page

### 2. **ViewContent** 👀
- **When**: After 5 seconds (configurable)
- **Purpose**: Track engaged users who spend time on the page
- **Data**: 
  ```javascript
  {
    content_name: 'Landing Page Engagement',
    content_category: 'User Interaction'
  }
  ```

### 3. **Lead** 🎯
- **When**: When user clicks "Join Now" button
- **Purpose**: Track users who show intent to join
- **Data**:
  ```javascript
  {
    content_name: 'OPTRIXTRADES Bot Access',
    content_category: 'Trading Bot',
    value: 1.00,
    currency: 'USD'
  }
  ```

### 4. **InitiateCheckout** 🛒
- **When**: Just before auto-redirect to Telegram (after 10 seconds)
- **Purpose**: Track users who are about to join the bot
- **Data**:
  ```javascript
  {
    content_name: 'Bot Registration Intent',
    content_category: 'Trading Bot'
  }
  ```

## 🔧 Configuration Options

### Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `FACEBOOK_PIXEL_ID` | `YOUR_PIXEL_ID` | Your Facebook Pixel ID (Required) |
| `FACEBOOK_PIXEL_ENABLED` | `true` | Enable/disable all pixel tracking |
| `TRACK_PAGE_VIEW` | `true` | Track page views |
| `TRACK_LEAD_CONVERSION` | `true` | Track lead conversions |
| `TRACK_ENGAGEMENT` | `true` | Track user engagement |
| `AUTO_REDIRECT_DELAY` | `10` | Seconds before auto-redirect |
| `ENGAGEMENT_TRACKING_DELAY` | `5` | Seconds before tracking engagement |

### Testing Configuration

Run this command to check your current configuration:

```bash
python facebook_pixel_config.py
```

Expected output:
```
🎯 Facebook Pixel Configuration Summary
======================================

Pixel Settings:
- Pixel ID: 123456789012345
- Enabled: True
- Configured: True

Tracking Events:
- Page View: True
- Lead Conversion: True
- Engagement: True

Timing Settings:
- Auto-redirect Delay: 10 seconds
- Engagement Tracking: 5 seconds

✅ Ready for tracking!
======================================
```

## 🧪 Testing Your Setup

### 1. Facebook Pixel Helper (Chrome Extension)

1. Install [Facebook Pixel Helper](https://chrome.google.com/webstore/detail/facebook-pixel-helper/fdgfkebogiimcoedlicjlajpkdmockpc)
2. Visit your landing page: `https://bot.optrixtrades.com`
3. Check if the extension shows your Pixel ID and events

### 2. Facebook Events Manager

1. Go to **Events Manager** in Facebook Business Manager
2. Select your Pixel
3. Check **Test Events** tab
4. Visit your landing page and verify events appear

### 3. Browser Developer Tools

1. Open your landing page
2. Open Developer Tools (F12)
3. Go to **Console** tab
4. Look for Facebook Pixel logs

## 🎨 Customization

### Custom Event Tracking

You can add custom events by modifying the `facebook_pixel_config.py` file:

```python
# Add custom event configuration
TRACK_CUSTOM_EVENT = os.getenv('TRACK_CUSTOM_EVENT', 'true').lower() == 'true'
CUSTOM_EVENT_DELAY = int(os.getenv('CUSTOM_EVENT_DELAY', '15'))
```

### Custom Event Values

Modify the event data in `landing.html`:

```javascript
fbq('track', 'Lead', {
    content_name: 'OPTRIXTRADES Bot Access',
    content_category: 'Trading Bot',
    value: 5.00,  // Increase lead value
    currency: 'USD'
});
```

## 🔒 Privacy & Compliance

### GDPR Compliance

For EU users, consider adding a cookie consent banner:

```html
<!-- Add to landing.html -->
<div id="cookie-banner" style="display:none;">
    <p>We use cookies and tracking pixels to improve your experience.</p>
    <button onclick="acceptCookies()">Accept</button>
</div>
```

### Data Processing

Facebook Pixel will collect:
- Page visits
- Button clicks
- Time spent on page
- Browser information
- IP address (for location)

## 🚨 Troubleshooting

### Common Issues

1. **Pixel Not Loading**
   - Check if `FACEBOOK_PIXEL_ID` is set correctly
   - Verify domain is added to Facebook Business Manager
   - Check browser ad blockers

2. **Events Not Tracking**
   - Verify Pixel ID in Facebook Events Manager
   - Check browser console for errors
   - Test with Facebook Pixel Helper

3. **Configuration Not Working**
   - Run `python facebook_pixel_config.py` to check settings
   - Verify environment variables are set in Railway
   - Restart the webhook server after changes

### Debug Mode

Enable debug logging by adding to your environment:

```bash
FACEBOOK_PIXEL_DEBUG=true
```

## 📈 Analytics & Optimization

### Key Metrics to Track

1. **Page Views**: Total visitors to landing page
2. **Engagement Rate**: ViewContent / PageView
3. **Lead Conversion**: Lead events / PageView
4. **Bot Join Rate**: InitiateCheckout / PageView

### Facebook Ads Optimization

Use these events for Facebook Ads optimization:

- **Awareness Campaigns**: Optimize for PageView
- **Engagement Campaigns**: Optimize for ViewContent
- **Conversion Campaigns**: Optimize for Lead or InitiateCheckout

## 🎯 Next Steps

1. **Set up Facebook Pixel** with your actual Pixel ID
2. **Deploy the changes** to Railway
3. **Test the tracking** using Facebook Pixel Helper
4. **Create Facebook Ads** targeting your tracked events
5. **Monitor performance** in Facebook Events Manager

---

**Need Help?** Check the [Facebook Pixel documentation](https://developers.facebook.com/docs/facebook-pixel/) or contact support.