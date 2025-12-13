# -*- coding: utf-8 -*-
from database import DatabaseManager

db = DatabaseManager('file_index.db')

# 1. 특정 파일 검색
print("=" * 60)
print("1. 파일 검색: 181655")
print("=" * 60)
cursor = db.conn.execute(
    "SELECT path, mtime FROM files_fts WHERE path LIKE ? AND deleted = '0'",
    ('%181655%',)
)
results = cursor.fetchall()
if results:
    for r in results:
        print(f"✅ 찾음: {r[0]}")
        print(f"   수정시간: {r[1]}")
else:
    print("❌ DB에 없음")

# 2. PNG 파일 통계
print("\n" + "=" * 60)
print("2. 인덱싱 통계")
print("=" * 60)
cursor = db.conn.execute("SELECT COUNT(*) FROM files_fts WHERE deleted = '0'")
total = cursor.fetchone()[0]
print(f"전체 파일: {total}개")

cursor = db.conn.execute("SELECT COUNT(*) FROM files_fts WHERE path LIKE '%.png' AND deleted = '0'")
png_count = cursor.fetchone()[0]
print(f"PNG 파일: {png_count}개")

# 3. 최근 인덱싱된 PNG 파일
print("\n" + "=" * 60)
print("3. 최근 인덱싱된 PNG 파일 (5개)")
print("=" * 60)
cursor = db.conn.execute(
    "SELECT path, mtime FROM files_fts WHERE path LIKE '%.png' AND deleted = '0' ORDER BY mtime DESC LIMIT 5"
)
recent_pngs = cursor.fetchall()
for i, r in enumerate(recent_pngs, 1):
    print(f"{i}. {r[0]}")
    print(f"   수정시간: {r[1]}")
