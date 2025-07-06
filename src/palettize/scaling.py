"""Domain-to-range scaling functions for Palettize."""

import math
from typing import Callable

ScalingFunction = Callable[[float], float]


def linear_scale(
    value: float, domain_min: float, domain_max: float, clamp: bool = True
) -> float:
    """
    Performs linear scaling of a value from a given domain to the range [0, 1].
    """
    if domain_min == domain_max:
        raise ValueError(
            "domain_min and domain_max cannot be equal for linear scaling."
        )
    normalized_value = (value - domain_min) / (domain_max - domain_min)
    if clamp:
        return max(0.0, min(1.0, normalized_value))
    return normalized_value


def get_linear_scaler(
    domain_min: float, domain_max: float, clamp: bool = True
) -> ScalingFunction:
    """
    Returns a linear scaling function configured with the given domain.
    """
    if domain_min == domain_max:
        raise ValueError(
            "domain_min and domain_max cannot be equal for get_linear_scaler."
        )

    def scaler(value: float) -> float:
        return linear_scale(value, domain_min, domain_max, clamp)

    return scaler


def power_scale(
    value: float,
    domain_min: float,
    domain_max: float,
    exponent: float,
    clamp: bool = True,
) -> float:
    """
    Performs power scaling: y = ((x - min)/(max - min))^exponent.
    Raises ValueError for invalid domain or if clamp=False and result is complex.
    """
    if domain_min == domain_max:
        raise ValueError("domain_min and domain_max cannot be equal for power scaling.")

    normalized_base = (value - domain_min) / (domain_max - domain_min)

    if clamp:
        if value <= domain_min:
            effective_normalized_base = 0.0
        elif value >= domain_max:
            effective_normalized_base = 1.0
        else:
            effective_normalized_base = normalized_base
        scaled_value = effective_normalized_base**exponent
        return max(0.0, min(1.0, scaled_value))
    else:
        scaled_value = normalized_base**exponent
        return scaled_value


def sqrt_scale(
    value: float, domain_min: float, domain_max: float, clamp: bool = True
) -> float:
    """Square root scaling. Equivalent to power_scale with exponent 0.5."""
    return power_scale(value, domain_min, domain_max, 0.5, clamp)


def get_power_scaler(
    domain_min: float, domain_max: float, exponent: float, clamp: bool = True
) -> ScalingFunction:
    """Returns a power scaling function."""
    if domain_min == domain_max:
        raise ValueError(
            "domain_min and domain_max cannot be equal for get_power_scaler."
        )

    def scaler(value: float) -> float:
        return power_scale(value, domain_min, domain_max, exponent, clamp)

    return scaler


def get_sqrt_scaler(
    domain_min: float, domain_max: float, clamp: bool = True
) -> ScalingFunction:
    """Returns a square root scaling function."""
    return get_power_scaler(domain_min, domain_max, 0.5, clamp)


def log_scale(
    value: float,
    domain_min: float,
    domain_max: float,
    base: float = 10.0,
    clamp: bool = True,
) -> float:
    """
    Performs logarithmic scaling. Domain and value must be positive.
    """
    if base <= 0 or base == 1:
        raise ValueError("Logarithm base must be > 0 and not equal to 1.")
    if domain_min <= 0 or domain_max <= 0:
        raise ValueError(
            "Logarithmic scale domain (domain_min, domain_max) must be positive."
        )
    if domain_min >= domain_max:
        raise ValueError(
            "domain_min must be less than domain_max for logarithmic scaling."
        )

    log_domain_min = math.log(domain_min, base)
    log_domain_max = math.log(domain_max, base)

    if clamp:
        if value <= domain_min:
            return 0.0
        if value >= domain_max:
            return 1.0
        if value <= 0:  # Should be caught by value <= domain_min if domain_min > 0
            raise ValueError(
                "Input value for clamped log_scale must be positive within domain."
            )
        log_value = math.log(value, base)
        scaled_value = (log_value - log_domain_min) / (log_domain_max - log_domain_min)
        return max(0.0, min(1.0, scaled_value))
    else:
        if value <= 0:
            raise ValueError("Input value for non-clamped log_scale must be positive.")
        log_value = math.log(value, base)
        if (
            log_domain_max - log_domain_min
        ) == 0:  # Should be caught by domain_min >= domain_max
            raise ValueError("Log-transformed domain has zero range.")
        return (log_value - log_domain_min) / (log_domain_max - log_domain_min)


