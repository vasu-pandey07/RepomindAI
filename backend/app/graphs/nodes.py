import re
from typing import Dict, Any, List
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings, settings
from app.db.models import CodeFile, Repository
from app.graphs.state import AgentState
from app.services.retriever import RepositoryRetriever


class AgentNodes:
    def __init__(self) -> None:
        self._retriever = None
        self._llm = None

    @property
    def retriever(self) -> RepositoryRetriever:
        return RepositoryRetriever()

    @property
    def llm(self):
        current_settings = get_settings()
        if current_settings.groq_api_key:
            return ChatGroq(
                model_name=current_settings.groq_model,
                groq_api_key=current_settings.groq_api_key,
                temperature=0.1,
            )
        if not current_settings.google_api_key:
            raise ValueError("Either GROQ_API_KEY or GOOGLE_API_KEY must be configured before running AI agents.")
        return ChatGoogleGenerativeAI(
            model=current_settings.gemini_chat_model,
            google_api_key=current_settings.google_api_key,
            temperature=0.1,
        )

    def retrieve_context_node(self, state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
        """
        RetrieveContextNode: Gathers source file content and semantic vector chunks
        based on the agent request type.
        """
        db: Session = config.get("configurable", {}).get("db")
        if not db:
            raise ValueError("Database session (db) was not provided in graph configuration.")

        repo_id = state.get("repository_id")
        changed_files = state.get("changed_files")
        file_path = state.get("file_path")

        context_parts = []
        sources = []

        # Case 1: PR Review Agent
        if changed_files is not None:
            for raw_path in changed_files:
                path = raw_path.strip().lstrip("/\\")
                code_file = (
                    db.query(CodeFile)
                    .filter(
                        CodeFile.repository_id == repo_id,
                        (func.lower(CodeFile.file_path) == path.lower()) |
                        (CodeFile.file_path.ilike(f"%{path}"))
                    )
                    .first()
                )
                if code_file:
                    matched_path = code_file.file_path
                    context_parts.append(
                        f"File: {matched_path}\nContent:\n```\n{code_file.content}\n```"
                    )
                    sources.append(matched_path)
                    
                    # Semantically retrieve related chunks for additional context
                    try:
                        chunks = self.retriever.retrieve(db, repo_id, f"functions, security and structure in {matched_path}", limit=3)
                        for chunk in chunks:
                            if chunk.file_path != matched_path:  # Avoid duplicating the same file
                                context_parts.append(
                                    f"Related Context from {chunk.file_path}:\n```\n{chunk.content}\n```"
                                )
                                sources.append(chunk.file_path)
                    except Exception:
                        pass  # Proceed without semantic context if retriever fails
                else:
                    context_parts.append(f"File: {path} (Not found in index or empty/deleted)")

        # Case 2: Test Generation Agent
        elif file_path is not None:
            path = file_path.strip().lstrip("/\\")
            code_file = (
                db.query(CodeFile)
                .filter(
                    CodeFile.repository_id == repo_id,
                    (func.lower(CodeFile.file_path) == path.lower()) |
                    (CodeFile.file_path.ilike(f"%{path}"))
                )
                .first()
            )
            if code_file:
                matched_path = code_file.file_path
                context_parts.append(
                    f"Target File for Test Generation:\nFile: {matched_path}\nContent:\n```\n{code_file.content}\n```"
                )
                sources.append(matched_path)
                
                # Retrieve imports or dependencies in other files
                try:
                    chunks = self.retriever.retrieve(db, repo_id, f"classes, types, functions or helpers imported by {matched_path}", limit=3)
                    for chunk in chunks:
                        if chunk.file_path != matched_path:
                            context_parts.append(
                                f"Related Context from dependency/helper ({chunk.file_path}):\n```\n{chunk.content}\n```"
                            )
                            sources.append(chunk.file_path)
                except Exception:
                    pass  # Proceed without semantic context if retriever fails
            else:
                context_parts.append(f"Error: Target file {path} not found in this repository index.")

        # Case 3: Documentation Agent
        else:
            # Query for main readme file
            readme_files = (
                db.query(CodeFile)
                .filter(
                    CodeFile.repository_id == repo_id,
                    CodeFile.file_path.ilike("%readme%")
                )
                .all()
            )
            for rf in readme_files:
                context_parts.append(
                    f"File: {rf.file_path} (README Content):\n```\n{rf.content}\n```"
                )
                sources.append(rf.file_path)

            # Query database for main config or route file names
            key_files = (
                db.query(CodeFile)
                .filter(
                    CodeFile.repository_id == repo_id,
                    CodeFile.file_path.ilike("%main.py") |
                    CodeFile.file_path.ilike("%app.py") |
                    CodeFile.file_path.ilike("%main.ts") |
                    CodeFile.file_path.ilike("%config%")
                )
                .limit(5)
                .all()
            )
            for kf in key_files:
                if kf.file_path not in sources:
                    context_parts.append(
                        f"Key Entry Point File: {kf.file_path}\nContent Snippet:\n```\n{kf.content[:2000]}\n```"
                    )
                    sources.append(kf.file_path)

            # Retrieve overall architectural context using pgvector
            arch_queries = [
                "project architecture, framework, and entry point setup",
                "database models, schemas, and ORM configuration",
                "API routes, endpoints, controller logic and handlers",
                "authentication, OAuth, middleware, and JWT security keys"
            ]
            for query in arch_queries:
                try:
                    chunks = self.retriever.retrieve(db, repo_id, query, limit=2)
                    for chunk in chunks:
                        if chunk.file_path not in sources:
                            context_parts.append(
                                f"Architectural Snippet ({chunk.file_path}):\n```\n{chunk.content}\n```"
                            )
                            sources.append(chunk.file_path)
                except Exception:
                    pass  # Proceed without semantic context if retriever fails

        # Deduplicate sources
        dedup_sources = list(dict.fromkeys(sources))

        return {
            "context": "\n\n".join(context_parts),
            "sources": dedup_sources
        }

    def analyze_code_node(self, state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
        """
        AnalyzeCodeNode: Calls Gemini to perform initial code quality analysis,
        review changes, or plan documentation structures.
        """
        context = state.get("context")
        changed_files = state.get("changed_files")
        file_path = state.get("file_path")

        # Define prompts based on Agent Type
        if changed_files is not None:
            # PR Review Analysis Prompt
            prompt = f"""You are a senior code quality and security auditor.
Analyze the following code files context that are part of a Pull Request (PR) change.
Identify:
1. Bugs, logical errors, edge case failures, or race conditions.
2. Security risks (such as insecure inputs, auth bypasses, secrets exposure).
3. Code smells (bloated functions, duplication, bad naming, formatting).
4. Concrete suggestions for optimization or clean code refactoring.

Repository context:
{context}

Provide a structured analysis outlining your findings for each area. Be concise and precise.
"""
        elif file_path is not None:
            # Test Generation Analysis Prompt
            prompt = f"""You are a principal QA automation engineer.
Analyze the target file and its dependencies context to design a robust test suite.
Determine:
1. What logic (functions, routes, classes) needs testing.
2. Happy path test cases.
3. Edge cases (empty inputs, nulls, division by zero, invalid roles).
4. Failure states (network drops, DB integrity exceptions, invalid tokens).

Target Code Context:
{context}

Provide a structured list of test plan steps and edge case strategies.
"""
        else:
            # Documentation Analysis Prompt
            prompt = f"""You are a lead technical writer.
Analyze the repository context code snippets and architecture.
Deduce:
1. The project overview (what is this codebase building).
2. The core system architecture (frameworks, tech stack, data flows).
3. The routing layout and APIs.
4. Database tables and schema layout.
5. Setup, configurations, and running instructions.

Repository context:
{context}

Create a technical index planning the document generation structure.
"""

        response = self.llm.invoke(prompt)
        return {"analysis": str(response.content).strip()}

    def generate_response_node(self, state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
        """
        GenerateResponseNode: Uses analysis and context to construct the final
        production-grade output.
        """
        context = state.get("context")
        analysis = state.get("analysis")
        changed_files = state.get("changed_files")
        file_path = state.get("file_path")

        if changed_files is not None:
            # PR Review Output
            prompt = f"""You are an automated PR reviewer like CodeRabbit.
Using the following code context and your initial analysis, write a professional, production-ready markdown PR review report.

Outline:
1. Summary of Changes
2. Findings Table (showing Category: Bug/Security/Smell, File Name, Description, Severity: High/Medium/Low)
3. Detailed Explanations & Suggestions
4. Code Refactoring diff recommendations.

At the very bottom of the document, you MUST include a single line in this exact format:
`ISSUES_FOUND: <count>` (where `<count>` is the total number of distinct bugs, security risks, or code smells found, as an integer. If none, write `ISSUES_FOUND: 0`).

Context:
{context}

Analysis:
{analysis}

Markdown PR Review:
"""
            response = self.llm.invoke(prompt)
            result_content = str(response.content).strip()

            # Parse issue count
            issues_found = 0
            match = re.search(r"ISSUES_FOUND:\s*(\d+)", result_content, re.IGNORECASE)
            if match:
                issues_found = int(match.group(1))
            else:
                # Fallback: count list items or issues mentioned
                issues_found = len(re.findall(r"(?:bug|security|smell|issue|severity)", result_content, re.IGNORECASE)) // 3
                if issues_found < 1:
                    issues_found = 1

            return {
                "result": result_content,
                "issues_found": issues_found
            }

        elif file_path is not None:
            # Test Generation Output
            prompt = f"""You are a test developer.
Using the analysis and context, write COMPLETE unit tests for the target file.
Do not leave placeholders or TODOs.
Write clean, compilable, and idiomatic code (e.g. pytest for Python, Jest/Vitest for TS/JS).
Include test cases for happy path, edge cases, and failure handling.

Context:
{context}

Analysis:
{analysis}

Write the full test file code inside a single code block:
"""
            response = self.llm.invoke(prompt)
            result_content = str(response.content).strip()
            return {"result": result_content}

        else:
            # Documentation Output
            prompt = f"""You are a senior technical writer.
Produce a comprehensive, publication-quality Markdown documentation file for the repository.
Using the context and architecture analysis, populate these sections thoroughly:

# Repository Documentation

## Project Overview
## Architecture Overview
## Folder Structure
## API Documentation
## Authentication Flow
## Database Design
## Setup & Installation Instructions

Use clean GFM tables and formatting. Do not use placeholders.

Context:
{context}

Analysis:
{analysis}

Comprehensive Markdown Documentation:
"""
            response = self.llm.invoke(prompt)
            result_content = str(response.content).strip()
            return {"result": result_content}
