import streamlit as st
import pandas as pd
from neo4j import GraphDatabase


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Manga Recommendation System",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# CSS
# =========================================================

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
    }

    .hero {
        padding: 1.5rem;
        border-radius: 20px;
        background: linear-gradient(
            120deg,
            #111827 0%,
            #312e81 55%,
            #7c3aed 100%
        );
        color: white;
        margin-bottom: 1rem;
    }

    .hero h1 {
        margin: 0;
        font-size: 2.2rem;
    }

    .hero p {
        margin-top: .4rem;
        opacity: .9;
    }

    .manga-card {
        padding: 1rem;
        border: 1px solid rgba(128,128,128,.3);
        border-radius: 16px;
        margin-bottom: .8rem;
    }

    .score {
        display: inline-block;
        padding: .25rem .6rem;
        border-radius: 999px;
        background: #7c3aed;
        color: white;
        font-size: .8rem;
        font-weight: bold;
    }

    .muted {
        opacity: .7;
        font-size: .9rem;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# NEO4J CONNECTION
# =========================================================

@st.cache_resource
def create_driver(uri, username, password):
    """
    สร้าง Neo4j Driver
    """

    driver = GraphDatabase.driver(
        uri,
        auth=(username, password)
    )

    # ตรวจสอบการเชื่อมต่อ
    driver.verify_connectivity()

    return driver


def get_connection():
    """
    อ่านค่าการเชื่อมต่อ Neo4j
    จาก Streamlit Secrets
    """

    try:

        config = st.secrets["neo4j"]

        uri = config["uri"]

        username = config["username"]

        password = config["password"]

        database = config.get(
            "database",
            "308b65ad"
        )

        driver = create_driver(
            uri,
            username,
            password
        )

        return driver, database

    except Exception as e:

        st.error(
            "❌ เชื่อมต่อ Neo4j Aura ไม่สำเร็จ"
        )

        st.markdown(
            """
            ### ตรวจสอบ Streamlit Secrets

            ให้ใส่ข้อมูลในรูปแบบนี้:

            ```toml
            [neo4j]

            uri = "neo4j+s://YOUR_INSTANCE.databases.neo4j.io"

            username = "neo4j"

            password = "YOUR_PASSWORD"

            database = "neo4j"
            ```
            """
        )

        st.warning(
            "ให้ใช้ URI / Username / Password / Database "
            "ที่ได้จาก Neo4j Aura จริง ๆ"
        )

        st.exception(e)

        st.stop()


# สร้าง Connection
driver, DATABASE = get_connection()


# =========================================================
# GENERAL QUERY FUNCTION
# =========================================================

def run_query(
    cypher,
    parameters=None
):
    """
    ฟังก์ชันกลางสำหรับส่ง Cypher ไป Neo4j

    parameters ต้องเป็น Dictionary เช่น:

    {
        "user_id": "U001"
    }
    """

    if parameters is None:
        parameters = {}

    result = driver.execute_query(
        cypher,
        parameters_=parameters,
        database_=DATABASE
    )

    return [
        record.data()
        for record in result.records
    ]


# =========================================================
# CREATE CONSTRAINTS
# =========================================================

def create_constraints():
    """
    สร้าง Constraint สำหรับ User และ Manga
    """

    run_query(
        """
        CREATE CONSTRAINT user_id_unique IF NOT EXISTS
        FOR (u:User)
        REQUIRE u.user_id IS UNIQUE
        """
    )

    run_query(
        """
        CREATE CONSTRAINT manga_id_unique IF NOT EXISTS
        FOR (m:Manga)
        REQUIRE m.manga_id IS UNIQUE
        """
    )


# =========================================================
# USER
# =========================================================

def get_users():
    """
    ดึง User ทั้งหมด
    """

    return run_query(
        """
        MATCH (u:User)

        RETURN
            u.user_id AS user_id,
            u.name AS name

        ORDER BY
            u.user_id
        """
    )


def get_user(user_id):
    """
    ดึงข้อมูล User คนเดียว
    """

    rows = run_query(
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
            "user_id": user_id
        }
    )

    return rows[0] if rows else None


