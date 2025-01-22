from pydantic import SecretStr
from app.services.utils import GlobalUISchemaOptions
from .core import PullActionConfiguration, AuthActionConfiguration


class AuthenticateConfig(AuthActionConfiguration):
    username: str
    password: SecretStr

    ui_global_options: GlobalUISchemaOptions = GlobalUISchemaOptions(
        order=[
            "username",
            "password",
        ],
    )


class PullObservationsConfig(PullActionConfiguration):
    endpoint: str = "mobile/vehicles"

