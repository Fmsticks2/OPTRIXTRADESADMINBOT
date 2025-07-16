#!/usr/bin/env python3
"""
Facebook Pixel Configuration for OPTRIXTRADES Landing Page
"""

import os
from typing import Optional

class FacebookPixelConfig:
    """
    Configuration class for Facebook Pixel integration
    """
    
    # Facebook Pixel Settings
    FACEBOOK_PIXEL_ID: str = os.getenv('FACEBOOK_PIXEL_ID', 'YOUR_PIXEL_ID')
    FACEBOOK_PIXEL_ENABLED: bool = os.getenv('FACEBOOK_PIXEL_ENABLED', 'true').lower() == 'true'
    
    # Tracking Events Configuration
    TRACK_PAGE_VIEW: bool = os.getenv('TRACK_PAGE_VIEW', 'true').lower() == 'true'
    TRACK_LEAD_CONVERSION: bool = os.getenv('TRACK_LEAD_CONVERSION', 'true').lower() == 'true'
    TRACK_ENGAGEMENT: bool = os.getenv('TRACK_ENGAGEMENT', 'true').lower() == 'true'
    
    # Landing Page Settings
    AUTO_REDIRECT_DELAY: int = int(os.getenv('AUTO_REDIRECT_DELAY', '30'))  # seconds
    ENGAGEMENT_TRACKING_DELAY: int = int(os.getenv('ENGAGEMENT_TRACKING_DELAY', '5'))  # seconds
    
    @classmethod
    def is_pixel_configured(cls) -> bool:
        """Check if Facebook Pixel is properly configured"""
        return (
            cls.FACEBOOK_PIXEL_ENABLED and 
            cls.FACEBOOK_PIXEL_ID and 
            cls.FACEBOOK_PIXEL_ID != 'YOUR_PIXEL_ID'
        )
    
    @classmethod
    def get_pixel_script(cls) -> Optional[str]:
        """Get the Facebook Pixel script with the configured ID"""
        if not cls.is_pixel_configured():
            return None
            
        return f"""
        !function(f,b,e,v,n,t,s)
        {{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?
        n.callMethod.apply(n,arguments):n.queue.push(arguments)}};
        if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
        n.queue=[];t=b.createElement(e);t.async=!0;
        t.src=v;s=b.getElementsByTagName(e)[0];
        s.parentNode.insertBefore(t,s)}}(window, document,'script',
        'https://connect.facebook.net/en_US/fbevents.js');
        
        fbq('init', '{cls.FACEBOOK_PIXEL_ID}');
        fbq('track', 'PageView');
        """
    
    @classmethod
    def get_noscript_tag(cls) -> Optional[str]:
        """Get the noscript fallback tag"""
        if not cls.is_pixel_configured():
            return None
            
        return f'<img height="1" width="1" style="display:none" src="https://www.facebook.com/tr?id={cls.FACEBOOK_PIXEL_ID}&ev=PageView&noscript=1"/>'
    
    @classmethod
    def get_summary(cls) -> str:
        """Get configuration summary"""
        return f"""
🎯 Facebook Pixel Configuration Summary
======================================

Pixel Settings:
- Pixel ID: {cls.FACEBOOK_PIXEL_ID}
- Enabled: {cls.FACEBOOK_PIXEL_ENABLED}
- Configured: {cls.is_pixel_configured()}

Tracking Events:
- Page View: {cls.TRACK_PAGE_VIEW}
- Lead Conversion: {cls.TRACK_LEAD_CONVERSION}
- Engagement: {cls.TRACK_ENGAGEMENT}

Timing Settings:
- Auto-redirect Delay: {cls.AUTO_REDIRECT_DELAY} seconds
- Engagement Tracking: {cls.ENGAGEMENT_TRACKING_DELAY} seconds

{'✅ Ready for tracking!' if cls.is_pixel_configured() else '⚠️  Please set FACEBOOK_PIXEL_ID environment variable'}
======================================
        """.strip()

# Create global config instance
fb_pixel_config = FacebookPixelConfig()

if __name__ == "__main__":
    print(fb_pixel_config.get_summary())