# =========================================================
# MANGA
# =========================================================

def get_mangas():
    """
    ดึง Manga ทั้งหมด
    """

    return run_query(
        """
        MATCH (m:Manga)

        RETURN
            m.manga_id AS manga_id,
            m.title AS title

        ORDER BY
            m.title
        """
    )


# =========================================================
# LIKES
# =========================================================

def get_liked_mangas(user_id):
    """
    ดึง Manga ที่ User กด Like
    """

    return run_query(
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
            "user_id": user_id
        }
    )


def add_like(
    user_id,
    manga_id
):
    """
    สร้างความสัมพันธ์

    (User)-[:LIKES]->(Manga)
    """

    run_query(
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
            "manga_id": manga_id
        }
    )


# =========================================================
# RECOMMENDATION - SIMILAR USER
# =========================================================

def recommend_by_similar_user(
    user_id,
    limit=5
):
    """
    หา Manga จาก User ที่มีความชอบคล้ายกัน

    ตัวอย่าง:

    User A
       |
      LIKES
       |
    Manga 1
       |
      LIKES
       |
    User B
       |
      LIKES
       |
    Manga 2

    ถ้า User A ยังไม่เคย Like Manga 2
    ระบบจะแนะนำ Manga 2
    """

    return run_query(
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
            "limit": int(limit)
        }
    )


# =========================================================
# RECOMMENDATION - POPULAR
# =========================================================

def recommend_popular(
    limit=5
):
    """
    แนะนำ Manga ที่ได้รับความนิยม

    นับจำนวน LIKES ของแต่ละ Manga
    """

    return run_query(
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
            "limit": int(limit)
        }
    )


# =========================================================
# MAIN RECOMMENDATION
# =========================================================

def get_recommendations(
    user_id,
    limit=5
):
    """
    ระบบ Recommendation หลัก

    User มี LIKES
        ↓
    Similar User

    User ไม่มี LIKES
        ↓
    Popular Manga

    ถ้ามี LIKES แต่หา Similar User ไม่ได้
        ↓
    Popular Manga
    """

    liked = get_liked_mangas(
        user_id
    )

    # -----------------------------------------------------
    # USER ใหม่
    # -----------------------------------------------------

    if not liked:

        return (
            recommend_popular(limit),
            "new_user"
        )

    # -----------------------------------------------------
    # USER เดิม
    # -----------------------------------------------------

    rows = recommend_by_similar_user(
        user_id,
        limit
    )

    if rows:

        return (
            rows,
            "similar"
        )

    # -----------------------------------------------------
    # FALLBACK
    # -----------------------------------------------------

    return (
        recommend_popular(limit),
        "popular_fallback"
    )


# =========================================================
# CLEAR RECOMMENDS
# =========================================================

def clear_recommend_relationships(
    user_id=None
):
    """
    ลบเฉพาะ RECOMMENDS

    ไม่ลบ LIKES
    """

    if user_id:

        run_query(
            """
            MATCH
                (u:User {
                    user_id: $user_id
                })
                -[r:RECOMMENDS]->()

            DELETE r
            """,

            {
                "user_id": user_id
            }
        )

    else:

        run_query(
            """
            MATCH
                ()-[r:RECOMMENDS]->()

            DELETE r
            """
        )


# =========================================================
# CREATE RECOMMENDS RELATIONSHIP
# =========================================================

