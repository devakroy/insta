import argparse
import getpass
import json
import os
import re
import sys
from urllib.parse import urlparse

import requests
from instaloader import Instaloader, Profile


def extract_username(value: str) -> str:
	value = value.strip()
	if value.startswith("http"):
		parsed = urlparse(value)
		path = parsed.path.strip("/")
		if not path:
			raise ValueError("Couldn't extract username from URL")
		return path.split("/")[0]
	return value


def profile_metadata(profile: Profile) -> dict:
	return {
		"username": profile.username,
		"full_name": profile.full_name,
		"biography": profile.biography,
		"external_url": profile.external_url,
		"is_private": profile.is_private,
		"is_verified": profile.is_verified,
		"followers": profile.followers,
		"followees": profile.followees,
		"mediacount": profile.mediacount,
	}


def main():
	parser = argparse.ArgumentParser(description="Download Instagram profile data and media (posts/videos/stories)")
	parser.add_argument("profile", help="Instagram profile URL or username")
	parser.add_argument("--login", "-l", help="Login username to access private content (optional)")
	parser.add_argument("--dest", "-d", default=".", help="Destination folder to save data and media")
	parser.add_argument("--no-media", action="store_true", help="Only fetch metadata, do not download media")
	parser.add_argument("--only-videos", action="store_true", help="Download only video posts (mp4), skip images and other media")
	args = parser.parse_args()

	try:
		username = extract_username(args.profile)
	except Exception as e:
		print("Error parsing profile input:", e)
		sys.exit(1)

	dest = os.path.abspath(args.dest)
	os.makedirs(dest, exist_ok=True)

	L = Instaloader(dirname_pattern=os.path.join(dest, "{target}"))

	logged_in = False
	if args.login:
		password = getpass.getpass(f"Password for {args.login}: ")
		try:
			L.login(args.login, password)
			logged_in = True
		except Exception as e:
			print("Login failed:", e)

	try:
		profile = Profile.from_username(L.context, username)
	except Exception as e:
		print("Failed to load profile:", e)
		sys.exit(1)

	meta = profile_metadata(profile)


	# Collect posts metadata
	posts_meta = []
	print(f"Fetching metadata for {username} ({profile.mediacount} posts)...")

	def fetch_posts_via_html(username, max_posts=50):
		"""Fallback: scrape profile HTML for recent posts JSON (public profiles only)."""
		url = f"https://www.instagram.com/{username}/"
		headers = {
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36",
			"Accept-Language": "en-US,en;q=0.9",
		}
		try:
			r = requests.get(url, headers=headers, timeout=10)
			r.raise_for_status()
		except Exception as e:
			print("HTML fetch failed:", e)
			return []

		# Try to extract JSON from window._sharedData or from the script that contains 'edge_owner_to_timeline_media'
		m = re.search(r"window\._sharedData = (.*?);</script>", r.text, re.S)
		data = None
		if m:
			try:
				data = json.loads(m.group(1))
			except Exception:
				data = None

		if not data:
			# Try alternative JSON location
			m2 = re.search(r"<script type=\"text/javascript\">\s*try\{\s*window.__additionalDataLoaded\((.*?)\);", r.text, re.S)
			if m2:
				try:
					# m2 may contain two args, the second is JSON; attempt to find JSON object
					text = m2.group(1)
					# find first occurrence of '{' to parse
					idx = text.find('{')
					if idx != -1:
						data = json.loads(text[idx:])
				except Exception:
					data = None

		try:
			# Navigate to timeline media in the JSON structures
			if data and 'entry_data' in data and 'ProfilePage' in data['entry_data']:
				user = data['entry_data']['ProfilePage'][0]['graphql']['user']
				edges = user['edge_owner_to_timeline_media']['edges']
			else:
				# fallback: search for the timeline media object anywhere in the text
				json_match = re.search(r'"edge_owner_to_timeline_media"\s*:\s*(\{.*?\})\s*,\s*"edge_followed_by"', r.text, re.S)
				if json_match:
					media_obj = json.loads(json_match.group(1))
					edges = media_obj.get('edges', [])
				else:
					edges = []
		except Exception:
			edges = []

		posts = []
		for edge in edges[:max_posts]:
			node = edge.get('node', {})
			shortcode = node.get('shortcode')
			posts.append(
				{
					'shortcode': shortcode,
					'url': f"https://www.instagram.com/p/{shortcode}/" if shortcode else None,
					'is_video': node.get('is_video'),
					'likes': node.get('edge_liked_by', {}).get('count') if node.get('edge_liked_by') else None,
					'comments': node.get('edge_media_to_comment', {}).get('count') if node.get('edge_media_to_comment') else None,
					'date_utc': None,
					'caption': (node.get('edge_media_to_caption', {}).get('edges') or [{}])[0].get('node', {}).get('text'),
				}
			)
		return posts

	if logged_in:
		try:
			for post in profile.get_posts():
				posts_meta.append(
					{
						"shortcode": post.shortcode,
						"url": f"https://www.instagram.com/p/{post.shortcode}/",
						"is_video": post.is_video,
						"likes": post.likes,
						"comments": post.comments,
						"date_utc": post.date_utc.isoformat(),
						"caption": post.caption,
					}
				)
		except Exception as e:
			print("Error fetching posts while logged in:", e)
	else:
		# Anonymous: avoid GraphQL long retries; use HTML fallback for recent posts.
		posts_meta = fetch_posts_via_html(username, max_posts=50)

	meta["posts"] = posts_meta

	meta_path = os.path.join(dest, f"{username}_metadata.json")
	with open(meta_path, "w", encoding="utf-8") as f:
		json.dump(meta, f, ensure_ascii=False, indent=2)

	print("Saved metadata to", meta_path)

	if not args.no_media:
		print("Downloading media (this may take a while)...")
		try:
			# If requested, download only video posts (mp4)
			if args.only_videos:
				print("Downloading only video posts (mp4)...")
				count = 0
				import subprocess
				def delete_related_files(basepath):
					exts = [".jpg", ".txt", ".json.xz", ".json", ".webp", ".mp4"]
					for ext in exts:
						f = basepath + ext
						if os.path.exists(f):
							try:
								os.remove(f)
								print(f"Deleted {f}")
							except Exception:
								print(f"Failed to delete {f}")
					# Also delete thumbnail generated by instagrapi: <basename>.mp4.jpg
					thumb = basepath + ".mp4.jpg"
					if os.path.exists(thumb):
						try:
							os.remove(thumb)
							print(f"Deleted {thumb}")
						except Exception:
							print(f"Failed to delete {thumb}")

				try:
					for post in profile.get_posts():
						if getattr(post, 'is_video', False):
							L.download_post(post, target=username)
							# Find the downloaded mp4 file
							base = os.path.join(dest, username, f"{post.date_utc.strftime('%Y-%m-%d_%H-%M-%S_UTC')}")
							mp4_path = base + ".mp4"
							caption = post.caption or ""
							if os.path.exists(mp4_path):
								print(f"Uploading {mp4_path}...")
								try:
									subprocess.run([
										sys.executable,
										os.path.join(os.path.dirname(__file__), "instagrapi_upload.py"),
										"--video", mp4_path,
										"--caption", caption,
										"--session", "session.json"
									], check=True)
								except Exception as e:
									print(f"Upload failed for {mp4_path}: {e}")
								# Delete all related files
								delete_related_files(base)
							else:
								print(f"Video file not found: {mp4_path}")
							count += 1
				except Exception as e:
					print("Error while downloading/uploading video posts:", e)
				print(f"Downloaded and uploaded {count} video posts (if any).")
				# Delete metadata file after all uploads/cleanups
				if os.path.exists(meta_path):
					try:
						os.remove(meta_path)
						print(f"Deleted metadata file {meta_path}")
					except Exception:
						print(f"Failed to delete metadata file {meta_path}")
				# Delete the profile's download folder if empty
				profile_folder = os.path.join(dest, username)
				if os.path.isdir(profile_folder):
					try:
						if not os.listdir(profile_folder):
							os.rmdir(profile_folder)
							print(f"Deleted profile folder {profile_folder}")
						else:
							print(f"Profile folder {profile_folder} not empty, not deleted.")
					except Exception:
						print(f"Failed to delete profile folder {profile_folder}")
			else:
				# Download profile posts (images & videos)
				L.download_profile(username, profile_pic_only=False)

			# Attempt to download stories and highlights if logged in
			if logged_in:
				try:
					L.download_stories(userids=[profile.userid])
				except Exception:
					pass
		except Exception as e:
			print("Error while downloading media:", e)


if __name__ == "__main__":
	main()

