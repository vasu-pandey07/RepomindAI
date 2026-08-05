export type User = {
  id: number;
  github_id: number;
  username: string;
  email: string | null;
  avatar_url: string | null;
  created_at: string;
};

export type Repository = {
  id: number;
  github_repo_id: number;
  name: string;
  full_name: string;
  language: string | null;
  stars: number;
  forks: number;
  description: string | null;
  owner_id: number;
  created_at: string;
};

export type RepositoryIndexStatus = {
  repository_id: number;
  files: number;
  chunks: number;
  indexed: boolean;
};


export type ChatResponse = {
  answer: string;
  sources: string[];
  session_id: number;
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
};

export interface PRReviewRequest {
  repository_id: number;
  changed_files: string[];
}

export interface PRReviewResponse {
  review: string;
  issues_found: number;
}

export interface TestGenerationRequest {
  repository_id: number;
  file_path: string;
}

export interface TestGenerationResponse {
  tests: string;
}

export interface DocumentationResponse {
  documentation: string;
}

