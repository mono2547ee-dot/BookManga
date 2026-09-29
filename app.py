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
    driver = GraphDatabase.driver(
        uri,
        auth=(username, password)
    )

    driver.verify_connectivity()

    return driver


def get_connection():

    try:
        uri = st.secrets["neo4j"]["uri"]
        username = st.secrets["neo4j"]["username"]
        password = st.secrets["neo4j"]["password"]
        database = st.secrets["neo4j"].get(
            "database",
            "neo4j"
        )

        driver = create_driver(
            uri,
            username,
            password
        )

        return driver, database

    except Exception as e:

        st.error("❌ เชื่อมต่อ Neo4j Aura ไม่สำเร็จ")

        st.markdown(
            """
            สร้าง Secrets ใน Streamlit Cloud เป็นรูปแบบนี้:
            """
        )

        st.code(
            """
[neo4j]
uri = "neo4j+s://YOUR_INSTANCE.databases.neo4j.io"
username = "neo4j"
password = "YOUR_PASSWORD"
database = "neo4j"
            """,
            language="toml"
        )

        st.exception(e)

        st.stop()


driver, DATABASE = get_connection()


# =========================================================
# GENERAL QUERY FUNCTION
# =========================================================

def run_query(cypher, **params):

    result = driver.execute_query(
        cypher,
        database_=DATABASE,
        **params
    )

    return [
        record.data()
        for record in result.records
    ]


# =========================================================
# CONSTRAINT
# =========================================================

def create_constraints():

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

    return run_query(
        """
        MATCH (u:User)

        RETURN
            u.user_id AS user_id,
            u.name AS name

        ORDER BY u.user_id
        """
    )


def get_user(user_id):

    rows = run_query(
        """
        MATCH (u:User {
            user_id: $user_id
        })

        RETURN
            u.user_id AS user_id,
            u.name AS name
        """,
        user_id=user_id
    )

    return rows[0] if rows else None


# =========================================================
# MANGA
# =========================================================

def get_mangas():

    return run_query(
        """
        MATCH (m:Manga)

        RETURN
            m.manga_id AS manga_id,
            m.title AS title

        ORDER BY m.title
        """
    )


# =========================================================
# LIKES
# =========================================================

def get_liked_mangas(user_id):

    return run_query(
        """
        MATCH
            (u:User {
                user_id: $user_id
            })-[:LIKES]->(m:Manga)

        RETURN
            m.manga_id AS manga_id,
            m.title AS title

        ORDER BY title
        """,
        user_id=user_id
    )


def add_like(user_id, manga_id):

    run_query(
        """
        MATCH
            (u:User {
                user_id: $user_id
            }),

            (m:Manga {
                manga_id: $manga_id
            })

        MERGE (u)-[:LIKES]->(m)
        """,
        user_id=user_id,
        manga_id=manga_id
    )


# =========================================================
# RECOMMENDATION
# =========================================================

def recommend_by_similar_user(
    user_id,
    limit=5
):

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
        user_id=user_id,
        limit=limit
    )


def recommend_popular(limit=5):

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
        limit=limit
    )


def get_recommendations(
    user_id,
    limit=5
):

    liked = get_liked_mangas(user_id)

    # ==========================================
    # USER เคยอ่านแล้ว
    # ==========================================

    if liked:

        rows = recommend_by_similar_user(
            user_id,
            limit
        )

        # ถ้าไม่มี Similar User
        # ให้ใช้ Manga ยอดนิยมแทน
        if rows:

            return rows, "similar"

        return (
            recommend_popular(limit),
            "popular_fallback"
        )

    # ==========================================
    # USER ใหม่
    # ==========================================

    return (
        recommend_popular(limit),
        "new_user"
    )


# =========================================================
# CREATE RECOMMENDS RELATIONSHIP
# =========================================================

def create_recommend_relationships(
    user_id=None,
    limit=5
):

    # ลบ RECOMMENDS เดิม
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
            user_id=user_id
        )

        target_users = [
            {
                "user_id": user_id
            }
        ]

    else:

        run_query(
            """
            MATCH ()-[r:RECOMMENDS]->()
            DELETE r
            """
        )

        target_users = get_users()

    created = 0

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

                user_id=uid,

                manga_id=row["manga_id"],

                score=row["score"],

                type=row["type"]
            )

            created += 1

    return created


# =========================================================
# RECOMMENDS
# =========================================================

