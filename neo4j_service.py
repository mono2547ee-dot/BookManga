from __future__ import annotations

from typing import Any

import streamlit as st
from neo4j import GraphDatabase, RoutingControl


# ============================================================
# Neo4j Configuration
# ============================================================

def _config() -> tuple[str, str, str, str]:
    """
    อ่านค่าการเชื่อมต่อ Neo4j จาก Streamlit Secrets

    ตัวอย่างไฟล์ .streamlit/secrets.toml

    [neo4j]
    uri = "neo4j+s://f7676f9c.databases.neo4j.io"
    username = "f7676f9c"
    password = "ThfWy64phy4_rMjelXRAvIIoFlgZNXzNyJL5NV7c0hM"
    database = "f7676f9c"
    """

    cfg = st.secrets["neo4j"]

    return (
        cfg["uri"],
        cfg["username"],
        cfg["password"],
        cfg.get("database", "5c11df82"),
    )


# ============================================================
# Neo4j Driver
# ============================================================

@st.cache_resource(show_spinner=False)
def get_driver():
    """
    สร้าง Neo4j Driver
    และตรวจสอบการเชื่อมต่อ
    """

    uri, username, password, _ = _config()

    driver = GraphDatabase.driver(
        uri,
        auth=(username, password),
    )

    driver.verify_connectivity()

    return driver


# ============================================================
# Query
# ============================================================

def query(
    cypher: str,
    parameters: dict[str, Any] | None = None,
    *,
    write: bool = False,
) -> list[dict[str, Any]]:
    """
    ใช้สำหรับรัน Cypher Query กับ Neo4j

    write=False
        ใช้สำหรับอ่านข้อมูล

    write=True
        ใช้สำหรับ CREATE / MERGE / DELETE / SET
    """

    _, _, _, database = _config()

    records, _, _ = get_driver().execute_query(
        cypher,
        parameters_=parameters or {},
        database_=database,
        routing_=(
            RoutingControl.WRITE
            if write
            else RoutingControl.READ
        ),
    )

    return [
        record.data()
        for record in records
    ]


# ============================================================
# Test Connection
# ============================================================

def ping() -> bool:
    """
    ตรวจสอบว่าเชื่อมต่อ Neo4j ได้หรือไม่
    """

    try:
        rows = query(
            "RETURN 1 AS ok"
        )

        return bool(
            rows and rows[0]["ok"] == 1
        )

    except Exception:
        return False


# ============================================================
# Create Schema
# ============================================================

def create_schema() -> None:
    """
    สร้าง Constraint สำหรับ User และ Manga
    """

    statements = [

        # User ID ต้องไม่ซ้ำ
        """
        CREATE CONSTRAINT user_id_unique IF NOT EXISTS
        FOR (u:User)
        REQUIRE u.user_id IS UNIQUE
        """,

        # Manga ID ต้องไม่ซ้ำ
        """
        CREATE CONSTRAINT manga_id_unique IF NOT EXISTS
        FOR (m:Manga)
        REQUIRE m.manga_id IS UNIQUE
        """,
    ]

    for statement in statements:
        query(
            statement,
            write=True,
        )


# ============================================================
# Seed Demo Data
# ============================================================

