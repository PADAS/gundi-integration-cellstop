from pydantic import SecretStr, Field
from app.services.utils import GlobalUISchemaOptions
from .core import PullActionConfiguration, AuthActionConfiguration


class AuthenticateConfig(AuthActionConfiguration):
    username: str
    password: SecretStr = Field(..., format="password")

    ui_global_options: GlobalUISchemaOptions = GlobalUISchemaOptions(
        order=[
            "username",
            "password",
        ],
    )


class PullObservationsConfig(PullActionConfiguration):
    endpoint: str = "mobile/vehicles"

