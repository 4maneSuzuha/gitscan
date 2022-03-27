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

with open('config.json', 'r') as f:
    config = json.load(f)
    text_regexes = config['text']
    filename_regexes = config['filename']
    excludes = config['excludes']

for path in paths:
    print(f'scanning files in {path}')
    filename_regex = ''.join([f' "*{incl}"' for incl in filename_regexes])[1:]
    command1 = f'git --git-dir={path}/.git --no-pager log --name-only --oneline -p -- {filename_regex} '
    command1 += f'$(git --git-dir={path}/.git rev-list --all)'
    logging.debug(command1)
    subprocess.run(command1, shell=True)

    print(f'scanning for text occurrences in {path}')
    text_regex = ''.join([f'({tr})|' for tr in text_regexes])[:-1]
    exclude = ''.join([f' ":!{excl}"' for excl in excludes])[1:]
    command2 = f'git --git-dir={path}/.git --no-pager grep -iE "{text_regex}" '
    command2 += f'$(git --git-dir={path}/.git rev-list --all '
    command2 += f'-- {exclude}) -- {exclude}'
    logging.debug(command2)
    subprocess.run(command2, shell=True)
