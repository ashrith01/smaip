"""Errors raised by the Week 1 scaffold."""


class SmaipError(Exception):
    """Base error for SMAIP."""


class SandboxError(SmaipError):
    """Raised when an expression or path leaves the sandbox."""


class ValidationError(SmaipError):
    """Raised when tool arguments fail schema checks."""


class UnknownEngine(SmaipError):
    """Raised when a chat request names an engine this scaffold will not run."""


class HfCpuDisabled(UnknownEngine):
    """Raised when the optional CPU model is requested while the flag is off.

    Raising this does not download weights.
    """


class NetworkRefused(SmaipError):
    """Raised when a client is asked to use the network."""


class ProbeWeightsUnavailable(SmaipError):
    """Raised when a probe would need to download or load model weights."""


class ProbeBackendUnavailable(SmaipError):
    """Raised when activation collection was asked for a backend it cannot run.

    Raising this on a missing install does not download weights.
    """


class TaintRejected(SmaipError):
    """Raised when an actor subject would be taken from tainted data."""