def create_recommend_relationships(
    user_id=None,
    limit=5
):
    """
    สร้าง

    (User)-[:RECOMMENDS]->(Manga)

    พร้อม properties:

    score
    type
    """

    # -----------------------------------------------------
    # User คนเดียว
    # -----------------------------------------------------

    if user_id:

        clear_recommend_relationships(
            user_id
        )

        target_users = [
            {
                "user_id": user_id
            }
        ]

    # -----------------------------------------------------
    # ทุก User
    # -----------------------------------------------------

    else:

        clear_recommend_relationships()

        target_users = get_users()

    created = 0

    # -----------------------------------------------------
    # สร้าง Recommendation
    # -----------------------------------------------------

    for user in target_users:

        uid = user["user_id"]

        rows, mode = get_recommendations(
            uid,
            limit
        )

        for row in rows:

            run_query(
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
                    "manga_id": row["manga_id"],
                    "score": row["score"],
                    "type": row["type"]
                }
            )

            created += 1

    return created


# =========================================================
# GET RECOMMENDS
# =========================================================

def get_recommends(
    user_id=None
):
    """
    ดึง Relationship RECOMMENDS
    """

    if user_id:

        return run_query(
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
                "user_id": user_id
            }
        )

    return run_query(
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


# =========================================================
# SEARCH MANGA
# =========================================================

def search_manga(
    keyword=""
):
    """
    ค้นหา Manga
    """

    return run_query(
        """
        MATCH (m:Manga)

        WHERE
            $keyword = ""

            OR

            toLower(m.title)
            CONTAINS
            toLower($keyword)

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
            "keyword": keyword.strip()
        }
    )


# =========================================================
# GRAPH
# =========================================================

def get_graph(
    user_id=None
):
    """
    ดึง Graph

    Relationship:

    LIKES
    RECOMMENDS
    """

    if user_id:

        return run_query(
            """
            MATCH
                (u:User {
                    user_id: $user_id
                })
                -[r:LIKES|RECOMMENDS]->(m:Manga)

            RETURN
                u.user_id AS source_id,
                u.name AS source_name,

                type(r) AS relationship,

                m.manga_id AS target_id,
                m.title AS target_name

            """,

            {
                "user_id": user_id
            }
        )

    return run_query(
        """
        MATCH
            (u:User)
            -[r:LIKES|RECOMMENDS]->(m:Manga)

        RETURN
            u.user_id AS source_id,
            u.name AS source_name,

            type(r) AS relationship,

            m.manga_id AS target_id,
            m.title AS target_name

        LIMIT 100
        """
    )


# =========================================================
# DASHBOARD METRICS
# =========================================================

def get_metrics():
    """
    นับจำนวน:

    User
    Manga
    LIKES
    RECOMMENDS
    """

    users = run_query(
        """
        MATCH (u:User)

        RETURN count(u) AS count
        """
    )[0]["count"]

    mangas = run_query(
        """
        MATCH (m:Manga)

        RETURN count(m) AS count
        """
    )[0]["count"]

    likes = run_query(
        """
        MATCH ()-[r:LIKES]->()

        RETURN count(r) AS count
        """
    )[0]["count"]

    recommends = run_query(
        """
        MATCH ()-[r:RECOMMENDS]->()

        RETURN count(r) AS count
        """
    )[0]["count"]

    return (
        users,
        mangas,
        likes,
        recommends
    )


# =========================================================
# DEMO DATA
# =========================================================

def create_demo_data():
    """
    สร้างข้อมูลตัวอย่าง

    U011 จะเป็น User ใหม่
    และไม่มี LIKES
    เพื่อทดสอบ Cold Start
    """

    # สร้าง Constraint
    create_constraints()

    # -----------------------------------------------------
    # USERS
    # -----------------------------------------------------

    users = [

        {
            "user_id": "U001",
            "name": "Sompong"
        },

        {
            "user_id": "U002",
            "name": "Siriporn"
        },

        {
            "user_id": "U003",
            "name": "Niran"
        },

        {
            "user_id": "U004",
            "name": "Malee"
        },

        {
            "user_id": "U005",
            "name": "Chaiwat"
        },

        {
            "user_id": "U006",
            "name": "Kanya"
        },

        {
            "user_id": "U007",
            "name": "Anan"
        },

        {
            "user_id": "U008",
            "name": "Somying"
        },

        {
            "user_id": "U009",
            "name": "Prasit"
        },

        {
            "user_id": "U010",
            "name": "Nattaya"
        },

        # User ใหม่
        {
            "user_id": "U011",
            "name": "New User"
        }
    ]

    # -----------------------------------------------------
    # MANGA
    # -----------------------------------------------------

    mangas = [

        {
            "manga_id": "M001",
            "title": "Naruto"
        },

        {
            "manga_id": "M002",
            "title": "One Piece"
        },

        {
            "manga_id": "M003",
            "title": "Attack on Titan"
        },

        {
            "manga_id": "M004",
            "title": "Demon Slayer"
        },

        {
            "manga_id": "M005",
            "title": "Death Note"
        },

        {
            "manga_id": "M006",
            "title": "My Hero Academia"
        },

        {
            "manga_id": "M007",
            "title": "Jujutsu Kaisen"
        },

        {
            "manga_id": "M008",
            "title": "Fullmetal Alchemist"
        },

        {
            "manga_id": "M009",
            "title": "Spy x Family"
        },

        {
            "manga_id": "M010",
            "title": "Chainsaw Man"
        }
    ]

    # -----------------------------------------------------
    # LIKES
    # -----------------------------------------------------

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
        ["U010", "M008"]
    ]

    # -----------------------------------------------------
    # CREATE USERS
    # -----------------------------------------------------

    run_query(
        """
        UNWIND $users AS row

        MERGE (
            u:User {
                user_id: row.user_id
            }
        )

        SET
            u.name = row.name
        """,

        {
            "users": users
        }
    )

    # -----------------------------------------------------
    # CREATE MANGA
    # -----------------------------------------------------

    run_query(
        """
        UNWIND $mangas AS row

        MERGE (
            m:Manga {
                manga_id: row.manga_id
            }
        )

        SET
            m.title = row.title
        """,

        {
            "mangas": mangas
        }
    )

    # -----------------------------------------------------
    # CREATE LIKES
    # -----------------------------------------------------

    run_query(
        """
        UNWIND $likes AS row

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
            "likes": likes
        }
    )


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown(
        "## 📚 MangaGraph"
    )

    st.caption(
        "Neo4j Aura + Streamlit"
    )

    page = st.radio(
        "เมนู",

        [
            "Dashboard",
            "Recommendations",
            "Manga Search",
            "Manage Likes",
            "Graph Explorer",
            "Admin / Setup"
        ]
    )

    st.divider()

    st.caption(
        "Manga Recommendation System"
    )


