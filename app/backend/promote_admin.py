"""Promote an existing account to administrator from the trusted server shell."""
import argparse

from database import SessionLocal, init_db
from models import User


def main():
    parser = argparse.ArgumentParser(description="将现有 TILIAN 题炼账号提升为管理员")
    parser.add_argument("username", help="已注册的用户名")
    args = parser.parse_args()
    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == args.username).first()
        if not user:
            raise SystemExit(f"用户不存在：{args.username}")
        user.role = "admin"
        db.commit()
        print(f"已将 {args.username} 提升为管理员")
    finally:
        db.close()


if __name__ == "__main__":
    main()