def get_log_scaler(
    domain_min: float, domain_max: float, base: float = 10.0, clamp: bool = True
) -> ScalingFunction:
    """Returns a logarithmic scaling function."""
    if base <= 0 or base == 1:
        raise ValueError("Logarithm base must be > 0 and not equal to 1.")
    if domain_min <= 0 or domain_max <= 0:
        raise ValueError(
            "Logarithmic scale domain (domain_min, domain_max) must be positive."
        )
    if domain_min >= domain_max:
        raise ValueError(
            "domain_min must be less than domain_max for logarithmic scaling."
        )

    log_domain_min = math.log(domain_min, base)
    log_domain_max = math.log(domain_max, base)
    log_domain_range = log_domain_max - log_domain_min
    if log_domain_range == 0:
        raise ValueError("Log-transformed domain has zero range.")

    def scaler(value: float) -> float:
        return log_scale(
            value, domain_min, domain_max, base, clamp
        )  # Delegate to log_scale for logic

    return scaler


def _symlog_transform(value: float, linthresh: float, base: float) -> float:
    """Internal symlog transformation function."""
    if linthresh <= 0:
        raise ValueError("Symlog linear threshold (linthresh) must be positive.")
    # Ensure base is valid for log, though get_symlog_scaler will also check.
    # if base <= 0 or base == 1: raise ValueError("Logarithm base must be > 0 and not equal to 1.")

    abs_value = abs(value)
    if abs_value < linthresh:
        # The linear part is scaled such that at value = +/-linthresh, the output is +/-1.
        # This ensures continuity with the logarithmic part if it starts at 1.
        return value / linthresh
    else:
        # Logarithmic part: starts from 1 (or -1) and grows logarithmically.
        # The (abs_value / linthresh) ensures that at the threshold, the log argument is 1 (log(1)=0).
        # So, at threshold, output is sign(value) * (1 + 0) = sign(value).
        return math.copysign(1.0 + math.log(abs_value / linthresh, base), value)


def symlog_scale(
    value: float,
    domain_min: float,
    domain_max: float,
    linthresh: float,
    base: float = 10.0,
    clamp: bool = True,
) -> float:
    """
    Performs symmetric logarithmic (symlog) scaling.
    Useful for data with a wide dynamic range that includes zero and negative values.

    Args:
        value: The input value to scale.
        domain_min: The minimum value of the input domain.
        domain_max: The maximum value of the input domain.
        linthresh: The threshold around zero within which the scale is linear. Must be positive.
        base: The base of the logarithm used for the non-linear part (default 10.0).
        clamp: If True (default), clamps the output to [0, 1].

    Returns:
        The scaled value, typically in [0, 1] if clamped.

    Raises:
        ValueError: If domain_min >= domain_max, linthresh <= 0, or base is invalid.
    """
    if linthresh <= 0:
        raise ValueError("Symlog linear threshold (linthresh) must be positive.")
    if base <= 0 or base == 1:
        raise ValueError("Logarithm base must be > 0 and not equal to 1.")
    if domain_min >= domain_max:
        # Symlog can handle domain_min == domain_max if linthresh is well defined relative to it.
        # However, the final linear scaling of transformed values would have div by zero.
        raise ValueError("domain_min must be less than domain_max for symlog scaling.")

    # Transform the domain and the value
    transformed_min = _symlog_transform(domain_min, linthresh, base)
    transformed_max = _symlog_transform(domain_max, linthresh, base)

    # Check if transformed domain is valid for scaling
    if transformed_min == transformed_max:
        # This can happen if domain_min and domain_max are very close and fall into the same
        # region of the symlog transform or if linthresh is very large relative to domain.
        # Or if domain is [-C, C] and maps to [-1,1].
        # If they are equal, all values in the original domain map to the same transformed point.
        # We can return 0.0, 0.5, or 1.0 depending on where `value` falls relative to this point.
        # Or raise error, which is safer.
        # A common case: domain is e.g. [-1, 1] and linthresh is 1. Then transformed_min=-1, transformed_max=1.
        # If domain is [-0.5, 0.5] and linthresh is 1. transformed_min=-0.5, transformed_max=0.5.
        # If domain is [2,2] and linthresh 1. transformed_min=1+log(2), transformed_max=1+log(2) -> error here.
        raise ValueError(
            "Transformed symlog domain (domain_min, domain_max) has zero range. "
            "Check domain, linthresh, and base."
        )

    # Transform the value being scaled
    # If clamping, we want to clamp based on original domain values for the output range [0,1].
    # The _symlog_transform itself doesn't clamp to a specific output range other than what its math implies.
    if clamp:
        if value <= domain_min:
            return 0.0
        if value >= domain_max:
            return 1.0
        # If value is within domain, then proceed with transform and scale
        transformed_value = _symlog_transform(value, linthresh, base)
        scaled_output = (transformed_value - transformed_min) / (
            transformed_max - transformed_min
        )
        return max(0.0, min(1.0, scaled_output))  # Final safety clamp
    else:
        # No clamping, allow extrapolation
        transformed_value = _symlog_transform(value, linthresh, base)
        return (transformed_value - transformed_min) / (
            transformed_max - transformed_min
        )


