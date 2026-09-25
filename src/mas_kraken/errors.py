"""Safe, provider-independent errors exposed to the conversation layer."""


class MasfsError(Exception):
    """Base class for expected MASFS failures."""


class ConfigurationError(MasfsError):
    """Invalid or missing runtime configuration."""


class ModelError(MasfsError):
    """A normalized model-provider failure with a safe public message."""


class ModelTimeoutError(ModelError):
    """A model request exceeded its configured timeout."""


class ModelAuthenticationError(ModelError):
    """The model provider rejected authentication."""


class ModelRateLimitError(ModelError):
    """The model provider rate-limited a request."""


class ModelResponseError(ModelError):
    """The provider returned an unusable response."""
