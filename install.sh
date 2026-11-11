#!/usr/bin/env bash
# FKskill 安装器：把 skills/ 下的独立技能装到 WorkBuddy 用户级技能目录。
# 只创建/复制文件，不删除用户已有技能；覆盖前会先备份。
# --fetch 优先走 raw.githubusercontent.com，不可达时自动改用 GitHub contents API。
# 注意：中文文案里变量一律写成 ${VAR}，避免 bash 把全角标点吞进变量名。

set -euo pipefail

OWNER="${FKSKILL_OWNER:-2201242220-FranKing}"
REPO="${FKSKILL_REPO:-FKskill}"
BRANCH="${FKSKILL_BRANCH:-main}"
SKILLS_ROOT="${WORKBUDDY_SKILLS_DIR:-$HOME/.workbuddy/skills}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_SKILLS="${REPO_DIR}/skills"

MODE_LINK=0
FORCE=0
CMD=""
TARGET=""
TMP_DIR=""
FETCH_SOURCE="${FKSKILL_FETCH_SOURCE:-auto}"
case "${FETCH_SOURCE}" in
  auto|raw|api) ;;
  *) printf '错误：FKSKILL_FETCH_SOURCE 只能是 auto / raw / api\n' >&2; exit 1 ;;
esac

log() { printf '%s\n' "$*"; }
die() { printf '错误：%s\n' "$*" >&2; exit 1; }

cleanup() {
  if [ -n "${TMP_DIR}" ] && [ -d "${TMP_DIR}" ]; then
    rm -rf "${TMP_DIR}"
  fi
}
trap cleanup EXIT

usage() {
  cat <<'EOF'
FKskill 安装器

  ./install.sh --list                 查看仓库内技能与本机安装状态
  ./install.sh --all                  安装仓库内全部技能（含 fkskill 总览，复制）
  ./install.sh --only <name>          只安装仓库里已有的某一个技能
  ./install.sh --fetch <name>         不 clone 仓库，直接从 GitHub 下载并只装这一个技能

可选参数：
  --link       改为软链安装（仅 --all / --only；改仓库即时生效）
  --force      目标已存在时先备份到 .backup/ 再覆盖

环境变量：
  FKSKILL_OWNER / FKSKILL_REPO / FKSKILL_BRANCH   远程仓库与分支
  FKSKILL_FETCH_SOURCE                             auto(默认) / raw / api，--fetch 下载通道
  WORKBUDDY_SKILLS_DIR                             安装目录（默认 ~/.workbuddy/skills）

示例：
  ./install.sh --all
  ./install.sh --only tuntun-forum
  bash install.sh --fetch tuntun-forum
  FKSKILL_FETCH_SOURCE=api bash install.sh --fetch tuntun-forum

单装的子技能不依赖其他技能目录；--fetch 需要 curl 与 python3，且要求目标技能已推送到远程 main 分支。raw 通道不可达时自动改用 GitHub contents API（国内网络常见）。
EOF
}

valid_name() {
  [[ "$1" =~ ^[a-z0-9][a-z0-9-]*$ ]]
}

install_from() {
  local name="$1" src="$2" dest backup
  valid_name "${name}" || die "非法技能名：${name}（只允许小写字母、数字、连字符）"
  [ -f "${src}/SKILL.md" ] || die "源目录缺少 SKILL.md：${src}"
  mkdir -p "${SKILLS_ROOT}"
  dest="${SKILLS_ROOT}/${name}"
  if [ -e "${dest}" ] || [ -L "${dest}" ]; then
    if [ "${FORCE}" -eq 1 ]; then
      backup="${SKILLS_ROOT}/.backup/${name}-$(date +%Y%m%d-%H%M%S)"
      mkdir -p "$(dirname "${backup}")"
      mv "${dest}" "${backup}"
      log "  已备份旧版本 → ${backup}"
    else
      log "  跳过 ${name}：目标已存在（${dest}）。加 --force 可覆盖。"
      return 0
    fi
  fi
  if [ "${MODE_LINK}" -eq 1 ]; then
    ln -s "${src}" "${dest}"
  else
    cp -R "${src}" "${dest}"
  fi
  log "  已安装 ${name} → ${dest}"
}

list_skills() {
  local d name
  log "仓库内技能（${LOCAL_SKILLS}）："
  if [ -d "${LOCAL_SKILLS}" ]; then
    for d in "${LOCAL_SKILLS}"/*/; do
      [ -d "${d}" ] || continue
      name="$(basename "${d}")"
      if [ -e "${SKILLS_ROOT}/${name}" ]; then
        log "  ${name}   [本机已安装]"
      else
        log "  ${name}   [未安装]"
      fi
    done
  else
    log "  （未找到 skills/ 目录，当前目录不是完整仓库；可用 --fetch 下载单个技能）"
  fi
}

do_all() {
  local d name count=0
  [ -d "${LOCAL_SKILLS}" ] || die "未找到 ${LOCAL_SKILLS}，请先 clone 完整仓库，或改用 --fetch <name>"
  for d in "${LOCAL_SKILLS}"/*/; do
    [ -d "${d}" ] || continue
    name="$(basename "${d}")"
    install_from "${name}" "${d}"
    count=$((count + 1))
  done
  [ "${count}" -gt 0 ] || die "skills/ 下没有技能目录"
  log "完成，共处理 ${count} 个技能。"
}

