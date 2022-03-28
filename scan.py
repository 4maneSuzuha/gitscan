import argparse
import json
import multiprocessing as mp
import logging
import os
import subprocess

import requests


# TODO: don't create file if result is empty
#   may put shell commands into separated script file
class Scanner:
    def __init__(self, source, config, output):
        self.reg_strings = ''.join([f'({reg_string})|' for reg_string in config['strings']])[:-1]
        self.reg_file = ''.join([f' "*{reg_file}"' for reg_file in config['files']])[1:]
        self.excludes = config['excludes']
        self.clone_url = source['clone_url']
        self.name = source['name']
        self.output = output
        self.path = f'{self.output}{self.name}'

    def git_clone(self):
        if os.path.exists(self.path):
            logging.info(f'{self.path} already exists')
            return
        subprocess.run(['git', 'clone', '--quiet', self.clone_url, self.path])
        logging.info(f'cloned {self.clone_url} to {self.path}')

    def scan_files(self):
        logging.info(f'scanning files in {self.path}')
        command1 = f'git --git-dir={self.path}/.git --no-pager log --name-only --oneline -p -- {self.reg_file} '
        command1 += f'$(git --git-dir={self.path}/.git rev-list --all) '
        command1 += f'>> {self.output}out.d/git-scan-files-{self.name}.txt'
        logging.debug(command1)
        subprocess.run(command1, shell=True)

    def scan_strings(self):
        logging.info(f'scanning for text occurrences in {self.path}')
        exclude = ''.join([f' ":!{exclude}"' for exclude in self.excludes])[1:]
        command2 = f'git --git-dir={self.path}/.git --no-pager grep -iE "{self.reg_strings}" '
        command2 += f'$(git --git-dir={self.path}/.git rev-list --all '
        command2 += f'-- {exclude}) -- {exclude} '
        # TODO: fix here to match everything after second item
        command2 += f"| awk -F'[:]' '!seen[$2,$3,$4,$5,$6,$7,$8,$9,$10]++' "
        command2 += f'>> {self.output}out.d/git-scan-strings-{self.name}.txt'
        logging.debug(command2)
        subprocess.run(command2, shell=True)

    def scan(self):
        self.git_clone()
        self.scan_files()
        self.scan_strings()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Scan credentials in git repos/users.')
    parser.add_argument('-u', '--user', help='github username', required=True)
    parser.add_argument('-r', '--repo', help='repository name')
    parser.add_argument('-o', '--out', help='output folder', required=True)
    parser.add_argument('-v', '--verbose', help='show verbose output from scan', action='store_true')
    args = parser.parse_args()
    username = args.user

    repo = args.repo
    out = args.out
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    os.makedirs(f'{out}out.d', exist_ok=True)

    api_url = f'https://api.github.com/users/{username}/repos'

    repos = [{'name': repo, 'fork': False,
              'clone_url': f'https://github.com/{username}/{repo}.git'}] if repo else json.loads(
        requests.get(api_url).text)

    sources = [{'name': r['name'], 'clone_url': r['clone_url']} for r in repos if not r['fork']]
    with open('config.json', 'r') as f:
        conf = json.load(f)
    scanners = [Scanner(source, conf, out) for source in sources]
    ps = [mp.Process(target=scanner.scan) for scanner in scanners]
    for p in ps:
        p.start()
    for p in ps:
        p.join()
