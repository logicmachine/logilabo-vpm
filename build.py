import json
import logging
import os

from collections import OrderedDict
from pathlib import Path
from urllib.parse import urlparse

import requests
from github import Auth, Github


PACKAGES_CACHE_DIR = Path("./cache")
OUTPUT_DIR = Path("./public")


gh_token = os.getenv("GH_TOKEN")
gh = Github(auth=Auth.Token(gh_token))

headers = {
    "Authorization": "token " + gh_token,
    "Accept": "application/octet-stream"
}
session = requests.Session()


def download_releases(package_repo: str, vpm_repo_url: str):
    repo = gh.get_repo(package_repo)
    releases = OrderedDict()
    for release in repo.get_releases():
        title = release.title
        package_json_asset = None
        package_zip_asset = None
        for asset in release.get_assets():
            if asset.name == "package.json":
                package_json_asset = asset
            if asset.name.endswith(".zip"):
                package_zip_asset = asset
        if package_json_asset is None:
            logging.warning("package.json is not found in {}:{}".format(package_repo, title))
            continue
        browser_download_url = package_zip_asset.browser_download_url
        asset_url = package_json_asset.url
        asset_path = Path(urlparse(asset_url).path[1:])
        cache_path = PACKAGES_CACHE_DIR / asset_path
        if cache_path.exists():
            logging.info("load cached package.json for {}:{}".format(package_repo, title))
            with open(cache_path, "r") as f:
                releases[title] = json.load(f)
            continue
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        logging.info("download package.json for {}:{}".format(package_repo, title))
        response = session.get(asset_url, headers=headers)
        data = json.loads(response.text)
        data["url"] = browser_download_url
        data["repo"] = vpm_repo_url
        with open(cache_path, "w") as f:
            json.dump(data, f)
        releases[title] = data
    return releases


def process_repo(repo_json_path: Path):
    with open(repo_json_path, "r") as f:
        repo_data = json.load(f)
    packages = {}
    for package_name, package_repo in repo_data["package_repos"].items():
        packages[package_name] = {
            "versions": download_releases(package_repo, repo_data["url"])
        }

    output = {
        "author":   repo_data["author"],
        "name":     repo_data["name"],
        "id":       repo_data["id"],
        "url":      repo_data["url"],
        "packages": packages
    }
    stem = repo_json_path.stem
    with open(OUTPUT_DIR / (stem + ".json"), "w") as f:
        json.dump(output, f)


def main():
    logging.basicConfig(level=logging.INFO)
    repos_dir = Path("./repos")
    for repo in repos_dir.glob("*.json"):
        process_repo(repo)


if __name__ == "__main__":
    main()

