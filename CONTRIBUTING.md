# Contributing to ChessGuard

Thank you for your interest in improving ChessGuard!  The project aims to stay
lightweight, reproducible and well documented.  Contributions that align with
these principles are very welcome.

## Development Workflow

1. Fork the repository and create a feature branch.
2. Install the project in editable mode (`pip install -e .`) and install any
dev-only tooling you require (e.g. `pytest`).
3. Write tests covering the new behaviour or bug fix.
4. Ensure `python -m pytest` passes locally.
5. Submit a pull request describing the motivation, implementation details and
testing steps.

## Coding Guidelines

* Keep the standard library as the only runtime dependency unless a strong
  justification exists.
* Prefer descriptive variable names and module level docstrings to aid future
  contributors.
* Avoid premature optimisation; prioritise clarity and determinism.
* When adding new detection strategies, surface interpretable explanations via
  the existing reporting helpers.

## Reporting Issues

Please include:

* A minimal reproduction (PGN/telemetry files where possible).
* The observed vs expected behaviour.
* Environment information (Python version, operating system, etc.).

## Security & Ethics

Chess cheating detection can have real-world implications.  When contributing
new ideas, consider the ethical impact, fairness and privacy of the proposed
approach.  Contributions promoting transparency and due process are
particularly valuable.
