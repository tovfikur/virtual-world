from app.config import settings
print(f'API Prefix: [{settings.api_prefix}]')
print(f'Starts with /: {settings.api_prefix.startswith("/")}')
