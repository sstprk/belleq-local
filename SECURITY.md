# Security

The lab API is intended for a trusted isolated LAN. It has no TLS termination or
internet-facing authentication service. Keep Qdrant and Ollama bound to loopback.
Do not forward the lab API or their ports onto the internet.

`BELLEQ_API_KEY` optionally enables the same `X-API-Key` header on coordinator,
workers and clients. A shared key does not replace TLS or network access controls.
Do not commit secrets, SSH passwords, private documents or unrelated captures.

The simulator binds to `127.0.0.1`; it does not contact the lab or execute submitted
questions against a live LLM. For vulnerabilities, use GitHub private vulnerability
reporting if available. Do not disclose live secrets in a public issue.
