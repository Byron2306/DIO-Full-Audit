"""Telegram is terminated at the DIO Presence Edge (HF Space). This core adapter exists as an architectural marker only.
The edge must authenticate Telegram's webhook secret and HMAC-sign the normalized envelope before DIO accepts it.
"""
CHANNEL="telegram"
WRITE_AUTHORITY="reply_only_after_dio_response"
