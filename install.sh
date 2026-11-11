#!/usr/bin/env bash
# FKskill 安装器：把 skills/ 下的独立技能装到 WorkBuddy 用户级技能目录。
# 只创建/复制文件，不删除用户已有技能；覆盖前会先备份。
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
  WORKBUDDY_SKILLS_DIR                             安装目录（默认 ~/.workbuddy/skills）

示例：
  ./install.sh --all
  ./install.sh --only tuntun-forum
  bash install.sh --fetch tuntun-forum

单装的子技能不依赖其他技能目录；--fetch 需要 curl 与 python3，且要求目标技能已推送到远程 main 分支。
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
  curl -fsSL "${api}" -o "${TMP_DIR}/tree.json" \
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
    curl -fsSL "https://raw.githubusercontent.com/${OWNER}/${REPO}/${BRANCH}/${path}" -o "${dest}" \
      || die "下载失败：${path}"
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
