import getpass
import json
import os
import random
import sys
import time
from instaloader import Instaloader, Profile
from instagrapi import Client

from instagram_reels_download import extract_username, extract_shortcode, delete_related_files, download_single_reel, download_profile_reels, download_profile
from instagram_reels_upload import load_simple_env, create_client_with_session, upload_video


def main():
	load_simple_env()

	username = os.environ.get("IG_USERNAME")
	password = os.environ.get("IG_PASSWORD")

	if not username:
		username = input("Enter your Instagram username: ").strip()
	if not password:
		password = getpass.getpass("Enter password: ")

	print("\nChoose an option:")
	print("1. Download and upload a single reel from link")
	print("2. Download and upload all reels from an Instagram profile")
	print("3. Download only (from profile)")
	print("4. Upload a video file")

	choice = input("Enter choice (1-4): ").strip()

	dest = "downloads"
	os.makedirs(dest, exist_ok=True)

	L = Instaloader(dirname_pattern=os.path.join(dest, "{target}"), quiet=True)

	# No login for downloading, proceed anonymously

	if choice in ['1', '2', '4']:
		# Upload client
		cl = create_client_with_session()
		# Check if logged in
		try:
			cl.get_timeline_feed()  # test if logged in
			print("Using existing session for uploading.")
		except:
			# Not logged in, login
			try:
				cl.login(username, password)
				print("Logged in for uploading.")
			except Exception as e:
				print("Login failed for uploading:", e)
				sys.exit(1)

	if choice == '1':
		# Single reel
		reel_link = input("Enter the reel link: ").strip()
		try:
			shortcode = extract_shortcode(reel_link)
		except ValueError as e:
			print(e)
			sys.exit(1)

		result = download_single_reel(L, shortcode, dest)
		if result:
			mp4_path, caption = result
			print(f"Uploading {mp4_path}...")
			upload_video(cl, mp4_path, caption)
			base = mp4_path[:-4]  # remove .mp4
			delete_related_files(base)

		download_folder = os.path.join(dest, "reel_download")
		if os.path.isdir(download_folder):
			try:
				if not os.listdir(download_folder):
					os.rmdir(download_folder)
			except Exception:
				pass

	elif choice == '2':
		# Profile reels
		profile_input = input("Enter Instagram username or profile link: ").strip()
		try:
			profile_username = extract_username(profile_input)
		except Exception as e:
			print("Error parsing profile input:", e)
			sys.exit(1)

		# Load profile to get total
		try:
			profile = Profile.from_username(L.context, profile_username)
			total_reels = sum(1 for post in profile.get_posts() if getattr(post, 'is_video', False))
			print(f"Total reels available: {total_reels}")
		except Exception as e:
			print("Failed to load profile:", e)
			sys.exit(1)

		print("1. Download and upload ALL reels")
		print("2. Download and upload in RANGE")
		sub_choice = input("Enter sub-choice (1-2): ").strip()

		if sub_choice == '1':
			start, end = 1, None
			total_in_range = total_reels
		elif sub_choice == '2':
			range_input = input("Enter range (e.g., 4,20): ").strip()
			try:
				start, end = map(int, range_input.split(','))
				total_in_range = end - start + 1
			except:
				print(json.dumps({"error": "Invalid range"}))
				sys.exit(1)
		else:
			print(json.dumps({"error": "Invalid sub-choice"}))
			sys.exit(1)

		count = 0
		reel_count = 0
		for post in profile.get_posts():
			if getattr(post, 'is_video', False):
				reel_count += 1
				if reel_count < start:
					continue
				if end and reel_count > end:
					break
				try:
					L.download_post(post, target=profile_username)

					base = os.path.join(dest, profile_username, f"{post.date_utc.strftime('%Y-%m-%d_%H-%M-%S_UTC')}")
					mp4_path = base + ".mp4"

					if os.path.exists(mp4_path):
						caption = post.caption or ""
						upload_video(cl, mp4_path, caption)
						delete_related_files(base)
						count += 1
						wait_time = random.randint(20 * 60, 60 * 60)
						print(f"{count}/{total_in_range} done - waiting {wait_time // 60} min before next")
						time.sleep(wait_time)
					else:
						print(json.dumps({"error": f"Video file not found: {mp4_path}"}))
				except Exception as e:
					print(json.dumps({"error": f"Failed to process reel {reel_count}: {str(e)}"}))

		profile_folder = os.path.join(dest, profile_username)
		if os.path.isdir(profile_folder):
			try:
				if not os.listdir(profile_folder):
					os.rmdir(profile_folder)
			except Exception:
				pass
		print(f"Processed {count} reels.")

	elif choice == '3':
		# Download only
		profile_input = input("Enter Instagram username or profile link: ").strip()
		try:
			profile_username = extract_username(profile_input)
		except Exception as e:
			print("Error parsing profile input:", e)
			sys.exit(1)

		download_profile(L, profile_username)

	elif choice == '4':
		# Upload only
		video_path = input("Enter path to video file: ").strip()
		caption = input("Enter caption: ").strip()
		if os.path.exists(video_path):
			upload_video(cl, video_path, caption)
		else:
			print("Video file not found")

	else:
		print("Invalid choice")


if __name__ == "__main__":
	main()