do_only() {
  local name="$1" src
  [ -n "${name}" ] || die "--only 需要技能名"
  valid_name "${name}" || die "非法技能名：${name}"
  src="${LOCAL_SKILLS}/${name}"
  [ -d "${src}" ] || die "仓库里没有 skills/${name}/；想从远程下载请用 --fetch ${name}"
  install_from "${name}" "${src}"
}

fetch_file() {
  local path="$1" dest="$2" raw_url api_url tmpjson
  if [ "${FETCH_SOURCE}" = "raw" ] || [ "${FETCH_SOURCE}" = "auto" ]; then
    raw_url="https://raw.githubusercontent.com/${OWNER}/${REPO}/${BRANCH}/${path}"
    if curl -fsSL --connect-timeout 5 --max-time 15 "${raw_url}" -o "${dest}" 2>/dev/null; then
      FETCH_SOURCE="raw"
      return 0
    fi
  fi
  if [ "${FETCH_SOURCE}" = "auto" ]; then
    log "  raw 通道不可达，自动改用 GitHub contents API 下载。"
    FETCH_SOURCE="api"
  fi
  api_url="https://api.github.com/repos/${OWNER}/${REPO}/contents/${path}?ref=${BRANCH}"
  tmpjson="${dest}.__json"
  if ! curl -fsSL --connect-timeout 8 --max-time 25 -H "Accept: application/vnd.github+json" \
       "${api_url}" -o "${tmpjson}" 2>/dev/null; then
    rm -f "${tmpjson}"
    return 1
  fi
  if python3 -c 'import base64,json,sys; d=json.load(open(sys.argv[1],encoding="utf-8")); c=d.get("content"); assert d.get("encoding")=="base64" and isinstance(c,str); open(sys.argv[2],"wb").write(base64.b64decode("".join(c.split())))' "${tmpjson}" "${dest}" 2>/dev/null; then
    rm -f "${tmpjson}"
    return 0
  fi
  rm -f "${tmpjson}"
  return 1
}

do_fetch() {
  local name="$1" api paths count=0 path rel dest
  [ -n "${name}" ] || die "--fetch 需要技能名"
  valid_name "${name}" || die "非法技能名：${name}"
  command -v curl >/dev/null 2>&1 || die "需要 curl"
  command -v python3 >/dev/null 2>&1 || die "需要 python3"
  if [ "${MODE_LINK}" -eq 1 ]; then
    log "  提示：--fetch 下载的是临时副本，自动改用复制安装。"
    MODE_LINK=0
  fi
  TMP_DIR="$(mktemp -d)"
  api="https://api.github.com/repos/${OWNER}/${REPO}/git/trees/${BRANCH}?recursive=1"
  curl -fsSL --connect-timeout 8 --max-time 25 -H "Accept: application/vnd.github+json" "${api}" -o "${TMP_DIR}/tree.json" \
    || die "拉取仓库文件列表失败（检查 OWNER/REPO/BRANCH、网络或 API 限频）"
  paths="${TMP_DIR}/paths.txt"
  python3 - "${TMP_DIR}/tree.json" "${name}" > "${paths}" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as f:
    tree = json.load(f)
name = sys.argv[2]
prefix = "skills/" + name + "/"
if tree.get("truncated"):
    sys.stderr.write("警告：GitHub 文件树被截断，可能漏文件\n")
for item in tree.get("tree", []):
    p = item.get("path", "")
    if item.get("type") == "blob" and p.startswith(prefix):
        print(p)
PY
  while IFS= read -r path; do
    [ -n "${path}" ] || continue
    rel="${path#skills/${name}/}"
    dest="${TMP_DIR}/skill/${rel}"
    mkdir -p "$(dirname "${dest}")"
    fetch_file "${path}" "${dest}" || die "下载失败：${path}"
    count=$((count + 1))
  done < "${paths}"
  [ "${count}" -gt 0 ] || die "仓库里没有找到 skills/${name}/（检查技能名与分支）"
  [ -f "${TMP_DIR}/skill/SKILL.md" ] || die "下载内容缺少 SKILL.md，安装中止"
  find "${TMP_DIR}/skill" -type f -name "*.py" -exec chmod +x {} \; 2>/dev/null || true
  log "  已下载 ${count} 个文件（skills/${name}/）"
  install_from "${name}" "${TMP_DIR}/skill"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --all) CMD="all"; shift ;;
    --only) CMD="only"; TARGET="${2:-}"; shift 2 ;;
    --fetch) CMD="fetch"; TARGET="${2:-}"; shift 2 ;;
    --list) CMD="list"; shift ;;
    --link) MODE_LINK=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "未知参数：${1}（用 --help 查看用法）" ;;
  esac
done

[ -n "${CMD}" ] || { usage; exit 1; }

case "${CMD}" in
  list) list_skills ;;
  all) do_all ;;
  only) do_only "${TARGET}" ;;
  fetch) do_fetch "${TARGET}" ;;
esac
