# BEAST release keys

This file pins release-verification material for BEAST C4-X proof capsules.

## BEAST C4-X physical truth release key · 2026-08-03

Status: active for the C4-X physical-truth source-file-bound proof capsule.

Key type: SSH Ed25519

Declared use:

- signing BEAST C4-X proof bundles;
- publishing those signatures to a public transparency log;
- verifying that downloaded proof capsules match the artifact logged in Rekor.

Public key:

```text
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICchCycJgQwjU22Y2vigrOYNRAMewXK0BiS8OpmIOb/T beast-c4x-physical-truth-2026-08-03
```

SSH fingerprint:

```text
SHA256:dPClisgoezAMAYxhiU2O/E0x6hueE3MBqPXmUvHLfRg
```

Public-key file SHA-256:

```text
sha256:8e872677bdabb5f31a0f3e7c1c542d4df124a4afaff85fb2d698f760485f8fca
```

Signed artifact:

```text
artifacts/BEAST_C4X_PHYSICAL_TRUTH_12_GATE_DIGEST_BOUND_SELF_CONTAINED_2026-08-03.zip
```

Artifact SHA-256:

```text
sha256:50a8ce87c2140e26d85fc31a04ea78e5e737202ce1d69a476f7b4b88e4a2d8ce
```

Detached SSH signature SHA-256:

```text
sha256:ce9db7ebef0969b9ee0e023b4c684b65851c71c91df7f10e87d8080c716e4e59
```

Rekor UUID:

```text
108e9186e8c5677ac634a8c30255042bd7a67e75e414ca8d4a0ec2544e768e8b26b6e4b8c388633d
```

Rekor entry:

```text
https://rekor.sigstore.dev/api/v1/log/entries/108e9186e8c5677ac634a8c30255042bd7a67e75e414ca8d4a0ec2544e768e8b26b6e4b8c388633d
```

Verification packet:

```text
artifacts/BEAST_C4X_REKOR_TRANSPARENCY_PACKET_2026-08-03.zip
sha256:789530c07a3f847c937da13fda27a11252bf4be730f0bcf1b023b7e723d53948
```

Boundary:

This file pins the BEAST C4-X release key inside the repository. Public identity
binding becomes stronger once this same file/key appears in the public GitHub
repository, signed Git tag, GitHub release notes, and preregistration. For a
future final public release, prefer a Sigstore Fulcio/OIDC keyless certificate
issued from a declared GitHub workflow or another independently controlled
identity provider.

## Sophia/Integritas lineage key · 2026-08-04

Status: active for the DAI Phase 6.3 Sophia/Integritas unified lineage
certificate.

Key type: raw Ed25519 public key

Declared use:

- verifying the exact Sophia/Integritas academic-integrity export digest that
  entered BEAST;
- binding that export to the Phase-1 Seraph challenge, Commons quorum,
  promotion and Arda bounded replay lineage;
- binding the same export to the Phase-6.1 and Phase-6.2 deterministic
  expression / capability-ledger lineage.

Signer id:

```text
integritas-sophia-local-lineage-signer
```

Public key:

```text
naO+wn9I36pjrK9uufn+s5PpZBEmqySpvfx8wiKOD8Y=
```

Public-key fingerprint:

```text
sha256:bcfad7dbb07bff2858b7fc2172a5f40e1684012fe9764897e8d77a7a010028cc
```

Machine-readable key policy:

```text
release-keys/sophia_integritas_lineage_key_policy.json
sha256:34fe8e196c2218661585abe6ed6d850efa44d972f086fad81161214bc4c26e6f
```

Signed Sophia export digest:

```text
sha256:5fa74d666de74bbd1de9b41d5652cd6f16ee39d8985ab4de3ca6ef758fa6d3a2
```

Unified lineage certificate:

```text
evidence/dai-diode/phase6-sophia-integritas-lineage/sophia_integritas_unified_lineage_certificate.json
sha256:30caf2b353d25997eda1dc3a546db0e9637ce93ed4cb8e8a6be46428ee7a4332
```

Boundary:

This pins the Sophia/Integritas lineage key to the BEAST project evidence
policy for the named certificate. It proves project continuity for this
lineage key once this file is committed and published. It is not an NWU,
employer, journal, institutional, or third-party endorsement. A future public
release can strengthen this with Sigstore Fulcio/OIDC, a signed Git tag,
release notes, and transparency-log inclusion.
