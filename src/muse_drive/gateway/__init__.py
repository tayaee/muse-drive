from .gateway import Gateway, AuthError, GatewayError, load_cookies

# Alias Gateway to GatewayClient for readability
GatewayClient = Gateway

__all__ = ["Gateway", "GatewayClient", "AuthError", "GatewayError", "load_cookies"]