def get_recommends(user_id=None):

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
            user_id=user_id
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
            score DESC
        """
    )


# =========================================================
# SEARCH
# =========================================================

def search_manga(keyword=""):

    return run_query(
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
        keyword=keyword.strip()
    )


# =========================================================
# GRAPH
# =========================================================

def get_graph(user_id=None):

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
            user_id=user_id
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

    return users, mangas, likes, recommends


# =========================================================
# DEMO DATA
# =========================================================

def create_demo_data():

    create_constraints()

    users = [
        ("U001", "Sompong"),
        ("U002", "Siriporn"),
        ("U003", "Niran"),
        ("U004", "Malee"),
        ("U005", "Chaiwat"),
        ("U006", "Kanya"),
        ("U007", "Anan"),
        ("U008", "Somying"),
        ("U009", "Prasit"),
        ("U010", "Nattaya"),
        ("U011", "New User"),
    ]

    mangas = [
        ("M001", "Naruto"),
        ("M002", "One Piece"),
        ("M003", "Attack on Titan"),
        ("M004", "Demon Slayer"),
        ("M005", "Death Note"),
        ("M006", "My Hero Academia"),
        ("M007", "Jujutsu Kaisen"),
        ("M008", "Fullmetal Alchemist"),
        ("M009", "Spy x Family"),
        ("M010", "Chainsaw Man"),
    ]

    likes = [
        ("U001", "M001"),
        ("U001", "M002"),

        ("U002", "M009"),
        ("U002", "M004"),

        ("U003", "M001"),
        ("U003", "M002"),
        ("U003", "M007"),

        ("U004", "M009"),
        ("U004", "M004"),
        ("U004", "M006"),

        ("U005", "M005"),
        ("U005", "M003"),

        ("U006", "M005"),
        ("U006", "M003"),
        ("U006", "M008"),

        ("U007", "M001"),
        ("U007", "M006"),

        ("U008", "M007"),
        ("U008", "M010"),

        ("U009", "M005"),
        ("U009", "M010"),

        ("U010", "M002"),
        ("U010", "M008"),
    ]

    for user_id, name in users:

        run_query(
            """
            MERGE (u:User {
                user_id: $user_id
            })

            SET
                u.name = $name
            """,

            user_id=user_id,
            name=name
        )

    for manga_id, title in mangas:

        run_query(
            """
            MERGE (m:Manga {
                manga_id: $manga_id
            })

            SET
                m.title = $title
            """,

            manga_id=manga_id,
            title=title
        )

    for user_id, manga_id in likes:

        add_like(
            user_id,
            manga_id
        )


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown("## 📚 MangaGraph")

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
            "Admin / Setup",
        ]
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
            ระบบแนะนำหนังสือการ์ตูนด้วย
            Neo4j Graph Database
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

    users_count, manga_count, likes_count, recommends_count = (
        get_metrics()
    )

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
                    "User นี้ยังไม่เคยอ่าน Manga"
                )

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
        "✨ ระบบแนะนำหนังสือการ์ตูน"
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

    if mode == "similar":

        st.success(
            "👥 User นี้มีประวัติการอ่าน "
            "ระบบจึงแนะนำจาก User ที่มีความชอบคล้ายกัน"
        )

    elif mode == "new_user":

        st.info(
            "🆕 User นี้ยังไม่เคยอ่าน Manga "
            "ระบบจึงแนะนำ Manga ที่ได้รับความนิยม"
        )

    else:

        st.info(
            "ไม่พบ User ที่มีความชอบคล้ายกัน "
            "ระบบจึงใช้ Manga ยอดนิยมแทน"
        )

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
                "แนะนำจาก User "
                "ที่มีความชอบคล้ายกัน"
            )

        else:

            reason = (
                "แนะนำจากความนิยมของ Manga"
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


# =========================================================
# MANGA SEARCH
# =========================================================

elif page == "Manga Search":

    st.subheader(
        "🔎 ค้นหาหนังสือการ์ตูน"
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
        "❤️ เพิ่ม Manga ที่ User ชอบ"
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

    user_options = {
        f"{u['user_id']} — {u['name']}":
        u["user_id"]

        for u in all_users
    }

    manga_options = {
        f"{m['manga_id']} — {m['title']}":
        m["manga_id"]

        for m in all_mangas
    }

    selected_user = st.selectbox(
        "User",
        list(user_options.keys())
    )

    user_id = user_options[
        selected_user
    ]

    st.markdown(
        "### Manga ที่ User ชอบอยู่แล้ว"
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
            "ยังไม่มี LIKES"
        )

    st.divider()

    selected_manga = st.selectbox(
        "เลือก Manga",
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
        "แสดงทั้งความสัมพันธ์ LIKES และ RECOMMENDS"
    )

    all_users = get_users()

    if not all_users:

        st.warning(
            "ยังไม่มี User"
        )

        st.stop()

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

            if source not in seen:

                safe_name = (
                    str(row["source_name"])
                    .replace('"', "'")
                )

                dot.append(
                    f'"{source}" '
                    f'[label="{safe_name}\\nUser"];'
                )

                seen.add(source)

            if target not in seen:

                safe_name = (
                    str(row["target_name"])
                    .replace('"', "'")
                )

                dot.append(
                    f'"{target}" '
                    f'[label="{safe_name}\\nManga"];'
                )

                seen.add(target)

            dot.append(
                f'"{source}" -> "{target}" '
                f'[label="{row["relationship"]}"];'
            )

        dot.append("}")

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
# ADMIN
# =========================================================

elif page == "Admin / Setup":

    st.subheader(
        "⚙️ Admin / Setup"
    )

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

    if st.button(
        "🔧 สร้าง Constraint",
        use_container_width=True
    ):

        create_constraints()

        st.success(
            "สร้าง Constraint สำเร็จ"
        )

    st.divider()

    st.markdown(
        "### สร้างข้อมูลตัวอย่าง"
    )

    st.caption(
        "ข้อมูลตัวอย่างจะใช้ MERGE "
        "จึงไม่สร้าง User/Manga ซ้ำ"
    )

    if st.button(
        "📦 สร้าง User + Manga + LIKES",
        type="primary",
        use_container_width=True
    ):

        create_demo_data()

        st.success(
            "สร้างข้อมูลตัวอย่างสำเร็จ"
        )

        st.rerun()

    st.divider()

    st.markdown(
        "### สร้าง RECOMMENDS"
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

        count = create_recommend_relationships(
            limit=limit
        )

        st.success(
            f"สร้าง RECOMMENDS สำเร็จ {count} เส้น"
        )

    st.divider()

    st.markdown(
        "### RECOMMENDS ทั้งหมด"
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