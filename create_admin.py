"""
Script to create the first admin user
Run this after setting up the database

Usage:
  Interactive mode: python create_admin.py
  Non-interactive:  python create_admin.py --username admin --email admin@example.com --password secret123
  Auto mode:        python create_admin.py --auto  (creates admin/admin@local.host/admin123)
"""
import asyncio
import sys
import argparse

from database import db
from auth import create_user, get_password_hash
from sqlalchemy import select
from database import User


async def create_admin_user(username: str = None, email: str = None, password: str = None, force: bool = False):
    """Create an admin user (interactive or non-interactive)"""
    interactive = username is None

    if interactive:
        print("\n" + "="*50)
        print("CSFloat Bot - Create Admin User")
        print("="*50 + "\n")

    # Initialize database
    await db.init()

    async for session in db.get_session():
        # Check if any users exist
        result = await session.execute(select(User))
        existing_users = result.scalars().all()

        if existing_users and not force:
            if interactive:
                print(f"Found {len(existing_users)} existing user(s):")
                for user in existing_users:
                    role = "Admin" if user.is_admin else "User"
                    print(f"  - {user.username} ({role})")
                print()

                choice = input("Create another admin? (y/n): ").strip().lower()
                if choice != 'y':
                    print("Cancelled.")
                    return False
            else:
                # Non-interactive: check if admin already exists
                for user in existing_users:
                    if user.is_admin:
                        print(f"Admin user already exists: {user.username}")
                        return True

        if interactive:
            # Get user details interactively
            print("\nEnter admin details:\n")

            username = input("Username (min 3 chars): ").strip()
            if len(username) < 3:
                print("Error: Username must be at least 3 characters")
                return False

            email = input("Email: ").strip()
            if '@' not in email:
                print("Error: Invalid email format")
                return False

            password = input("Password (min 6 chars): ").strip()
            if len(password) < 6:
                print("Error: Password must be at least 6 characters")
                return False

            confirm = input("Confirm password: ").strip()
            if password != confirm:
                print("Error: Passwords do not match")
                return False

        # Validate non-interactive inputs
        if len(username) < 3:
            print("Error: Username must be at least 3 characters")
            return False
        if '@' not in email:
            print("Error: Invalid email format")
            return False
        if len(password) < 6:
            print("Error: Password must be at least 6 characters")
            return False

        # Check if username/email exists
        result = await session.execute(
            select(User).where(User.username == username)
        )
        if result.scalar_one_or_none():
            print(f"Error: Username '{username}' already exists")
            return False

        result = await session.execute(
            select(User).where(User.email == email)
        )
        if result.scalar_one_or_none():
            print(f"Error: Email '{email}' already registered")
            return False

        # Create admin user
        try:
            user = await create_user(
                session=session,
                username=username,
                email=email,
                password=password,
                is_admin=True
            )

            print("\n" + "="*50)
            print("Admin user created successfully!")
            print("="*50)
            print(f"  Username: {user.username}")
            print(f"  Email: {user.email}")
            print(f"  Admin: Yes")
            print("\nYou can now login at http://localhost:8000/login")
            print("="*50 + "\n")
            return True

        except Exception as e:
            print(f"\nError creating user: {e}")
            return False

    await db.close()
    return False


def parse_args():
    parser = argparse.ArgumentParser(description='Create admin user for CSFloat Bot')
    parser.add_argument('--username', '-u', help='Admin username')
    parser.add_argument('--email', '-e', help='Admin email')
    parser.add_argument('--password', '-p', help='Admin password')
    parser.add_argument('--auto', action='store_true',
                        help='Create default admin (admin/admin@local.host/admin123)')
    parser.add_argument('--force', '-f', action='store_true',
                        help='Force create even if admin exists')
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    try:
        if args.auto:
            # Auto mode with default credentials
            result = asyncio.run(create_admin_user(
                username="admin",
                email="admin@local.host",
                password="admin123",
                force=args.force
            ))
        elif args.username and args.email and args.password:
            # Non-interactive mode with provided credentials
            result = asyncio.run(create_admin_user(
                username=args.username,
                email=args.email,
                password=args.password,
                force=args.force
            ))
        else:
            # Interactive mode
            result = asyncio.run(create_admin_user())

        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(0)
