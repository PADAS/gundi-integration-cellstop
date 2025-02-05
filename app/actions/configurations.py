from pydantic import SecretStr, Field
from app.services.utils import GlobalUISchemaOptions
from .core import PullActionConfiguration, AuthActionConfiguration, ExecutableActionMixin


class AuthenticateConfig(AuthActionConfiguration, ExecutableActionMixin):
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