def get_symlog_scaler(
    domain_min: float,
    domain_max: float,
    linthresh: float,
    base: float = 10.0,
    clamp: bool = True,
) -> ScalingFunction:
    """
    Returns a symmetric logarithmic (symlog) scaling function.
    """
    if linthresh <= 0:
        raise ValueError("Symlog linear threshold (linthresh) must be positive.")
    if base <= 0 or base == 1:
        raise ValueError("Logarithm base must be > 0 and not equal to 1.")
    if domain_min >= domain_max:
        raise ValueError("domain_min must be less than domain_max for symlog scaling.")

    transformed_min = _symlog_transform(domain_min, linthresh, base)
    transformed_max = _symlog_transform(domain_max, linthresh, base)

    if transformed_min == transformed_max:
        raise ValueError(
            "Transformed symlog domain (domain_min, domain_max) has zero range upon scaler creation. "
            "Check domain, linthresh, and base."
        )

    transformed_range = transformed_max - transformed_min

    def scaler(value: float) -> float:
        if clamp:
            if value <= domain_min:
                return 0.0
            if value >= domain_max:
                return 1.0
            transformed_val = _symlog_transform(value, linthresh, base)
            scaled_out = (transformed_val - transformed_min) / transformed_range
            return max(0.0, min(1.0, scaled_out))
        else:
            transformed_val = _symlog_transform(value, linthresh, base)
            return (transformed_val - transformed_min) / transformed_range

    return scaler


# --- Factory function to get scaler by name ---

_SCALER_FACTORIES = {
    "linear": get_linear_scaler,
    "power": get_power_scaler,
    "sqrt": get_sqrt_scaler,
    "log": get_log_scaler,
    "symlog": get_symlog_scaler,
}


def get_scaler_by_name(
    name: str, domain_min: float, domain_max: float, clamp: bool = True, **kwargs
) -> ScalingFunction:
    """
    Returns a scaling function by its name, configured with the given domain and options.

    Args:
        name: The name of the scaler (e.g., "linear", "power", "log", "symlog", "sqrt").
        domain_min: The minimum value of the input domain.
        domain_max: The maximum value of the input domain.
        clamp: Whether to clamp the output to [0, 1]. Defaults to True.
        **kwargs: Additional arguments specific to the scaler type:
            - for "power": `exponent` (float)
            - for "log": `base` (float, default 10.0)
            - for "symlog": `linthresh` (float), `base` (float, default 10.0)

    Returns:
        A configured ScalingFunction.

    Raises:
        ValueError: If the scaler name is unknown or required arguments are missing.
    """
    scaler_name = name.lower()
    if scaler_name not in _SCALER_FACTORIES:
        raise ValueError(
            f"Unknown scaler type: '{name}'. Available: {list(_SCALER_FACTORIES.keys())}"
        )

    factory = _SCALER_FACTORIES[scaler_name]

    # Prepare arguments for the specific factory
    factory_args = {"domain_min": domain_min, "domain_max": domain_max, "clamp": clamp}

    if scaler_name == "power":
        if "exponent" not in kwargs:
            raise ValueError("Missing required argument 'exponent' for power scaler.")
        factory_args["exponent"] = kwargs["exponent"]
    elif scaler_name == "log":
        if "base" in kwargs:
            factory_args["base"] = kwargs["base"]
        # 'base' has a default in get_log_scaler, so not strictly required here
    elif scaler_name == "symlog":
        if "linthresh" not in kwargs:
            raise ValueError("Missing required argument 'linthresh' for symlog scaler.")
        factory_args["linthresh"] = kwargs["linthresh"]
        if "base" in kwargs:
            factory_args["base"] = kwargs["base"]
        # 'base' has a default in get_symlog_scaler

    try:
        return factory(**factory_args)  # type: ignore
    except TypeError as e:
        # This might happen if a factory expects an arg that wasn't handled above
        # or if an unexpected kwarg was passed that the factory doesn't accept.
        raise ValueError(f"Incorrect arguments for scaler '{name}': {e}") from e
