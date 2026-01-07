import contextlib
import os
from instagrapi import Client


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


def create_client_with_session(session_path="session.json"):
	"""Create instagrapi client, load session if exists."""
	cl = Client()
	if os.path.exists(session_path):
		try:
			cl.load_settings(session_path)
			print("Loaded session from", session_path)
		except Exception as e:
			print("Failed to load session:", e)
	return cl


def upload_video(cl, video_path, caption="", session_path="session.json"):
	"""Upload a video, save session after."""
	try:
		with contextlib.redirect_stdout(None):
			media = cl.video_upload(video_path, caption)
		# Save session
		try:
			cl.dump_settings(session_path)
		except Exception:
			pass
		return True
	except Exception:
		return False