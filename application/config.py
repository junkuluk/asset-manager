import sys
import os

# 이 config.py 파일이 있는 폴더의 경로 (asset_manager 또는 app)
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# 그 상위 폴더(MyFinance 또는 dist)를 기본 경로(BASE_DIR)로 설정
BASE_DIR = os.path.dirname(APP_DIR)

# 이제 모든 파일 경로는 이 BASE_DIR을 기준으로 생성.
STATIC_DIR = os.path.join(BASE_DIR, "static")
RULES_PATH = os.path.join(STATIC_DIR, "initial_rules.json")
CATEGORIES_PATH = os.path.join(STATIC_DIR, "categories.json")
TRANSFER_RULES_PATH = os.path.join(STATIC_DIR, "initial_transfer_rules.json")

SCHEMA_PATH = os.path.join(APP_DIR, "migrations")