# =========================================================
# HEADER
# =========================================================

st.markdown(
    """
    <div class="hero">

        <h1>
            📚 Manga Recommendation System
        </h1>

        <p>
            ระบบแนะนำ Manga ด้วย Neo4j Graph Database
        </p>

    </div>
    """,

    unsafe_allow_html=True
)


# =========================================================
# DASHBOARD
# =========================================================

if page == "Dashboard":

    st.subheader(
        "📊 ภาพรวมระบบ"
    )

    (
        users_count,
        manga_count,
        likes_count,
        recommends_count
    ) = get_metrics()

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Users",
        users_count
    )

    c2.metric(
        "Manga",
        manga_count
    )

    c3.metric(
        "LIKES",
        likes_count
    )

    c4.metric(
        "RECOMMENDS",
        recommends_count
    )

    st.divider()

    all_users = get_users()

    if all_users:

        options = {
            f"{u['user_id']} — {u['name']}":
            u["user_id"]

            for u in all_users
        }

        selected = st.selectbox(
            "เลือก User",
            list(options.keys())
        )

        user_id = options[selected]

        left, right = st.columns(2)

        # -------------------------------------------------
        # LIKES
        # -------------------------------------------------

        with left:

            st.markdown(
                "### ❤️ Manga ที่ User ชอบ"
            )

            rows = get_liked_mangas(
                user_id
            )

            if rows:

                st.dataframe(
                    pd.DataFrame(rows),
                    use_container_width=True,
                    hide_index=True
                )

            else:

                st.info(
                    "User นี้ยังไม่มี LIKES"
                )

        # -------------------------------------------------
        # RECOMMENDS
        # -------------------------------------------------

        with right:

            st.markdown(
                "### ✨ Manga ที่ระบบแนะนำ"
            )

            rows = get_recommends(
                user_id
            )

            if rows:

                st.dataframe(
                    pd.DataFrame(rows),
                    use_container_width=True,
                    hide_index=True
                )

            else:

                st.info(
                    "ยังไม่มี RECOMMENDS"
                )


