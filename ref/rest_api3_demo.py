import github_api_v3
import os

os.environ["GITHUB_TOKEN"] = "cfb4ad35f5cbde8676b8fbb8ef858ea0dc32391e"

url = "https://api.github.com/user/starred"
headers = {"Accept": "application/vnd.github.v3.star+json, application/vnd.github.mercy-preview+json"}
github_api_v3.getall(url, headers=headers)
