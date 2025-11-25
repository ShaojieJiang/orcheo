# Troubleshooting Guide

This guide lists frequent issues encountered when running conversational search workflows with Orcheo and how to resolve them quickly.

## Slow Retrieval
- Ensure embeddings are generated for the latest documents.
- Check that the vector store is warmed up and not using a cold cache.
- Reduce `top_k` temporarily to verify the query path is healthy.

## Hallucinated Answers
- Confirm the generator is instructed to cite sources for every statement.
- Increase the similarity threshold in the retrieval config to tighten context.
- Add a hallucination guard node to validate outputs before returning them.

## Missing Documents
- Verify the loader glob patterns include the new files.
- Re-run the ingestion pipeline after adding or renaming documents.
- Inspect metadata extraction to ensure titles and sections are captured.

## Authentication Failures
- Make sure the correct environment variables are loaded from your `.env` file.
- Rotate expired keys and re-run the sample demos with fresh credentials.
- Use the built-in health check script to validate network connectivity.
