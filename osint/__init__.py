"""Horcrux OSINT enrichment module."""

from .phone_intel import enrich_phone, COUNTRY_CODES
from .geo_intel import find_locations, ITALIAN_CITIES, lookup_city, reverse_geocode
from .email_intel import enrich_email, extract_emails
from .username_gen import generate_username_variants
from .social_check import check_username_on_socials, SOCIAL_SITES
from .emoji_words import emoji_to_keywords, expand_emoji_list
from .online_intel import (
    whois_lookup,
    dns_lookup,
    ip_geolocation,
    wayback_search,
    email_reputation,
    github_user_info,
    reddit_user_info,
    parse_codice_fiscale,
    find_codici_fiscali,
)

__all__ = [
    # Offline
    "enrich_phone",
    "find_locations",
    "lookup_city",
    "enrich_email",
    "extract_emails",
    "generate_username_variants",
    "check_username_on_socials",
    "ITALIAN_CITIES",
    "COUNTRY_CODES",
    "SOCIAL_SITES",
    "reverse_geocode",
    "emoji_to_keywords",
    "expand_emoji_list",
    # Online
    "whois_lookup",
    "dns_lookup",
    "ip_geolocation",
    "wayback_search",
    "email_reputation",
    "github_user_info",
    "reddit_user_info",
    "parse_codice_fiscale",
    "find_codici_fiscali",
]