# =========================================================
# RECOMMENDATIONS
# =========================================================

elif page == "Recommendations":

    st.subheader(
        "✨ Manga Recommendation"
    )

    all_users = get_users()

    if not all_users:

        st.warning(
            "ยังไม่มี User"
        )

        st.stop()

    options = {
        f"{u['user_id']} — {u['name']}":
        u["user_id"]

        for u in all_users
    }

    selected = st.selectbox(
        "เลือก User",
        list(options.keys())
    )

    user_id = options[selected]

    limit = st.slider(
        "จำนวน Manga ที่แนะนำ",
        3,
        12,
        5
    )

    rows, mode = get_recommendations(
        user_id,
        limit
    )

    # -----------------------------------------------------
    # MODE MESSAGE
    # -----------------------------------------------------

    if mode == "similar":

        st.success(
            "👥 ระบบพบ User ที่มีความชอบคล้ายกัน "
            "จึงใช้ Similar User Recommendation"
        )

    elif mode == "new_user":

        st.info(
            "🆕 User นี้ยังไม่มี LIKES "
            "ระบบจึงใช้ Popular Manga Recommendation"
        )

    else:

        st.info(
            "ไม่พบ User ที่มีความชอบคล้ายกัน "
            "ระบบจึงใช้ Popular Manga เป็นทางเลือก"
        )

    # -----------------------------------------------------
    # SHOW RECOMMENDATIONS
    # -----------------------------------------------------

    if not rows:

        st.warning(
            "ยังไม่มี Manga สำหรับแนะนำ"
        )

    for i, row in enumerate(
        rows,
        start=1
    ):

        if row["type"] == "similar_user":

            reason = (
                "User ที่มีความชอบคล้ายกัน "
                "เคยชอบ Manga นี้"
            )

        else:

            reason = (
                "Manga นี้ได้รับความนิยม "
                "จากจำนวน LIKES"
            )

        st.markdown(
            f"""
            <div class="manga-card">

                <span class="score">
                    #{i} · score {row["score"]}
                </span>

                <h3>
                    {row["title"]}
                </h3>

                <div class="muted">
                    Manga ID: {row["manga_id"]}
                </div>

                <p>
                    <b>เหตุผล:</b>
                    {reason}
                </p>

            </div>
            """,

            unsafe_allow_html=True
        )

    # -----------------------------------------------------
    # CREATE RELATIONSHIP
    # -----------------------------------------------------

    st.divider()

    if st.button(
        "🔗 สร้างเส้น RECOMMENDS ให้ User นี้",
        type="primary",
        use_container_width=True
    ):

        count = create_recommend_relationships(
            user_id,
            limit
        )

        st.success(
            f"สร้าง RECOMMENDS สำเร็จ {count} เส้น"
        )

        st.rerun()


# =========================================================
# MANGA SEARCH
# =========================================================

