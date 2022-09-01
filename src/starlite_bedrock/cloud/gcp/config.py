from typing import Optional

from starlite_bedrock.schema import BaseSettings


class GoogleCloudSettings(BaseSettings):
    """Google Cloud Configuration

    Args:
        BaseSettings (_type_): _description_

    Returns:
        _type_: _description_
    """

    class Config:
        env_prefix = "GOOGLE_CLOUD_"
        fields = {
            "CREDENTIALS": {
                "env": "GOOGLE_APPLICATION_CREDENTIALS",
            },
        }

    PROJECT: str
    CREDENTIALS: Optional[str] = None
    RUNTIME_SECRETS: str = "run-config"
    WRITE_SECRETS: bool = False
    ASSETS_BUCKET: str = "app-assets"

    def get_secret_path(self) -> str:
        """Returns a string to the Google Secrets Path"""
        return f"projects/{self.PROJECT}/secrets/{self.RUNTIME_SECRETS}/versions/latest"
