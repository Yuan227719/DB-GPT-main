# Plan: DB-GPT Deep Research Supplement V2

## Overview

Based on deep codebase exploration, supplement `research_new.md` (currently 25 chapters, ~2017 lines) with 10 new chapters covering uncovered subsystems, and enhance 4 existing chapters with significantly more detail.

## New Chapters (10)

### 26. Datasource System Detail
- Full connector hierarchy (16+ database connectors)
- RDBMSConnector: connection pooling, SQL execution flow, timeout per-dialect
- convert_sql_write_to_select boundary case
- DBType enum, schema retrieval, dialect handling

### 27. Cache System
- LLMCacheKey/LLMCacheValue data models
- SHA-256 cache key generation
- Three storage backends: Memory (LRU/FIFO), Disk (RocksDB), Valkey
- AWEL Operator integration (ModelCacheBranchOperator, etc.)

### 28. Full-text Search & Graph Store
- Elasticsearch BM25 integration, metadata filtering
- Graph element types, MemoryGraph BFS search
- Neo4j/TuGraph connectors, graph visualization

### 29. Embedding Model Management
- EmbeddingFactory (Default/Wrapped), three creation modes
- Embedding backends: HuggingFace, BGE, Instructor, Inference API, OpenAPI
- Rerank models: CrossEncoder, QwenRerank (logits algorithm), OpenAPI, SiliconFlow, TEI, InfiniAI

### 30. AWEL DAG Lifecycle & Execution
- DAG build phase, DAGVar context tracking, BaseOperatorMeta metaclass auto-injection
- DefaultWorkflowRunner execution algorithm (topological order, branch skip propagation, JoinOperator skip logic)
- HttpTrigger (streaming vs non-streaming, _after_dag_end background task)
- IteratorTrigger (parallel execution, retry with exponential backoff, timeout, caching system)

### 31. Evaluate & Benchmark System
- EvaluationScene (RECALL, APP), metrics (RetrieverSimilarityMetric, AnswerRelevancyMetric)
- BenchmarkService background task execution
- LLM benchmark vs Agent benchmark
- Dataset management and result comparison

### 32. Tracing / Observability
- Span/SpanType lifecycle, ContextVar span stack
- DefaultTracer with 4 SpanStorageType modes
- MemorySpanStorage, FileSpanStorage (daily rolling), SpanStorageContainer (batching)
- @trace decorator, span context propagation via headers

### 33. Conversation Management
- StorageConversation lifecycle (create/query/list/delete/export)
- Two-layer storage: conversation + messages
- Message history enrichment (feedback, vis_name_change, model_name)
- Old message format backward compatibility

### 34. Model Worker/Cluster
- WorkerType, WorkerRunData with Semaphore
- LocalWorkerManager: startup/shutdown, model_startup/model_shutdown
- Heartbeat system (60s interval, 120s timeout)
- RemoteWorkerManager, ModelController, ModelRegistry
- Worker Manager REST API (10+ endpoints)

### 35. Supplementary Systems (i18n, CLI, Security, Serialization, Chat Models, Prompt Mgmt)
- i18n: gettext + LazyTranslatedString for Pydantic compatibility
- CLI: Full command tree (start/stop/db/new/app/repo/run/net/tool/setup/profile/model/trace)
- Module utils: import_from_string, ModelScanner
- Chat models: BaseMessage hierarchy, ModelMessage transformation, OnceConversation/StorageConversation
- Prompt management: PromptTemplate hierarchy, PromptManager, debug endpoint
- Security: API key validation, Variable encryption (Fernet + PBKDF2)
- Serialization: Serializable/Serializer, JsonSerializer, EnhancedJSONEncoder

## Enhanced Existing Chapters (4)

### Chapter 5 (Configuration): Add _convert_value edge cases table
Already completed from V1.

### Chapter 6 (Model Management): Add DeepSeek special handling details
Already completed from V1.

### Chapter 9 (AWEL): Significantly expand
- Add DAG lifecycle section (build, lazy compilation, context tracking)
- Add DefaultWorkflowRunner execution algorithm
- Add branch skip propagation mechanism
- Add trigger system details (HttpTrigger streaming, IteratorTrigger parallel/cache/retry)
- Add FlowRegistry and ViewMetadata details

### Chapter 10 (API Layer): Add security/auth details
- API key validation flow
- Variable encryption

### Chapter 16 (Data Flow): Add message model flow
- BaseMessage -> ModelMessage transformation pipeline
- OnceConversation -> StorageConversation persistence

## Implementation Steps

1. Read research_new.md again to understand current structure
2. Expand Chapter 9 (AWEL) with DAG lifecycle, execution, triggers
3. Expand Chapter 10 (API Layer) with security details
4. Add Chapter 26: Datasource System Detail
5. Add Chapter 27: Cache System
6. Add Chapter 28: Full-text Search & Graph Store
7. Add Chapter 29: Embedding Model Management
8. Add Chapter 30: AWEL DAG Lifecycle & Execution (detailed)
9. Add Chapter 31: Evaluate & Benchmark System
10. Add Chapter 32: Tracing / Observability
11. Add Chapter 33: Conversation Management
12. Add Chapter 34: Model Worker/Cluster
13. Add Chapter 35: Supplementary Systems
14. Expand Chapter 16 (Data Flow) with message model flow
15. Update Table of Contents