def seed_demo_data() -> None:
    """
    สร้างข้อมูลตัวอย่างสำหรับระบบ Manga Recommendation

    Node:
        User
        Manga

    Relationship:
        LIKES

    U011 ถูกตั้งใจให้ไม่มี LIKES
    เพื่อใช้ทดสอบระบบ Cold Start
    """

    # สร้าง Constraint ก่อน
    create_schema()

    # --------------------------------------------------------
    # Users
    # --------------------------------------------------------

    users = [

        {
            "user_id": "U001",
            "name": "Sompong",
        },

        {
            "user_id": "U002",
            "name": "Siriporn",
        },

        {
            "user_id": "U003",
            "name": "Niran",
        },

        {
            "user_id": "U004",
            "name": "Malee",
        },

        {
            "user_id": "U005",
            "name": "Chaiwat",
        },

        {
            "user_id": "U006",
            "name": "Kanya",
        },

        {
            "user_id": "U007",
            "name": "Anan",
        },

        {
            "user_id": "U008",
            "name": "Somying",
        },

        {
            "user_id": "U009",
            "name": "Prasit",
        },

        {
            "user_id": "U010",
            "name": "Nattaya",
        },

        # User ใหม่
        # ไม่มี LIKES
        {
            "user_id": "U011",
            "name": "New User",
        },
    ]

    query(
        """
        UNWIND $rows AS row

        MERGE (
            u:User {
                user_id: row.user_id
            }
        )

        SET
            u.name = row.name
        """,

        {
            "rows": users,
        },

        write=True,
    )

    # --------------------------------------------------------
    # Manga
    # --------------------------------------------------------

    mangas = [

        {
            "manga_id": "M001",
            "title": "Naruto",
        },

        {
            "manga_id": "M002",
            "title": "One Piece",
        },

        {
            "manga_id": "M003",
            "title": "Attack on Titan",
        },

        {
            "manga_id": "M004",
            "title": "Demon Slayer",
        },

        {
            "manga_id": "M005",
            "title": "Death Note",
        },

        {
            "manga_id": "M006",
            "title": "My Hero Academia",
        },

        {
            "manga_id": "M007",
            "title": "Jujutsu Kaisen",
        },

        {
            "manga_id": "M008",
            "title": "Fullmetal Alchemist",
        },

        {
            "manga_id": "M009",
            "title": "Spy x Family",
        },

        {
            "manga_id": "M010",
            "title": "Chainsaw Man",
        },
    ]

    query(
        """
        UNWIND $rows AS row

        MERGE (
            m:Manga {
                manga_id: row.manga_id
            }
        )

        SET
            m.title = row.title
        """,

        {
            "rows": mangas,
        },

        write=True,
    )

    # --------------------------------------------------------
    # LIKES
    # --------------------------------------------------------

    likes = [

        ["U001", "M001"],
        ["U001", "M002"],

        ["U002", "M009"],
        ["U002", "M004"],

        ["U003", "M001"],
        ["U003", "M002"],
        ["U003", "M007"],

        ["U004", "M009"],
        ["U004", "M004"],
        ["U004", "M006"],

        ["U005", "M005"],
        ["U005", "M003"],

        ["U006", "M005"],
        ["U006", "M003"],
        ["U006", "M008"],

        ["U007", "M001"],
        ["U007", "M006"],

        ["U008", "M007"],
        ["U008", "M010"],

        ["U009", "M005"],
        ["U009", "M010"],

        ["U010", "M002"],
        ["U010", "M008"],
    ]

    query(
        """
        UNWIND $rows AS row

        MATCH
            (u:User {
                user_id: row[0]
            }),

            (m:Manga {
                manga_id: row[1]
            })

        MERGE
            (u)-[:LIKES]->(m)
        """,

        {
            "rows": likes,
        },

        write=True,
    )


# ============================================================
# Get Users
# ============================================================

def get_users() -> list[dict[str, Any]]:
    """
    ดึงข้อมูล User ทั้งหมด
    """

    return query(
        """
        MATCH (u:User)

        RETURN
            u.user_id AS user_id,
            u.name AS name

        ORDER BY
            u.user_id
        """
    )


# ============================================================
# Get User
# ============================================================

def get_user(
    user_id: str,
) -> dict[str, Any] | None:
    """
    ดึงข้อมูล User ตาม user_id
    """

    rows = query(
        """
        MATCH (
            u:User {
                user_id: $user_id
            }
        )

        RETURN
            u.user_id AS user_id,
            u.name AS name
        """,

        {
            "user_id": user_id,
        },
    )

    if rows:
        return rows[0]

    return None


# ============================================================
# Get Manga
# ============================================================

def get_mangas() -> list[dict[str, Any]]:
    """
    ดึง Manga ทั้งหมด
    """

    return query(
        """
        MATCH (m:Manga)

        RETURN
            m.manga_id AS manga_id,
            m.title AS title

        ORDER BY
            title
        """
    )


# Alias
list_manga = get_mangas


# ============================================================
# Get Liked Manga
# ============================================================

def get_liked_mangas(
    user_id: str,
) -> list[dict[str, Any]]:
    """
    ดึง Manga ที่ User กด Like
    """

    return query(
        """
        MATCH
            (u:User {
                user_id: $user_id
            })
            -[:LIKES]->(m:Manga)

        RETURN
            m.manga_id AS manga_id,
            m.title AS title

        ORDER BY
            title
        """,

        {
            "user_id": user_id,
        },
    )


# ============================================================
# Add Like
# ============================================================

def add_like(
    user_id: str,
    manga_id: str,
) -> None:
    """
    เพิ่มความสัมพันธ์

    (User)-[:LIKES]->(Manga)
    """

    query(
        """
        MATCH
            (u:User {
                user_id: $user_id
            }),

            (m:Manga {
                manga_id: $manga_id
            })

        MERGE
            (u)-[:LIKES]->(m)
        """,

        {
            "user_id": user_id,
            "manga_id": manga_id,
        },

        write=True,
    )


# Alias
record_like = add_like


# ============================================================
# Recommendation จาก Similar User
# ============================================================

