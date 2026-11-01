# Kritva Sense Security Policy

**Repository:** `kritva-sense`
**Security Owner:** Dinesh (program decision D-032)

## 1. Scope

Reproducible security vulnerabilities in this repository's code, tooling, documentation and CI configuration. The repository holds the Sense contracts, a reference implementation in Python (the validator, frame graph, stream checker, synthetic data generator and consumer conformance harness, standard library only), the CI workflows and the release files. The consumer conformance harness imports the consumer module it is given into its own process and is not a sandbox: do not run it on code you do not trust (see `src/kritva_sense/CONFORMANCE.md` and `tasks/KOS-SENSE-008/THREAT_MODEL.md`).

## 2. Do not disclose unfixed vulnerabilities publicly

Please do not put details of an unpatched vulnerability in a public issue, pull request, discussion or post.

## 3. Reporting

Reporting route: GitHub private vulnerability reporting for this repository (Security tab, "Report a vulnerability") is the first route. The Security Owner (Dinesh, D-032) reports that the reporting route was tested on 18 October 2026 (D-068). That is an owner statement; it has not been independently verified from this repository. If that option is not available to you, contact the Security Owner directly through your existing Kritva channel, say only that you have a security report, and ask for a private place to share the details; do not put details in the first message.

Include the affected file or commit, a description, steps to reproduce, observed and expected behaviour, the potential impact and any mitigation you know of. Leave out personal, customer, credential or production data.

## 4. What to expect

The Security Owner will make reasonable efforts to acknowledge a valid report, assess it, coordinate a fix and agree disclosure timing. This policy sets no guaranteed deadlines.

## 5. Secrets

Never commit credentials, tokens, private keys or production data. If one is committed by mistake, tell the Security Owner at once so it can be revoked or rotated.
