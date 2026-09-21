# Security Policy

## Reporting a vulnerability

Please do not open a public issue for a security problem.

Report it privately through GitHub's [private vulnerability
reporting](https://github.com/Ernosto0/JevKit/security/advisories/new). Include what you
found, how to reproduce it, and what an attacker could do with it. You can expect an
acknowledgement within a few days.

## Supported versions

JevKit is pre-alpha. Only the `main` branch receives fixes until v0.1 is tagged.

## Scope

In scope: credential leakage, injection into provider requests, unbounded resource consumption,
authentication bypass in the API service, and sensitive data appearing in traces or logs.

Out of scope: the behavior of the Jev API itself, and the accuracy of any model's decisions.

## Design commitments

These are properties the project intends to hold. A break in any of them is a security bug:

- **Credentials stay server-side.** Provider API keys are never logged, traced, serialized into
  a result, or returned to an API client. Error messages must not echo them.
- **Untrusted input stays data.** User input and retrieved content are never treated as
  instructions to the surrounding system.
- **Model output never acts.** A decision is a recommendation. JevKit does not execute shell
  commands, call external services, or perform privileged actions based on a model result.
  Authorization stays with the calling application.
- **Everything is bounded.** Retries, timeouts, request body size and concurrency all have
  explicit limits. There is no unbounded retry or fallback loop.
- **Schemas are enforced.** Every input is checked against its task's declared fields, and
  every answer against its question's type — including answers from a fallback provider.
- **Traces are metadata-first.** Input capture is off by default, retention is configurable,
  and the trace storage column is nullable on purpose.

## High-impact decisions

For decisions affecting money, access, employment, health, legal status, or comparable
outcomes, use `OnFailure.REVIEW` and treat the result as input to a human decision. JevKit does
not present model output as a definitive determination, and neither should an application
built on it.