elif page == "Manga Search":

    st.subheader(
        "🔎 ค้นหา Manga"
    )

    keyword = st.text_input(
        "ชื่อ Manga",

        placeholder=(
            "เช่น Naruto, One Piece, Jujutsu"
        )
    )

    rows = search_manga(
        keyword
    )

    st.write(
        f"พบ {len(rows)} รายการ"
    )

    if rows:

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "ไม่พบ Manga"
        )


# =========================================================
# MANAGE LIKES
# =========================================================

elif page == "Manage Likes":

    st.subheader(
        "❤️ จัดการ Manga ที่ User ชอบ"
    )

    all_users = get_users()

    all_mangas = get_mangas()

    if not all_users:

        st.warning(
            "ยังไม่มี User"
        )

        st.stop()

    if not all_mangas:

        st.warning(
            "ยังไม่มี Manga"
        )

        st.stop()

    # -----------------------------------------------------
    # USER
    # -----------------------------------------------------

    user_options = {
        f"{u['user_id']} — {u['name']}":
        u["user_id"]

        for u in all_users
    }

    selected_user = st.selectbox(
        "เลือก User",
        list(user_options.keys())
    )

    user_id = user_options[
        selected_user
    ]

    # -----------------------------------------------------
    # CURRENT LIKES
    # -----------------------------------------------------

    st.markdown(
        "### ❤️ Manga ที่ชอบอยู่แล้ว"
    )

    liked = get_liked_mangas(
        user_id
    )

    if liked:

        st.dataframe(
            pd.DataFrame(liked),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "User นี้ยังไม่มี LIKES"
        )

    st.divider()

    # -----------------------------------------------------
    # ADD LIKE
    # -----------------------------------------------------

    manga_options = {
        f"{m['manga_id']} — {m['title']}":
        m["manga_id"]

        for m in all_mangas
    }

    selected_manga = st.selectbox(
        "เลือก Manga ที่ชอบ",
        list(manga_options.keys())
    )

    manga_id = manga_options[
        selected_manga
    ]

    if st.button(
        "❤️ เพิ่ม LIKES",
        type="primary",
        use_container_width=True
    ):

        add_like(
            user_id,
            manga_id
        )

        st.success(
            "เพิ่ม LIKES สำเร็จ"
        )

        st.rerun()


# =========================================================
# GRAPH EXPLORER
# =========================================================

elif page == "Graph Explorer":

    st.subheader(
        "🕸️ Graph Explorer"
    )

    st.write(
        """
        แสดงความสัมพันธ์ระหว่าง User และ Manga

        - LIKES
        - RECOMMENDS
        """
    )

    all_users = get_users()

    if not all_users:

        st.warning(
            "ยังไม่มี User"
        )

        st.stop()

    # -----------------------------------------------------
    # USER SELECT
    # -----------------------------------------------------

    options = {
        "ทั้งหมด": None
    }

    options.update({
        f"{u['user_id']} — {u['name']}":
        u["user_id"]

        for u in all_users
    })

    selected = st.selectbox(
        "เลือก User",
        list(options.keys())
    )

    user_id = options[selected]

    rows = get_graph(
        user_id
    )

    if not rows:

        st.info(
            "ยังไม่มี Graph"
        )

    else:

        dot = [

            "digraph G {",

            'rankdir="LR";',

            (
                'node [shape=box, '
                'style="rounded,filled", '
                'fillcolor="#f8fafc"];'
            )
        ]

        seen = set()

        for row in rows:

            source = row["source_id"]

            target = row["target_id"]

            relationship = row[
                "relationship"
            ]

            # -------------------------------------------------
            # SOURCE
            # -------------------------------------------------

            if source not in seen:

                safe_name = (
                    str(
                        row["source_name"]
                    )
                    .replace(
                        '"',
                        "'"
                    )
                )

                dot.append(
                    f'"{source}" '
                    f'[label="{safe_name}\\nUser"];'
                )

                seen.add(source)

            # -------------------------------------------------
            # TARGET
            # -------------------------------------------------

            if target not in seen:

                safe_name = (
                    str(
                        row["target_name"]
                    )
                    .replace(
                        '"',
                        "'"
                    )
                )

                dot.append(
                    f'"{target}" '
                    f'[label="{safe_name}\\nManga"];'
                )

                seen.add(target)

            # -------------------------------------------------
            # EDGE
            # -------------------------------------------------

            dot.append(
                f'"{source}" -> "{target}" '
                f'[label="{relationship}"];'
            )

        dot.append(
            "}"
        )

        st.graphviz_chart(
            "\n".join(dot),
            use_container_width=True
        )

        st.markdown(
            "### Relationship Data"
        )

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True
        )

    # -----------------------------------------------------
    # CYPHER
    # -----------------------------------------------------

    st.divider()

    st.markdown(
        "### Cypher สำหรับดู Graph ใน Neo4j"
    )

    st.code(
        """
MATCH p=(u:User)-[r:LIKES|RECOMMENDS]->(m:Manga)
RETURN p
LIMIT 100
        """,

        language="cypher"
    )


