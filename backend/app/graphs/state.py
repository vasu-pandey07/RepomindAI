from typing import List, TypedDict, Optional


class AgentState(TypedDict):
    repository_id: int
    file_path: Optional[str]
    changed_files: Optional[List[str]]
    context: str
    analysis: str
    result: str
    issues_found: int
    sources: List[str]
