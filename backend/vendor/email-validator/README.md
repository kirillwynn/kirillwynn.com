# email-validator (offline shim)

This vendored package provides a minimal subset of the `email_validator` API
needed by WTForms' `Email` validator. It performs basic syntax checks without
DNS lookups so the application can run in network-restricted environments.
