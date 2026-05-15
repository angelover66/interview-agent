"""Interview Agent 数据模型（全部使用 dataclass，纯 JSON 序列化）"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime


# ─── 素材库模型 ─────────────────────────────────────────

@dataclass
class ResumeInfo:
    """简历信息"""
    name: str = ""
    title: str = ""
    summary: str = ""
    education: list[dict] = field(default_factory=list)          # [{school, degree, major, year}]
    work_experience: list[dict] = field(default_factory=list)    # [{company, role, period, highlights}]
    skills: list[str] = field(default_factory=list)
    projects_overview: list[str] = field(default_factory=list)


@dataclass
class ProjectInfo:
    """项目信息"""
    name: str = ""
    role: str = ""
    background: str = ""
    problem: str = ""
    solution: str = ""
    my_contribution: str = ""
    results: list[str] = field(default_factory=list)
    metrics: list[dict] = field(default_factory=list)  # [{name, value, description}]
    skills_used: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class JDInfo:
    """岗位描述信息"""
    company: str = ""
    position: str = ""
    responsibilities: list[str] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)
    preferred: list[str] = field(default_factory=list)
    department: str = ""
    industry: str = ""
    salary_range: str = ""


@dataclass
class NoteInfo:
    """用户笔记"""
    title: str = ""
    content: str = ""
    source: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = ""


# ─── 用户画像 ───────────────────────────────────────────

@dataclass
class UserProfile:
    """候选人完整画像（从所有素材合成）"""
    name: str = ""
    target_positions: list[str] = field(default_factory=list)
    current_title: str = ""
    years_of_experience: int = 0
    education: list[dict] = field(default_factory=list)
    core_skills: list[str] = field(default_factory=list)
    career_summary: str = ""
    key_projects: list[dict] = field(default_factory=list)  # [{name, role, metrics}]
    b2b_domain_expertise: list[str] = field(default_factory=list)
    highlight_achievements: list[str] = field(default_factory=list)
    weak_areas: list[str] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ─── 模拟面试模型 ───────────────────────────────────────

@dataclass
class MockQuestion:
    question: str
    type: str = ""          # 行为/估算/产品sense/策略/执行
    difficulty: str = "中"
    expected_framework: str = ""
    hint: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MockAnswer:
    question: str
    answer: str
    score: float = 0.0
    feedback: str = ""
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MockSession:
    company: str = ""
    position: str = ""
    questions: list[MockQuestion] = field(default_factory=list)
    answers: list[MockAnswer] = field(default_factory=list)
    current_q_index: int = 0
    status: str = "进行中"  # 进行中 | 已完成
    summary: str = ""
    overall_score: float = 0.0
    dimension_scores: dict = field(default_factory=dict)
    started_at: str = ""
    ended_at: str = ""

    def to_dict(self) -> dict:
        return {
            "company": self.company,
            "position": self.position,
            "questions": [q.to_dict() for q in self.questions],
            "answers": [a.to_dict() for a in self.answers],
            "current_q_index": self.current_q_index,
            "status": self.status,
            "summary": self.summary,
            "overall_score": self.overall_score,
            "dimension_scores": self.dimension_scores,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }


# ─── 面试追踪模型 ───────────────────────────────────────

@dataclass
class InterviewRecord:
    company: str = ""
    position: str = ""
    interview_date: str = ""
    round: str = "一面"         # 一面/二面/三面/HR面/已offer/已挂
    status: str = "待面试"      # 待面试/已面试/有结果
    experience: str = ""        # 面经
    questions_recalled: list[str] = field(default_factory=list)
    result: str = ""            # 通过/挂/待定/offer
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ─── 搜索模型 ───────────────────────────────────────────

@dataclass
class SearchResult:
    title: str = ""
    url: str = ""
    content: str = ""
    source: str = ""
