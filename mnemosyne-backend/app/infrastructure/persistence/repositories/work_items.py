"""IssuePort and PullRequestPort adapters."""

from uuid import UUID

from sqlalchemy import select

from app.domain.entities.issue import Issue
from app.domain.entities.pull_request import PullRequest
from app.infrastructure.persistence.mappers import (
    issue_to_entity,
    issue_update_row,
    pr_to_entity,
    pr_update_row,
)
from app.infrastructure.persistence.models import IssueRow, PullRequestRow
from app.infrastructure.persistence.repositories.base import PostgresRepositoryBase


class PostgresIssueRepository(PostgresRepositoryBase):
    async def save_many(self, issues: list[Issue]) -> None:
        async with self._session_factory() as session, session.begin():
            for issue in issues:
                row = await session.scalar(
                    select(IssueRow).where(
                        IssueRow.repository_id == issue.repository_id,
                        IssueRow.number == issue.number,
                    )
                )
                if row is None:
                    row = IssueRow(id=issue.id)
                    session.add(row)
                else:
                    issue.id = row.id
                issue_update_row(row, issue)

    async def get_by_number(self, repository_id: UUID, number: int) -> Issue | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(IssueRow).where(
                    IssueRow.repository_id == repository_id, IssueRow.number == number
                )
            )
            return issue_to_entity(row) if row else None

    async def list_by_repository(
        self, repository_id: UUID, *, state: str | None = None, label: str | None = None
    ) -> list[Issue]:
        async with self._session_factory() as session:
            stmt = (
                select(IssueRow)
                .where(IssueRow.repository_id == repository_id)
                .order_by(IssueRow.number.desc())
            )
            if state:
                stmt = stmt.where(IssueRow.state == state)
            rows = await session.scalars(stmt)
            issues = [issue_to_entity(r) for r in rows]
        if label:
            issues = [i for i in issues if label in i.labels]
        return issues


class PostgresPullRequestRepository(PostgresRepositoryBase):
    async def save_many(self, pull_requests: list[PullRequest]) -> None:
        async with self._session_factory() as session, session.begin():
            for pr in pull_requests:
                row = await session.scalar(
                    select(PullRequestRow).where(
                        PullRequestRow.repository_id == pr.repository_id,
                        PullRequestRow.number == pr.number,
                    )
                )
                if row is None:
                    row = PullRequestRow(id=pr.id)
                    session.add(row)
                else:
                    pr.id = row.id
                pr_update_row(row, pr)

    async def get_by_number(self, repository_id: UUID, number: int) -> PullRequest | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(PullRequestRow).where(
                    PullRequestRow.repository_id == repository_id,
                    PullRequestRow.number == number,
                )
            )
            return pr_to_entity(row) if row else None

    async def list_by_repository(
        self, repository_id: UUID, *, state: str | None = None, author: str | None = None
    ) -> list[PullRequest]:
        async with self._session_factory() as session:
            stmt = (
                select(PullRequestRow)
                .where(PullRequestRow.repository_id == repository_id)
                .order_by(PullRequestRow.number.desc())
            )
            if state:
                stmt = stmt.where(PullRequestRow.state == state)
            if author:
                stmt = stmt.where(PullRequestRow.author == author)
            rows = await session.scalars(stmt)
            return [pr_to_entity(r) for r in rows]
