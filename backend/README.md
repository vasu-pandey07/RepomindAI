# RepoMind AI Backend

FastAPI backend for RepoMind AI. It handles GitHub OAuth login, JWT authentication, PostgreSQL persistence, repository sync, repository indexing, code chunking, pgvector-backed embedding storage, and repository-aware RAG chat.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Environment

```env
DATABASE_URL=postgresql://repomind_user:repomind_password@localhost:5432/repomind_ai
JWT_SECRET=replace-with-a-long-random-secret
GITHUB_CLIENT_ID=your-github-oauth-client-id
GITHUB_CLIENT_SECRET=your-github-oauth-client-secret
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
ACCESS_TOKEN_EXPIRE_MINUTES=10080
GOOGLE_API_KEY=your-google-gemini-api-key
GEMINI_EMBEDDING_MODEL=models/text-embedding-004
GEMINI_CHAT_MODEL=gemini-1.5-flash
EMBEDDING_DIMENSION=768
```

## Database

```bash
createdb repomind_ai
psql postgres
```

```sql
CREATE USER repomind_user WITH PASSWORD 'repomind_password';
GRANT ALL PRIVILEGES ON DATABASE repomind_ai TO repomind_user;
\c repomind_ai
GRANT ALL ON SCHEMA public TO repomind_user;
```

Install pgvector on macOS:

```bash
brew install postgresql@16 pgvector
brew services start postgresql@16
```

The migration enables the extension with:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## Migrations

```bash
alembic upgrade head
```

Create future migrations with:

```bash
alembic revision --autogenerate -m "describe change"
```

## Run

```bash
uvicorn app.main:app --reload
```

API health check:

```bash
curl http://localhost:8000/health
```

## Repository Indexing

Index a synced repository:

```bash
curl -X POST http://localhost:8000/repositories/1/index \
  -H "Authorization: Bearer YOUR_JWT"
```

Response:

```json
{
  "files_processed": 120,
  "status": "success"
}
```

Check index status:

```bash
curl http://localhost:8000/repositories/1/index-status \
  -H "Authorization: Bearer YOUR_JWT"
```

Response:

```json
{
  "repository_id": 1,
  "files": 125,
  "chunks": 980,
  "indexed": true
}
```

The indexer clones with the user's stored GitHub access token, reads supported code files, stores `CodeFile` rows, chunks content with LangChain `RecursiveCharacterTextSplitter`, generates Gemini embeddings, stores vectors in `CodeChunk.embedding`, and cleans up the temporary clone directory.

## RAG Chat

Ask a question using indexed repository context:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer YOUR_JWT" \
  -H "Content-Type: application/json" \
  -d '{"repository_id":1,"question":"How does authentication work?"}'
```

Response:

```json
{
  "answer": "...",
  "sources": ["backend/app/routers/auth.py"],
  "session_id": 1
}
```

Create a chat session:

```bash
curl -X POST http://localhost:8000/chat/session \
  -H "Authorization: Bearer YOUR_JWT" \
  -H "Content-Type: application/json" \
  -d '{"repository_id":1,"title":"Architecture questions"}'
```

Read chat history:

```bash
curl http://localhost:8000/chat/session/1 \
  -H "Authorization: Bearer YOUR_JWT"
```

The chat service embeds the user question, retrieves the top 5 chunks for the selected repository with pgvector cosine distance, builds a Gemini prompt with file paths and code context, and stores the user/assistant messages.
