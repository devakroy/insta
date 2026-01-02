Run the script to fetch a profile (metadata + media):

```bash
python main.py https://www.instagram.com/instagram_username/ --dest downloads
```

Only fetch metadata (no media):

```bash
python main.py instagram --no-media
```

To access private content or stories, provide a login username and you'll be prompted for a password:

```bash
python main.py private_account --login your_instagram_username
```

Notes
-----
- This uses the `instaloader` package and respects Instagram access rules.
- Downloading a large profile may take long and may require login for private content.
- Use this tool responsibly and in accordance with Instagram's terms.
# insta