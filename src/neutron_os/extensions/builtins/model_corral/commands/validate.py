"""neut model validate — validate a model directory."""

from __future__ import annotations

import json
from pathlib import Path


def cmd_validate(path: str, output_format: str = "human") -> int:
    """Validate a model directory and print results.

    Returns 0 on success, 1 on validation failure.
    """
    from neutron_os.extensions.builtins.model_corral.manifest import validate_model_dir

    model_dir = Path(path)
    result = validate_model_dir(model_dir)

    if output_format == "json":
        print(
            json.dumps(
                {
                    "valid": result.valid,
                    "errors": result.errors,
                    "warnings": result.warnings,
                    "path": str(model_dir),
                },
                indent=2,
            )
        )
    else:
        if result.valid:
            print(f"Validation passed: {model_dir}")
        else:
            print(f"Validation FAILED: {model_dir}")
            for error in result.errors:
                print(f"  - {error}")

    return 0 if result.valid else 1
