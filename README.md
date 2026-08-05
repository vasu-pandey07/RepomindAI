# RepoMind AI

RepoMind AI is a GitHub-powered code intelligence platform. This release includes GitHub OAuth login, JWT authentication, PostgreSQL persistence, repository sync, repository indexing, code chunking, pgvector storage for Gemini embeddings, and repository-aware RAG chat.

## Project Structure

```text
repomind-ai/
├── backend/
│   ├── alembic/
│   ├── app/
│   │   ├── core/
│   │   ├── db/
│   │   ├── routers/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── dependencies.py
│   │   └── main.py
│   ├── .env.example
│   ├── alembic.ini
│   ├── README.md
│   └── requirements.txt
└── frontend/
    ├── app/
    ├── components/
    ├── lib/
    ├── types/
    ├── .env.example
    └── package.json
```

## PostgreSQL Setup

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

## pgvector Setup On macOS

Install PostgreSQL and pgvector with Homebrew:

```bash
brew install postgresql@16 pgvector
brew services start postgresql@16
```

If PostgreSQL cannot find the extension, link pgvector into the active PostgreSQL installation:

```bash
brew link pgvector
```

The Phase 2 migration runs this automatically:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## GitHub OAuth Setup

1. Open GitHub Developer Settings: `Settings > Developer settings > OAuth Apps`.
2. Create a new OAuth App.
3. Set Homepage URL to `http://localhost:3000`.
4. Set Authorization callback URL to `http://localhost:8000/auth/github/callback`.
5. Copy the Client ID and Client Secret into `backend/.env`.

## Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Update `backend/.env`:

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

Run migrations and start the API:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

Useful backend checks:

```bash
curl http://localhost:8000/health
```

## Phase 2 Repository Indexing

The backend now supports:

- `POST /repositories/{repository_id}/index`
- `GET /repositories/{repository_id}/index-status`

Indexing flow:

```text
Repository
↓
Authenticated GitHub clone into a temporary directory
↓
Read supported source files
↓
Store CodeFile rows
↓
Chunk with RecursiveCharacterTextSplitter
↓
Generate Gemini embeddings
↓
Store CodeChunk rows with pgvector embeddings
↓
Remove temporary clone directory
```

Ignored folders:

```text
node_modules, .git, build, dist, .next, venv, .venv
```

Supported files:

```text
.py, .js, .ts, .tsx, .jsx, .java, .cpp, .c, .go, .rs, .md
```

## Frontend Setup

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Update `frontend/.env.local` if your API port differs:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## How To Test

1. Start PostgreSQL.
2. Run backend migrations with `alembic upgrade head`.
3. Start the backend with `uvicorn app.main:app --reload`.
4. Start the frontend with `npm run dev`.
5. Open `http://localhost:3000`.
6. Click `Login with GitHub`.
7. Approve the GitHub OAuth app.
8. Confirm you land on `/dashboard`.
9. Click `Sync repositories`.
10. Confirm repositories appear and refresh without duplicates.
11. Copy the JWT from browser local storage key `repomind_token`.
12. Index a synced repository:

```bash
curl -X POST http://localhost:8000/repositories/1/index \
  -H "Authorization: Bearer YOUR_JWT"
```

13. Check index status:

```bash
curl http://localhost:8000/repositories/1/index-status \
  -H "Authorization: Bearer YOUR_JWT"
```

Expected status response:

```json
{
  "repository_id": 1,
  "files": 125,
  "chunks": 980,
  "indexed": true
}
```

## Implemented Foundation

- FastAPI application with CORS and session middleware.
- PostgreSQL connection through SQLAlchemy.
- Alembic initial migration for users and repositories.
- GitHub OAuth login with Authlib.
- JWT generation and bearer-token authentication.
- Repository sync using the logged-in user's GitHub access token.
- Next.js 15 App Router frontend with Tailwind CSS, Shadcn-style UI primitives, Axios, and React Query.
- CodeFile and CodeChunk database models for repository indexing.
- pgvector extension and vector column migration.
- Temporary authenticated GitHub cloning for indexing.
- LangChain recursive chunking with `chunk_size=1000` and `chunk_overlap=200`.
- Google Gemini embedding generation and vector persistence.

## Phase 3 Repository Chat

The backend now supports:

- `POST /chat`
- `POST /chat/session`
- `GET /chat/session/{session_id}`

RAG flow:

```text
Question
↓
Embed question with Gemini
↓
Search top 5 pgvector code chunks for the selected repository
↓
Build prompt with file paths and retrieved code
↓
Ask Gemini
↓
Return answer and source file paths
```

The model is instructed to answer only from repository context. If the retrieved chunks are insufficient, it must return:

```text
I could not find enough information in this repository.
```

Ask a repository question:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer YOUR_JWT" \
  -H "Content-Type: application/json" \
  -d '{"repository_id":1,"question":"How does authentication work?"}'
```

Expected response:

```json
{
  "answer": "Authentication is handled by...",
  "sources": ["backend/app/routers/auth.py", "frontend/components/LoginButton.tsx"],
  "session_id": 1
}
```

Create a session manually:

```bash
curl -X POST http://localhost:8000/chat/session \
  -H "Authorization: Bearer YOUR_JWT" \
  -H "Content-Type: application/json" \
  -d '{"repository_id":1,"title":"Authentication questions"}'
```

Read session history:

```bash
curl http://localhost:8000/chat/session/1 \
  -H "Authorization: Bearer YOUR_JWT"
```

The dashboard now includes a Repository Chat panel where you can select a synced and indexed repository, ask a question, view the answer, and inspect source file citations.

## Phase Files

- `backend/app/db/models.py`: adds `CodeFile` and `CodeChunk` SQLAlchemy models plus relationships.
- `backend/alembic/versions/202606220001_add_code_indexing_tables.py`: enables pgvector and creates indexing tables.
- `backend/app/services/repository_indexer.py`: clones repositories, reads files, chunks content, embeds chunks, and stores vectors.
- `backend/app/routers/repositories.py`: adds repository indexing and index-status endpoints.
- `backend/app/core/config.py`: adds Gemini embedding configuration.
- `backend/app/schemas/user.py`: adds index response schemas.
- `backend/requirements.txt`: adds pgvector, LangChain, and Gemini embedding packages.
- `backend/alembic/versions/202606220002_add_chat_tables.py`: creates chat session and message tables.
- `backend/app/schemas/chat.py`: defines chat request, response, session, and history schemas.
- `backend/app/services/retriever.py`: embeds questions and retrieves the top 5 repository chunks with pgvector.
- `backend/app/services/rag_service.py`: builds repository-only prompts and calls Gemini for answers.
- `backend/app/routers/chat.py`: exposes chat, session creation, and session history APIs.
- `frontend/components/RepositoryChatPanel.tsx`: adds the ChatGPT-style repository chat UI.
- `frontend/types/index.ts`: adds chat response and message types.
- `frontend/app/dashboard/page.tsx`: renders the chat panel below the repository list.
