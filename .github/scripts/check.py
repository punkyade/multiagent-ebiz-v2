"""플러그인 저장소 자동 점검. 사용법: python .github/scripts/check.py [--base <git ref>]

--base를 주면 그 커밋 이후 플러그인 내용이 바뀌었는데 버전을 올리지 않았는지도 확인한다.
버전이 그대로면 설치한 사용자가 업데이트를 받지 못하기 때문이다.
"""
import glob
import json
import os
import re
import subprocess
import sys

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PLUGIN_JSON = ".claude-plugin/plugin.json"
MARKETPLACE_JSON = ".claude-plugin/marketplace.json"
SETTINGS_JSON = ".claude/settings.json"
PLUGIN_PATHS = ["skills/", ".claude-plugin/"]  # 바뀌면 버전을 올려야 하는 경로

errors = []


def git(*args):
    # encoding을 지정하지 않으면 Windows에서 시스템 코드페이지(cp949)로 읽어 한글이 깨진다
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, encoding="utf-8")


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


def load_json(path):
    try:
        return json.loads(read(path))
    except (OSError, ValueError) as e:
        errors.append(f"{path}: JSON을 읽을 수 없음 ({e})")
        return None


def check_manifests():
    plugin = load_json(PLUGIN_JSON)
    market = load_json(MARKETPLACE_JSON)
    settings = load_json(SETTINGS_JSON) if os.path.exists(os.path.join(ROOT, SETTINGS_JSON)) else None
    if not plugin or not market:
        return plugin

    entry = next((p for p in market.get("plugins", []) if p.get("name") == plugin.get("name")), None)
    if entry is None:
        errors.append(f"{MARKETPLACE_JSON}: plugins에 '{plugin.get('name')}' 항목이 없음")
    elif entry.get("version") != plugin.get("version"):
        errors.append(f"버전 불일치: {PLUGIN_JSON}={plugin.get('version')}, {MARKETPLACE_JSON}={entry.get('version')}")

    if settings:
        name = market.get("name")
        if name not in settings.get("extraKnownMarketplaces", {}):
            errors.append(f"{SETTINGS_JSON}: extraKnownMarketplaces에 마켓플레이스 이름 '{name}'이 없음")
        for key in settings.get("enabledPlugins", {}):
            if key.split("@")[-1] != name:
                errors.append(f"{SETTINGS_JSON}: enabledPlugins '{key}'의 마켓플레이스가 '{name}'과 다름")
    return plugin


def check_yaml():
    for path in sorted(glob.glob(os.path.join(ROOT, ".github", "ISSUE_TEMPLATE", "*.yml"))):
        try:
            yaml.safe_load(open(path, encoding="utf-8"))
        except yaml.YAMLError as e:
            errors.append(f"{os.path.relpath(path, ROOT)}: YAML 오류 ({e})")


def check_skills():
    for path in sorted(glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md"))):
        rel = os.path.relpath(path, ROOT)
        m = re.match(r"---\r?\n(.*?)\r?\n---", read(rel), re.S)
        meta = yaml.safe_load(m.group(1)) if m else None
        if not isinstance(meta, dict) or not meta.get("name") or not meta.get("description"):
            errors.append(f"{rel}: frontmatter에 name과 description이 필요함")


def slug(heading):
    # GitHub가 제목으로 만드는 앵커 규칙
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def check_links():
    files = git("ls-files", "*.md").stdout.split()
    for rel in files:
        text = re.sub(r"```.*?```", "", read(rel), flags=re.S)  # 코드 블록 안의 링크는 예시다
        ids = set(re.findall(r'<a id="([^"]+)"', text)) | {slug(h) for h in re.findall(r"^#+\s+(.+)$", text, re.M)}
        for target in re.findall(r"\]\(([^)\s]+)\)", text):
            if re.match(r"[a-z]+:", target):
                continue  # 외부 링크
            path, _, anchor = target.partition("#")
            if path:
                full = os.path.normpath(os.path.join(ROOT, os.path.dirname(rel), path))
                if not os.path.exists(full):
                    errors.append(f"{rel}: 없는 파일을 가리키는 링크 ({target})")
            elif anchor not in ids:
                errors.append(f"{rel}: 문서 안에 없는 앵커 (#{anchor})")


def check_version_bump(base, plugin):
    changed = git("diff", "--name-only", base, "HEAD", "--", *PLUGIN_PATHS).stdout.split()
    if not changed:
        return
    old = git("show", f"{base}:{PLUGIN_JSON}")
    if old.returncode != 0:
        return  # 기준 커밋에 plugin.json이 없으면 비교하지 않는다
    if json.loads(old.stdout).get("version") == plugin.get("version"):
        errors.append(
            f"플러그인 내용이 바뀌었는데 버전이 {plugin.get('version')} 그대로임 "
            f"(바뀐 파일: {', '.join(changed[:5])}). {PLUGIN_JSON}과 {MARKETPLACE_JSON}의 버전을 올리고 CHANGELOG에 적을 것"
        )


def main():
    base = sys.argv[sys.argv.index("--base") + 1] if "--base" in sys.argv else None
    plugin = check_manifests()
    check_yaml()
    check_skills()
    check_links()
    if base and plugin:
        check_version_bump(base, plugin)

    for e in errors:
        print(f"::error::{e}" if os.environ.get("GITHUB_ACTIONS") else f"오류: {e}")
    print(f"점검 완료: 오류 {len(errors)}건")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
