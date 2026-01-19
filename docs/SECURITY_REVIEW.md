# ChessGuard Security Review

_Last updated: 2024-09-22_

## Executive summary

The repository now ships with three distinct components: an authentication service, a site backend, and a static web
client. The codebase was reviewed following the OWASP Application Security Verification Standard (ASVS) Level 1/2
principles with emphasis on the authentication and data-handling pathways. Overall, the system implements strong
foundational controls—most notably Argon2id password hashing, JWT-based session tokens, TLS enablement hooks, and
environment-managed secrets. Remaining risks mainly relate to deployment hardening and operational monitoring.

## Methodology

The assessment combined manual source review and automated tooling:

- Walkthrough of the authentication service (`auth/`) covering registration, login, credential storage, and token
  issuance flows.
- Inspection of the backend service (`server/`) focusing on authorization checks, data storage, and API surface.
- Review of the front-end client for token handling and communication patterns.
- Evaluation of Docker and CI configurations for infrastructure hardening.
- Execution of unit tests and dependency vulnerability scans.

## Findings and analysis

### Authentication and session management (OWASP ASVS V2)

- **Password storage** – User passwords are hashed with `argon2-cffi` using the Argon2id algorithm, providing strong
  resistance to offline cracking attempts.
- **Password policy** – Registration enforces a 12 character minimum, aligning with OWASP recommendations for complex
  secrets.
- **Account enumeration** – Registration returns a generic `400` error for existing email addresses, which could reveal
  account existence. For high-sensitivity deployments, replace this with a generic response and send notifications
  through out-of-band channels.
- **Authentication tokens** – Access tokens are JSON Web Tokens signed with a shared secret and short lifetimes
  (default: 24 hours). The backend validates tokens on every request using the same secret.
- **Token storage** – The client stores JWTs in `sessionStorage`, limiting exposure to XSS-persistent storage. Ensure the
  front-end is served over HTTPS and with a strong Content Security Policy to reduce token theft risk.

### Access control (OWASP ASVS V4)

- All API routes on the backend require a valid bearer token. There is no concept of roles yet, so all authenticated users
  have equivalent privileges. If future roles are needed (e.g., administrators versus players), extend the token payload
  and authorization logic accordingly.

### Cryptography and secret management (OWASP ASVS V6)

- Encryption keys and signing secrets are supplied exclusively via environment variables (`AUTH_JWT_SECRET`,
  `SERVER_JWT_SECRET`). The services refuse to start when secrets are absent, encouraging integration with a vault such as
  HashiCorp Vault, AWS Secrets Manager, or Kubernetes secrets.
- TLS termination is supported through environment-configured certificate paths. For production, run the services behind
  a reverse proxy (e.g., Nginx, Traefik) with automatic certificate rotation.

### Data protection and integrity (OWASP ASVS V7)

- SQLite is used by default for simplicity; data directories are writable volumes defined by Docker Compose. For
  production, migrate to a managed database with encryption at rest and regular backups.
- Input validation uses Pydantic, providing type coercion and length checks for request payloads. Additional validation
  may be required for `moves` PGN fields if the server is extended to run chess engines.

### Logging, auditing, and monitoring (OWASP ASVS V10)

- The current implementation lacks structured logging and audit trails. Introduce request logging and security event logs
  (e.g., failed login counters) that can be shipped to SIEM tooling.
- Rate limiting is not yet enforced. Deploy services behind an API gateway or add application-level throttling to reduce
  brute-force exposure.

### Dependency and supply chain security (OWASP ASVS V14)

- GitHub Actions workflow runs unit tests, `pip-audit` for Python dependencies, and `npm audit` for the client, providing
  automated visibility into upstream vulnerabilities.
- Python dependencies are pinned to exact versions; ensure timely updates via Dependabot or Renovate.

## Recommendations

1. Configure TLS certificates and secrets via a dedicated secrets manager and ensure the same signing secret is used by
   both auth and backend services.
2. Add structured logging, tracing, and rate limiting to improve incident response and resilience against automated
   attacks.
3. Consider adopting refresh tokens with short-lived access tokens for enhanced session security, especially on shared
   devices.
4. Expand automated testing to include integration tests that cover inter-service communication through Docker Compose.
5. Harden deployment by using container image scanning (e.g., Trivy) and infrastructure-as-code validation as part of the
   CI/CD pipeline.

## Conclusion

ChessGuard now provides a secure foundation for user authentication and chess data management. The implementation aligns
with OWASP-recommended practices for credential handling and secret management, and the CI pipeline offers continuous
security assurance. Continued investment in observability, threat monitoring, and operational defenses will further
improve the system's security posture.
