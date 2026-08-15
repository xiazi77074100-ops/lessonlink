"""Development seed data (要件.md 38節).

Creates one organization, one admin user, 20 children, 15 parents
(with parent_children bindings), and 5 upcoming events with attendance
rows for demo/manual-testing purposes.

Usage:
    python -m app.scripts.seed
"""

import asyncio
import random
from datetime import UTC, date, datetime, timedelta

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models import AdminUser, Attendance, Child, Event, Organization, Parent, ParentChild

LAST_NAMES = [
    "田中", "佐藤", "鈴木", "高橋", "渡辺",
    "伊藤", "山本", "中村", "小林", "加藤",
]
BOY_FIRST_NAMES = ["太郎", "一郎", "次郎", "健太", "翔太", "大輔", "拓也", "蓮", "陽翔", "颯太"]
GIRL_FIRST_NAMES = ["花子", "美咲", "さくら", "陽菜", "結衣", "葵", "凛", "愛", "楓", "杏"]

ATTENDANCE_WEIGHTS = {
    "ATTENDING": 0.65,
    "ABSENT": 0.13,
    "LATE": 0.05,
    "NO_RESPONSE": 0.17,
}


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        organization = Organization(
            name="○○サッカークラブ",
            organization_type="サッカー",
            address="東京都○○区○○1-2-3",
            phone="03-1234-5678",
            email="contact@example.com",
        )
        session.add(organization)
        await session.flush()

        admin = AdminUser(
            organization_id=organization.id,
            email="admin@example.com",
            password_hash=hash_password("password123"),
            display_name="管理者 太郎",
            role="OWNER",
        )
        session.add(admin)

        grades = ["小1", "小2", "小3", "小4", "小5", "小6"]
        children: list[Child] = []
        for i in range(20):
            last = LAST_NAMES[i % len(LAST_NAMES)]
            is_boy = i % 2 == 0
            first = (BOY_FIRST_NAMES if is_boy else GIRL_FIRST_NAMES)[i % 10]
            grade = grades[i % len(grades)]
            birth_year = 2026 - int(grade[1]) - 6
            child = Child(
                organization_id=organization.id,
                first_name=first,
                last_name=last,
                first_name_kana=first,
                last_name_kana=last,
                birth_date=date(birth_year, 4, 1) + timedelta(days=i),
                grade=grade,
                status="ACTIVE",
            )
            children.append(child)
        session.add_all(children)
        await session.flush()

        parents: list[Parent] = []
        for i in range(15):
            last = LAST_NAMES[i % len(LAST_NAMES)]
            parent = Parent(
                organization_id=organization.id,
                line_user_id=f"dev-seed-line-user-{i:03d}",
                display_name=f"{last}さん",
                email=f"parent{i:02d}@example.com",
            )
            parents.append(parent)
        session.add_all(parents)
        await session.flush()

        # 10 parents with 1 child, 5 parents with 2 children = 20 children covered
        child_index = 0
        parent_children: list[ParentChild] = []
        for i, parent in enumerate(parents):
            num_children = 2 if i >= 10 else 1
            for _ in range(num_children):
                if child_index >= len(children):
                    break
                parent_children.append(
                    ParentChild(
                        organization_id=organization.id,
                        parent_id=parent.id,
                        child_id=children[child_index].id,
                        verified_at=datetime.now(UTC),
                    )
                )
                child_index += 1
        session.add_all(parent_children)

        events: list[Event] = []
        now = datetime.now(UTC)
        for week in range(1, 6):
            start = (now + timedelta(days=7 * week)).replace(
                hour=5, minute=0, second=0, microsecond=0  # 14:00 JST
            )
            event = Event(
                organization_id=organization.id,
                title=f"第{week}回 練習",
                description="通常練習です。動きやすい服装でお越しください。",
                start_at=start,
                end_at=start + timedelta(hours=2),
                location_name="○○小学校 グラウンド",
                location_address="東京都○○区○○4-5-6",
                status="PUBLISHED",
            )
            events.append(event)
        session.add_all(events)
        await session.flush()

        attendances: list[Attendance] = []
        rng = random.Random(42)
        for event in events:
            for child in children:
                status = rng.choices(
                    list(ATTENDANCE_WEIGHTS.keys()),
                    weights=list(ATTENDANCE_WEIGHTS.values()),
                )[0]
                responded_at = None if status == "NO_RESPONSE" else datetime.now(UTC)
                attendances.append(
                    Attendance(
                        organization_id=organization.id,
                        event_id=event.id,
                        child_id=child.id,
                        status=status,
                        responded_at=responded_at,
                    )
                )
        session.add_all(attendances)

        await session.commit()

        print("Seed complete:")
        print(f"  organization: {organization.name} ({organization.id})")
        print("  admin login : admin@example.com / password123")
        print(f"  children    : {len(children)}")
        print(f"  parents     : {len(parents)}")
        print(f"  events      : {len(events)}")
        print(f"  attendances : {len(attendances)}")


if __name__ == "__main__":
    asyncio.run(seed())
