"""Sales Research Assistant — Project 8.

Generates a one-page pre-call sales brief from three data sources:
1. Public web intelligence (Tavily)
2. Internal case study library (pgvector RAG)
3. ICP and recent CRM context (later phase)

Heavy reuse of services/nlp infra: llm_client, auth, db, CI pipeline.
"""
