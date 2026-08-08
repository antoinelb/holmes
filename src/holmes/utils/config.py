import hashlib
from typing import Any

##########
# public #
##########


def hash_config(config: dict[str, Any]) -> str:
    _config = _prepare_config_for_hashing(config)
    return hashlib.sha256(str(_config).encode()).hexdigest()[:8]


###########
# private #
###########


def _prepare_config_for_hashing(config: Any) -> Any:
    if isinstance(config, dict):
        return {
            key: _prepare_config_for_hashing(config[key])
            for key in sorted(config)
            if key != "hash"
        }
    elif isinstance(config, list):
        return [_prepare_config_for_hashing(x) for x in config]
    else:
        return config