def recommend_by_similar_user(
    user_id: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    ระบบแนะนำจาก User ที่มีความชอบคล้ายกัน

    ตัวอย่าง:

    User A
       |
      LIKES
       |
     Manga A
       |
      LIKES
       |
    User B
       |
      LIKES
       |
     Manga B

    ถ้า User A ยังไม่ได้ชอบ Manga B
    ระบบจะแนะนำ Manga B ให้ User A
    """

    return query(
        """
        MATCH
            (me:User {
                user_id: $user_id
            })
            -[:LIKES]->(liked:Manga)
            <-[:LIKES]-(similar:User)
            -[:LIKES]->(recommend:Manga)

        WHERE
            similar <> me

            AND NOT EXISTS {
                MATCH
                    (me)-[:LIKES]->(recommend)
            }

        WITH
            recommend,
            count(
                DISTINCT similar
            ) AS score

        RETURN
            recommend.manga_id AS manga_id,
            recommend.title AS title,
            score,
            "similar_user" AS type

        ORDER BY
            score DESC,
            title

        LIMIT $limit
        """,

        {
            "user_id": user_id,
            "limit": int(limit),
        },
    )


# ============================================================
# Popular Manga
# ============================================================

def recommend_popular(
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    แนะนำ Manga ยอดนิยม

    ใช้สำหรับ User ที่ยังไม่มี LIKES
    """

    return query(
        """
        MATCH (m:Manga)

        OPTIONAL MATCH
            (u:User)-[:LIKES]->(m)

        WITH
            m,
            count(u) AS score

        RETURN
            m.manga_id AS manga_id,
            m.title AS title,
            score,
            "popular" AS type

        ORDER BY
            score DESC,
            title

        LIMIT $limit
        """,

        {
            "limit": int(limit),
        },
    )


# ============================================================
# Main Recommendation
# ============================================================

def recommend_mangas(
    user_id: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    ระบบ Recommendation หลัก

    กรณีที่ 1:
        User มี LIKES
        -> Similar User

    กรณีที่ 2:
        User ไม่มี LIKES
        -> Popular Manga

    กรณีที่ 3:
        User มี LIKES
        แต่ไม่มี Similar User
        -> Popular Manga
    """

    # ตรวจสอบว่า User ชอบ Manga อะไรบ้าง
    liked = get_liked_mangas(
        user_id
    )

    # --------------------------------------------------------
    # Cold Start
    # --------------------------------------------------------

    if not liked:

        return recommend_popular(
            limit
        )

    # --------------------------------------------------------
    # Similar User
    # --------------------------------------------------------

    recommendations = recommend_by_similar_user(
        user_id,
        limit,
    )

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    if recommendations:

        return recommendations

    return recommend_popular(
        limit
    )


# Alias
recommend_manga = recommend_mangas


# ============================================================
# Create RECOMMENDS Relationship
# ============================================================

def create_recommend_relationships(
    user_id: str | None = None,
    limit: int = 5,
) -> int:
    """
    สร้าง Relationship:

    (User)-[:RECOMMENDS]->(Manga)

    พร้อมข้อมูล:

    score
    type

    ถ้า user_id ไม่ระบุ
    จะสร้าง Recommendation ให้ทุก User
    """

    # --------------------------------------------------------
    # User เดียว
    # --------------------------------------------------------

    if user_id:

        clear_recommend_relationships(
            user_id
        )

        target_users = [
            {
                "user_id": user_id
            }
        ]

    # --------------------------------------------------------
    # ทุก User
    # --------------------------------------------------------

    else:

        clear_recommend_relationships()

        target_users = get_users()

    created = 0

    # --------------------------------------------------------
    # สร้าง Recommendation
    # --------------------------------------------------------

    for user in target_users:

        uid = user["user_id"]

        recommendations = recommend_mangas(
            uid,
            limit,
        )

        for manga in recommendations:

            query(
                """
                MATCH
                    (u:User {
                        user_id: $user_id
                    }),

                    (m:Manga {
                        manga_id: $manga_id
                    })

                MERGE
                    (u)-[r:RECOMMENDS]->(m)

                SET
                    r.score = $score,
                    r.type = $type
                """,

                {
                    "user_id": uid,
                    "manga_id": manga["manga_id"],
                    "score": manga["score"],
                    "type": manga["type"],
                },

                write=True,
            )

            created += 1

    return created


# Alias
create_recommendations = create_recommend_relationships


# ============================================================
# Get RECOMMENDS
# ============================================================

def get_recommends(
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    ดึง Recommendation ที่สร้างไว้ใน Graph
    """

    # --------------------------------------------------------
    # User เดียว
    # --------------------------------------------------------

    if user_id:

        return query(
            """
            MATCH
                (u:User {
                    user_id: $user_id
                })
                -[r:RECOMMENDS]->(m:Manga)

            RETURN
                u.user_id AS user_id,
                u.name AS user,

                m.manga_id AS manga_id,
                m.title AS title,

                r.score AS score,
                r.type AS type

            ORDER BY
                score DESC,
                title
            """,

            {
                "user_id": user_id,
            },
        )

    # --------------------------------------------------------
    # ทุก User
    # --------------------------------------------------------

    return query(
        """
        MATCH
            (u:User)
            -[r:RECOMMENDS]->(m:Manga)

        RETURN
            u.user_id AS user_id,
            u.name AS user,

            m.manga_id AS manga_id,
            m.title AS title,

            r.score AS score,
            r.type AS type

        ORDER BY
            user_id,
            score DESC,
            title
        """
    )


# ============================================================
# Search Manga
# ============================================================

def search_mangas(
    keyword: str = "",
) -> list[dict[str, Any]]:
    """
    ค้นหา Manga จากชื่อ
    """

    return query(
        """
        MATCH (m:Manga)

        WHERE
            $keyword = ""
            OR toLower(m.title)
            CONTAINS toLower($keyword)

        OPTIONAL MATCH
            (u:User)-[:LIKES]->(m)

        RETURN
            m.manga_id AS manga_id,
            m.title AS title,
            count(u) AS likes

        ORDER BY
            likes DESC,
            title
        """,

        {
            "keyword": keyword.strip(),
        },
    )


# Alias
search_manga = search_mangas


# ============================================================
# Dashboard Metrics
# ============================================================

def get_dashboard_metrics() -> dict[str, int]:
    """
    ดึงข้อมูลสำหรับ Dashboard
    """

    rows = query(
        """
        OPTIONAL MATCH (u:User)

        WITH
            count(u) AS users

        OPTIONAL MATCH (m:Manga)

        WITH
            users,
            count(m) AS mangas

        OPTIONAL MATCH ()-[l:LIKES]->()

        WITH
            users,
            mangas,
            count(l) AS likes

        OPTIONAL MATCH ()-[r:RECOMMENDS]->()

        RETURN
            users,
            mangas,
            likes,
            count(r) AS recommends
        """
    )

    if rows:

        return rows[0]

    return {
        "users": 0,
        "mangas": 0,
        "likes": 0,
        "recommends": 0,
    }


# ============================================================
# Graph Explorer
# ============================================================

def graph_neighborhood(
    user_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    ดึง Graph สำหรับแสดงใน Streamlit

    Relationship ที่แสดง:

    LIKES
    RECOMMENDS
    """

    # --------------------------------------------------------
    # Graph ของ User คนเดียว
    # --------------------------------------------------------

    if user_id:

        return query(
            """
            MATCH
                (u:User {
                    user_id: $user_id
                })
                -[r:LIKES|RECOMMENDS]->(m:Manga)

            RETURN
                elementId(u) AS source_id,
                "User" AS source_label,
                u.name AS source_name,

                type(r) AS relationship,

                elementId(m) AS target_id,
                "Manga" AS target_label,
                m.title AS target_name

            LIMIT $limit
            """,

            {
                "user_id": user_id,
                "limit": int(limit),
            },
        )

    # --------------------------------------------------------
    # Graph ทั้งระบบ
    # --------------------------------------------------------

    return query(
        """
        MATCH
            (u:User)
            -[r:LIKES|RECOMMENDS]->(m:Manga)

        RETURN
            elementId(u) AS source_id,
            "User" AS source_label,
            u.name AS source_name,

            type(r) AS relationship,

            elementId(m) AS target_id,
            "Manga" AS target_label,
            m.title AS target_name

        LIMIT $limit
        """,

        {
            "limit": int(limit),
        },
    )


# ============================================================
# Clear RECOMMENDS
# ============================================================

def clear_recommend_relationships(
    user_id: str | None = None,
) -> None:
    """
    ลบเฉพาะ RECOMMENDS

    ไม่ลบ LIKES
    """

    # --------------------------------------------------------
    # ลบของ User คนเดียว
    # --------------------------------------------------------

    if user_id:

        query(
            """
            MATCH
                (u:User {
                    user_id: $user_id
                })
                -[r:RECOMMENDS]->()

            DELETE r
            """,

            {
                "user_id": user_id,
            },

            write=True,
        )

    # --------------------------------------------------------
    # ลบทั้งหมด
    # --------------------------------------------------------

    else:

        query(
            """
            MATCH
                ()-[r:RECOMMENDS]->()

            DELETE r
            """,

            write=True,
        )