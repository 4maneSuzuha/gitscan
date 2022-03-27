import json
import logging
import requests
import subprocess
import os
import argparse

parser = argparse.ArgumentParser(
    description='Scan credentials in git repos/users.')
parser.add_argument('-u', '--user', help='github username', required=True)
parser.add_argument('-r', '--repo', help='repository name')
parser.add_argument('-v', '--verbose', help='show verbose output from scan', action='store_true')

args = parser.parse_args()

username = args.user
repo = args.repo
if args.verbose:
    logging.basicConfig(level=logging.DEBUG)

api_url = f'https://api.github.com/users/{username}/repos'

with open('config.json', 'r') as f:
    config = json.load(f)
    text_regexes = config['text']
    filename_regexes = config['filename']

if repo:
    repos = [{'name': repo, 'fork': False, 'clone_url': f'https://github.com/{username}/{repo}.git'}]
else:
    repos = json.loads(requests.get(api_url).text)

sources = [{'name': r['name'], 'url': r['clone_url']} for r in repos if not r['fork']]

tmp_dir = '/tmp/git-scan'
os.makedirs(tmp_dir, exist_ok=True)
paths = []

for source in sources:
    path = f'{tmp_dir}/{source["name"]}'
    paths.append(path)
    if os.path.exists(path):
        print(f'{path} already exists')
        continue
    subprocess.run(['git', 'clone', '--quiet', source['url'], path])
    print(f'cloned {source["name"]} to {path}')

for path in paths:
    print(f'scanning {path} for text')
    text_regex = ''.join([f'({tr})|' for tr in text_regexes])[:-1]
    logging.debug(
        f'git --git-dir={path}/.git --no-pager grep -iE "{text_regex}" $(git --git-dir={path}/.git rev-list --all)')
    subprocess.run(
        f'git --git-dir={path}/.git --no-pager grep -iE "{text_regex}" $(git --git-dir={path}/.git rev-list --all)',
        shell=True)
