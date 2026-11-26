# Changelog

## 0.0.1 — 2026-11-25

- The name `s3rag` reserved on PyPI; repository created from the series template (docs layer:
  bilingual README, architecture diagram). The design: documents on S3, the vector index as one
  S3 file built on demand with Bedrock embeddings, a Lambda that loads it in memory to answer
  queries with citations — no vector database, ≈ $0 when idle. Client, Terraform and tests follow.
