from authlib.integrations.starlette_client import OAuth

from npo.core.config import backend_settings

oauth = OAuth()

for provider, config in backend_settings.oauth_configs.items():
    oauth.register(name=provider, **config)
