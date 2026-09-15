# Analytics

Mercatus Agent provides comprehensive analytics across conversations, memory growth, and token usage.

## Conversation Analytics

- **Total Conversations**: Count of unique sessions
- **Total Messages**: Total messages processed
- **Average Confidence**: Average confidence score across all interactions

## Memory Analytics

- **Total Memories**: Combined episodic + semantic memory count
- **Episodic Memories**: Interaction history stored as episodes
- **Semantic Memories**: Knowledge facts and rules

## Token Analytics

- **Total Tokens**: Cumulative tokens processed
- **Average TPS**: Average tokens per second
- **Average Latency**: Average response latency in milliseconds

## API Endpoints

```
GET /api/v1/analytics/conversations
GET /api/v1/analytics/memory
GET /api/v1/analytics/tokens
```