# =========================================================
# ADMIN / SETUP
# =========================================================

elif page == "Admin / Setup":

    st.subheader(
        "⚙️ Admin / Setup"
    )

    # -----------------------------------------------------
    # SCHEMA
    # -----------------------------------------------------

    st.markdown(
        """
        ### Graph Schema

        ```text
        (:User)-[:LIKES]->(:Manga)

        (:User)-[:RECOMMENDS {
            score,
            type
        }]->(:Manga)
        ```
        """
    )

    # -----------------------------------------------------
    # CONSTRAINT
    # -----------------------------------------------------

    if st.button(
        "🔧 สร้าง Constraint",
        use_container_width=True
    ):

        try:

            create_constraints()

            st.success(
                "สร้าง Constraint สำเร็จ"
            )

        except Exception as e:

            st.error(
                "สร้าง Constraint ไม่สำเร็จ"
            )

            st.exception(e)

    st.divider()

    # -----------------------------------------------------
    # DEMO DATA
    # -----------------------------------------------------

    st.markdown(
        "### 📦 ข้อมูลตัวอย่าง"
    )

    st.caption(
        """
        สร้าง User + Manga + LIKES

        U011 จะไม่มี LIKES
        เพื่อใช้ทดสอบ Cold Start
        """
    )

    if st.button(
        "📦 สร้าง User + Manga + LIKES",
        type="primary",
        use_container_width=True
    ):

        try:

            create_demo_data()

            st.success(
                "สร้างข้อมูลตัวอย่างสำเร็จ"
            )

            st.rerun()

        except Exception as e:

            st.error(
                "สร้างข้อมูลตัวอย่างไม่สำเร็จ"
            )

            st.exception(e)

    st.divider()

    # -----------------------------------------------------
    # RECOMMENDS
    # -----------------------------------------------------

    st.markdown(
        "### 🔗 สร้าง RECOMMENDS"
    )

    limit = st.slider(
        "จำนวน Recommendation ต่อ User",
        1,
        10,
        5
    )

    if st.button(
        "🔄 สร้าง RECOMMENDS ให้ทุก User",
        type="primary",
        use_container_width=True
    ):

        try:

            count = create_recommend_relationships(
                limit=limit
            )

            st.success(
                f"สร้าง RECOMMENDS สำเร็จ {count} เส้น"
            )

            st.rerun()

        except Exception as e:

            st.error(
                "สร้าง RECOMMENDS ไม่สำเร็จ"
            )

            st.exception(e)

    st.divider()

    # -----------------------------------------------------
    # SHOW RECOMMENDS
    # -----------------------------------------------------

    st.markdown(
        "### 📋 RECOMMENDS ทั้งหมด"
    )

    rows = get_recommends()

    if rows:

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "ยังไม่มี RECOMMENDS"
        )