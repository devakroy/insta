"""Upload video to Instagram using instagrapi (login with username/password).

Usage:
  python instagrapi_upload.py --username USER --password PASS --video path\to\video.mp4 --caption "My caption"

Options:
  --session FILE    Save/load session file to avoid re-login and 2FA prompts.
  --reel            Upload as a reel (calls `reel_upload`) instead of feed video.

Notes:
  - This uses the unofficial `instagrapi` library which logs in with credentials.
  - Keep credentials and session file secure.
"""
import argparse
import sys
import os
import json
from instagrapi import Client
from typing import Optional


def main():
    # Load simple .env file in workspace root if present (key=value lines)
    def load_simple_env(path: str = ".env"):
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    # don't override existing env vars
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass

    load_simple_env()

    parser = argparse.ArgumentParser(description="Upload video with instagrapi")
    parser.add_argument("--username", required=False, help="Instagram username (or set IG_USERNAME in .env)")
    parser.add_argument("--password", help="Instagram password (omit to prompt) or set IG_PASSWORD in .env")
    parser.add_argument("--video", required=True, help="Path to local MP4 video")
    parser.add_argument("--caption", default="", help="Caption for the post")
    parser.add_argument("--session", help="Path to session file to save/load session")
    parser.add_argument("--reel", action="store_true", help="Upload as a reel instead of feed video")
    args = parser.parse_args()

    if not os.path.exists(args.video):
        print("Video file not found:", args.video)
        sys.exit(1)

    # Use CLI args if provided, otherwise prefer IG-specific env vars (avoid Windows USERNAME)
    username = args.username or os.environ.get("IG_USERNAME")
    password = args.password or os.environ.get("IG_PASSWORD")

    if not username:
        print("No username provided. Set IG_USERNAME in .env or pass --username.")
        sys.exit(1)

    if not password:
        # Prompt for password if not provided
        import getpass
        password = getpass.getpass(f"Password for {username}: ")

    cl = Client()

    # Try to load session if provided
    if args.session and os.path.exists(args.session):
        try:
            cl.load_settings(args.session)
            print("Loaded session from", args.session)
        except Exception:
            print("Failed to load session; will login interactively")

    # Attempt login (if session valid, login will typically be fast)
    try:
        cl.login(username, password)
    except Exception as e:
        msg = str(e)
        print("Login failed:", msg)
        # Provide targeted advice for common cases
        low = msg.lower()
        if "blacklist" in low or "black list" in low or "ip" in low:
            print("Instagram may be blocking your IP. Try: 1) log in via browser to verify your account; 2) use a different network or VPN; 3) wait a few minutes and retry.")
        if "email" in low or "we can send you an email" in low:
            print("Instagram requests account recovery via email. Check your account email for recovery steps and complete them in a browser.")
        print("If the account shows a challenge/2FA in a browser, complete it there and try again.")
        sys.exit(1)

    # Save session if requested
    if args.session:
        try:
            cl.dump_settings(args.session)
            print("Saved session to", args.session)
        except Exception as e:
            print("Failed to save session:", e)

    try:
        if args.reel:
            print("Uploading as reel...")
            media = cl.video_upload_reel(args.video, args.caption)
        else:
            print("Uploading as feed video...")
            media = cl.video_upload(args.video, args.caption)
    except Exception as e:
        print("Upload failed:", e)
        sys.exit(1)

    print("Upload successful. Media info:")
    try:
        print(json.dumps(media, ensure_ascii=False, indent=2, default=str))
    except Exception:
        # Fallback: stringify
        print(str(media))


if __name__ == "__main__":
    main()
