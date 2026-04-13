#!/usr/bin/env python3
"""
Genera branch-cleanup.html dinamicamente consultando la API de GitHub
para todas las ramas de todos los repos de la organizacion GoEcosystemDH.

Clasificacion:
- MANTENER: rama default del repo, o < UMBRAL_DIAS de actividad, o en WHITELIST_BRANCHES
- ELIMINAR: >= UMBRAL_DIAS sin actividad AND (naming invalido OR 0 commits ahead del default)
- REVISAR:  >= UMBRAL_DIAS sin actividad, naming valido, con commits ahead o PR abierto

Requiere:
- env GH_TOKEN con permisos read de todos los repos de la org
- Python 3.9+
- gh CLI disponible
"""
import os, re, json, subprocess, sys, datetime, html, time
from collections import Counter

ORG = 'GoEcosystemDH'
UMBRAL_DIAS = 90
WHITELIST_BRANCHES = {
    'main', 'master', 'develop', 'release', 'production', 'staging', 'qa',
    'new_template', 'clinica-central-del-eje',
    'Alejandro-ParticionCuentas', 'Alejandro-ParticionCuentass',
    'estiven/feature/cambios_hemocomponente_hila_6506',
    'estiven/feature/contrasenias_seguras',
    'licenciaAMS', 'ultima_version_todos_los_cambios',
}
NAMING_VALID_PREFIXES = (
    'feature/', 'fix/', 'hotfix/', 'bugfix/', 'chore/', 'docs/', 'refactor/',
    'test/', 'release/', 'dependabot/', 'renovate/', 'ci/', 'perf/',
)
TICKET_PATTERN = re.compile(r'^\d+[_-]')
DATE_TODAY = datetime.date.today()
DATE_STR_UTC = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M')

def gh(*args, paginate=False):
    cmd = ['gh','api']
    if paginate:
        cmd.append('--paginate')
    cmd += list(args)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"gh api failed: {' '.join(args)}\n{r.stderr}")
    out = r.stdout.strip()
    if paginate and out:
        parts = []
        depth = 0
        buf = ''
        for ch in out:
            buf += ch
            if ch == '[': depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    try: parts.extend(json.loads(buf.strip()))
                    except: pass
                    buf = ''
        return parts
    return json.loads(out) if out else {}

def is_valid_naming(branch: str) -> bool:
    if branch in WHITELIST_BRANCHES: return True
    if branch.startswith(NAMING_VALID_PREFIXES): return True
    if TICKET_PATTERN.match(branch): return True
    return False

def days_since(iso_date: str) -> int:
    try:
        d = datetime.datetime.fromisoformat(iso_date.replace('Z','+00:00')).date()
        return (DATE_TODAY - d).days
    except Exception:
        return 0

def list_org_repos():
    print(f'[1/3] Listando repos de {ORG}...', flush=True)
    repos = gh(f'orgs/{ORG}/repos?per_page=100', paginate=True)
    repos = [r for r in repos if not r.get('archived') and not r.get('disabled')]
    print(f'      {len(repos)} repos activos', flush=True)
    return repos

def analyze_repo(repo):
    name = repo['name']
    default = repo.get('default_branch') or 'main'
    try:
        branches = gh(f'repos/{ORG}/{name}/branches?per_page=100', paginate=True)
    except Exception as e:
        print(f'  WARN {name}: {e}', flush=True)
        return []
    results = []
    for b in branches:
        br_name = b['name']
        sha = b.get('commit', {}).get('sha', '')
        # Get commit info
        try:
            commit = gh(f'repos/{ORG}/{name}/commits/{sha}')
            cd = commit.get('commit', {}).get('committer', {}).get('date', '')
            author = commit.get('commit', {}).get('author', {}).get('name', '') or \
                     (commit.get('author') or {}).get('login', '') or '—'
        except Exception:
            cd = ''
            author = '—'
        days = days_since(cd) if cd else 0
        last_date = cd.split('T')[0] if cd else '—'

        is_default = (br_name == default)
        ahead = 0
        prs_open = 0

        if not is_default:
            # compare for ahead count
            try:
                cmp = gh(f'repos/{ORG}/{name}/compare/{default}...{br_name}')
                ahead = cmp.get('ahead_by', 0)
            except Exception:
                ahead = 0
            # open PRs from this branch
            try:
                prs = gh(f'repos/{ORG}/{name}/pulls?head={ORG}:{br_name}&state=open&per_page=5')
                prs_open = len(prs) if isinstance(prs, list) else 0
            except Exception:
                prs_open = 0

        # Classification
        if is_default or br_name in WHITELIST_BRANCHES:
            accion = 'MANTENER'
            razon = 'Rama por defecto o whitelist' if is_default else 'En whitelist de proteccion'
        elif days < UMBRAL_DIAS:
            accion = 'MANTENER'
            razon = f'Actividad reciente ({days}d < {UMBRAL_DIAS}d)'
        elif not is_valid_naming(br_name):
            accion = 'ELIMINAR'
            razon = f'Sin actividad {days}d (>= {UMBRAL_DIAS}d) + naming incorrecto'
        elif ahead == 0:
            accion = 'ELIMINAR'
            razon = f'Sin actividad {days}d + 0 commits ahead de {default} (merged)'
        elif prs_open > 0:
            accion = 'REVISAR'
            razon = f'Sin actividad {days}d pero con {prs_open} PR abierto(s)'
        else:
            accion = 'REVISAR'
            razon = f'Sin actividad {days}d + {ahead} commits sin merge'

        results.append({
            'repo': name, 'branch': br_name, 'sha': sha[:40],
            'last_commit': last_date, 'days': days, 'author': author,
            'prs': prs_open, 'ahead': ahead, 'naming_ok': is_valid_naming(br_name),
            'default': default, 'accion': accion, 'razon': razon,
        })
    return results

def build_html(all_branches, deleted_history):
    by_accion = {'ELIMINAR': [], 'REVISAR': [], 'MANTENER': []}
    for b in all_branches:
        by_accion[b['accion']].append(b)

    stats = {
        'ELIMINAR': len(by_accion['ELIMINAR']),
        'REVISAR': len(by_accion['REVISAR']),
        'MANTENER': len(by_accion['MANTENER']),
        'TOTAL': len(all_branches),
        'REPOS': len({b['repo'] for b in all_branches}),
        'WITH_PR': sum(1 for b in all_branches if b['prs'] > 0),
        'WITH_AHEAD': sum(1 for b in all_branches if b['ahead'] > 0),
    }
    repos_list = sorted({b['repo'] for b in all_branches})

    def badge_naming(ok):
        return '<span class="badge b-ok">OK</span>' if ok else '<span class="badge b-bad">Naming</span>'

    def render_row(b, tab):
        repo, br = b['repo'], b['branch']
        key = f'{repo}::{br}'
        row_id = re.sub(r'[^a-zA-Z0-9]','_', key)
        btn = ''
        if tab == 'revisar':
            btn = (f'<td><button class="btn-confirm" data-key="{html.escape(key)}" '
                   f'onclick="toggleConfirm(this)" id="btn_{row_id}">Confirmar</button></td>')
        return (
            f'<tr data-repo="{html.escape(repo)}" data-branch="{html.escape(br)}" data-accion="{b["accion"]}">'
            f'<td><a href="https://github.com/{ORG}/{repo}" target="_blank">{repo}</a></td>'
            f'<td><code>{html.escape(br)}</code></td>'
            f'<td>{b["last_commit"]}</td>'
            f'<td class="num">{b["days"]}d</td>'
            f'<td>{html.escape(b["author"])}</td>'
            f'<td>{b["prs"] or "—"}</td>'
            f'<td>{b["ahead"] or "—"}</td>'
            f'<td>{badge_naming(b["naming_ok"])}</td>'
            f'<td>{html.escape(b["razon"])}</td>'
            f'<td><a href="https://github.com/{ORG}/{repo}/tree/{br}" target="_blank" class="btn-view">Ver</a>'
            f'<a href="https://github.com/{ORG}/{repo}/compare/{b["default"]}...{br}" target="_blank" class="btn-compare">Diff</a></td>'
            f'{btn}</tr>'
        )

    def tbody(tab, rows, with_confirm=False):
        return '\n'.join(render_row(b, tab) for b in rows)

    headers_basic = '''<th onclick="sortTable(this)">Repositorio</th>
        <th onclick="sortTable(this)">Rama</th>
        <th onclick="sortTable(this)">Ultimo Commit</th>
        <th onclick="sortTable(this)">Dias</th>
        <th>Autor</th><th>PRs</th><th>Sin Merge</th>
        <th>Naming</th><th>Razon</th><th>Links</th>'''

    headers_revisar = headers_basic + '<th>Confirmar</th>'

    # Deleted history (from data/deleted-branches.json)
    del_rows = []
    for d in deleted_history:
        if d.get('status') != 'DELETED': continue
        del_rows.append(
            f'<tr data-repo="{html.escape(d["repo"])}">'
            f'<td><a href="https://github.com/{ORG}/{d["repo"]}" target="_blank">{d["repo"]}</a></td>'
            f'<td><code>{html.escape(d["branch"])}</code></td>'
            f'<td>{d.get("last_commit","—")}</td>'
            f'<td class="num">{d.get("days","—")}</td>'
            f'<td>{html.escape(d.get("author","—"))}</td>'
            f'<td>{html.escape(d.get("reason","—"))}</td>'
            f'<td><code>{(d.get("sha") or "—")[:7]}</code></td>'
            f'<td>{d.get("deleted_at","—")}</td>'
            f'<td><span class="badge b-ok">DELETED</span></td></tr>'
        )

    repo_options = ''.join(f'<option value="{r}">{r}</option>' for r in repos_list)

    return f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Branch Cleanup — GoEcosystemDH</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f6f8fa;color:#24292e;font-size:13px}}
header{{background:#24292e;color:#fff;padding:18px 28px;display:flex;justify-content:space-between;align-items:center}}
header h1{{font-size:20px}} header p{{font-size:12px;color:#8b949e;margin-top:3px}}
.stats{{display:flex;gap:12px;padding:16px 28px;flex-wrap:wrap}}
.stat{{background:#fff;border:1px solid #d0d7de;border-radius:8px;padding:12px 20px;min-width:130px}}
.stat .num{{font-size:28px;font-weight:700}} .stat .lbl{{font-size:11px;color:#57606a;margin-top:2px}}
.stat.red .num{{color:#cf222e}} .stat.yellow .num{{color:#9a6700}}
.stat.green .num{{color:#1a7f37}} .stat.blue .num{{color:#0969da}} .stat.purple .num{{color:#8250df}}
.tabs{{display:flex;gap:0;padding:0 28px;border-bottom:1px solid #d0d7de;background:#fff}}
.tab{{padding:10px 18px;cursor:pointer;border-bottom:2px solid transparent;font-size:13px;font-weight:500;color:#57606a;user-select:none}}
.tab:hover{{color:#24292e;background:#f6f8fa}}
.tab.active{{color:#24292e;border-bottom-color:#fd8c73}}
.tab .cnt{{display:inline-block;background:#eee;border-radius:20px;padding:1px 7px;font-size:11px;margin-left:5px}}
.tab.t-eliminar .cnt{{background:#ffcdd2;color:#cf222e}}
.tab.t-revisar .cnt{{background:#fff3cd;color:#9a6700}}
.tab.t-mantener .cnt{{background:#c8e6c9;color:#1a7f37}}
.tab.t-eliminadas .cnt{{background:#d1f0d9;color:#1a7f37}}
.controls{{padding:10px 28px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;background:#f6f8fa;border-bottom:1px solid #d0d7de}}
.controls input{{border:1px solid #d0d7de;border-radius:6px;padding:7px 11px;font-size:13px;width:260px}}
.controls select{{border:1px solid #d0d7de;border-radius:6px;padding:7px 11px;font-size:13px}}
.controls button.primary{{background:#1a7f37;color:#fff;border:none;border-radius:6px;padding:8px 14px;font-size:13px;cursor:pointer;font-weight:600}}
.controls button.primary:hover{{background:#166b2c}}
.controls button.primary:disabled{{background:#b3b3b3;cursor:not-allowed}}
.count-lbl{{font-size:12px;color:#57606a;margin-left:auto}}
.panel{{display:none;padding:0 28px 28px}} .panel.active{{display:block}}
.table-wrap{{overflow-x:auto;margin-top:12px}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;border:1px solid #d0d7de}}
th{{background:#f6f8fa;padding:9px 10px;text-align:left;font-weight:600;border-bottom:1px solid #d0d7de;cursor:pointer;white-space:nowrap;user-select:none}}
th:hover{{background:#eaeef2}} th.sorted-asc::after{{content:" ▲";font-size:10px}} th.sorted-desc::after{{content:" ▼";font-size:10px}}
td{{padding:7px 10px;border-bottom:1px solid #f0f0f0;vertical-align:middle}}
tr:hover td{{background:#f6f8fa}}
tr[data-accion="ELIMINAR"] td{{background:#fff5f5}} tr[data-accion="REVISAR"] td{{background:#fffdf0}} tr[data-accion="MANTENER"] td{{background:#f0fff4}}
tr.confirmed td{{background:#d1f0d9 !important}}
code{{background:#f6f8fa;border:1px solid #d0d7de;border-radius:4px;padding:1px 5px;font-size:11px}}
.num{{text-align:right}}
.badge{{border-radius:4px;padding:2px 6px;font-size:10px;font-weight:700;white-space:nowrap}}
.b-ok{{background:#c8e6c9;color:#1a7f37}} .b-bad{{background:#ffcdd2;color:#cf222e}}
a.btn-view,a.btn-compare,button.btn-confirm{{font-size:11px;padding:3px 8px;border-radius:5px;text-decoration:none;display:inline-block;margin-right:4px;border:none;cursor:pointer;font-family:inherit}}
a.btn-view{{background:#0969da;color:#fff}} a.btn-compare{{background:#6e7781;color:#fff}}
a.btn-view:hover{{background:#0550ae}} a.btn-compare:hover{{background:#57606a}}
button.btn-confirm{{background:#f3f4f6;color:#24292e;border:1px solid #d0d7de}}
button.btn-confirm.confirmed{{background:#1a7f37;color:#fff;border-color:#166b2c}}
footer{{padding:16px 28px;font-size:11px;color:#57606a;border-top:1px solid #d0d7de;background:#fff}}
</style>
</head>
<body>

<header>
<div>
  <h1>GoEcosystemDH — Branch Cleanup</h1>
  <p>Auditoria DevSecOps (dinamica) · Generado {DATE_STR_UTC} UTC · Umbral: {UMBRAL_DIAS} dias</p>
</div>
<div style="text-align:right;font-size:12px;color:#8b949e">
  Datos en vivo desde GitHub API<br><strong style="color:#8ae68a">regeneracion automatica cada 6h</strong>
</div>
</header>

<div class="stats">
<div class="stat red"><div class="num">{stats['ELIMINAR']}</div><div class="lbl">ELIMINAR</div></div>
<div class="stat yellow"><div class="num">{stats['REVISAR']}</div><div class="lbl">REVISAR</div></div>
<div class="stat green"><div class="num">{stats['MANTENER']}</div><div class="lbl">MANTENER</div></div>
<div class="stat blue"><div class="num">{stats['TOTAL']}</div><div class="lbl">Total ramas</div></div>
<div class="stat purple"><div class="num">{stats['REPOS']}</div><div class="lbl">Repos</div></div>
<div class="stat"><div class="num" style="color:#cf222e">{stats['WITH_PR']}</div><div class="lbl">Con PR abierto</div></div>
<div class="stat"><div class="num" style="color:#9a6700">{stats['WITH_AHEAD']}</div><div class="lbl">Con commits sin merge</div></div>
</div>

<div class="tabs">
<div class="tab t-eliminar active" onclick="showTab('eliminar')">ELIMINAR <span class="cnt">{stats['ELIMINAR']}</span></div>
<div class="tab t-revisar" onclick="showTab('revisar')">REVISAR <span class="cnt">{stats['REVISAR']}</span></div>
<div class="tab t-mantener" onclick="showTab('mantener')">MANTENER <span class="cnt">{stats['MANTENER']}</span></div>
<div class="tab" onclick="showTab('todos')">TODOS <span class="cnt">{stats['TOTAL']}</span></div>
<div class="tab t-eliminadas" onclick="showTab('eliminadas')">ELIMINADAS <span class="cnt">{sum(1 for d in deleted_history if d.get('status')=='DELETED')}</span></div>
</div>

<div class="controls">
<input type="text" id="search" placeholder="Filtrar por repo o rama..." oninput="filterTable()">
<select id="repoFilter" onchange="filterTable()">
  <option value="">Todos los repos</option>
  {repo_options}
</select>
<button id="btnDownload" class="primary" onclick="downloadConfirmed()" disabled>Descargar confirmadas (0)</button>
<button onclick="clearConfirmed()" style="background:#fff;border:1px solid #d0d7de;border-radius:6px;padding:8px 14px;font-size:13px;cursor:pointer">Limpiar marcas</button>
<span class="count-lbl" id="countLabel"></span>
</div>

<div class="panel active" id="panel-eliminar"><div class="table-wrap"><table>
<thead><tr>{headers_basic}</tr></thead>
<tbody id="tbody-eliminar">{tbody('eliminar', by_accion['ELIMINAR'])}</tbody>
</table></div></div>

<div class="panel" id="panel-revisar"><div class="table-wrap"><table>
<thead><tr>{headers_revisar}</tr></thead>
<tbody id="tbody-revisar">{tbody('revisar', by_accion['REVISAR'])}</tbody>
</table></div></div>

<div class="panel" id="panel-mantener"><div class="table-wrap"><table>
<thead><tr>{headers_basic}</tr></thead>
<tbody id="tbody-mantener">{tbody('mantener', by_accion['MANTENER'])}</tbody>
</table></div></div>

<div class="panel" id="panel-todos"><div class="table-wrap"><table>
<thead><tr>{headers_basic}</tr></thead>
<tbody id="tbody-todos">{tbody('todos', all_branches)}</tbody>
</table></div></div>

<div class="panel" id="panel-eliminadas"><div class="table-wrap"><table>
<thead><tr>
<th onclick="sortTable(this)">Repositorio</th>
<th onclick="sortTable(this)">Rama</th>
<th>Ultimo Commit</th>
<th>Dias</th>
<th>Autor</th>
<th>Razon</th>
<th>SHA (recovery)</th>
<th>Eliminado en (UTC)</th>
<th>Estado</th>
</tr></thead>
<tbody id="tbody-eliminadas">{chr(10).join(del_rows)}</tbody>
</table></div></div>

<footer>
Generado automaticamente por <code>scripts/generate_branch_cleanup.py</code> via GitHub Actions.
Las marcas de confirmacion se guardan en tu navegador (localStorage) y no se comparten.
</footer>

<script>
const TABS = ['eliminar','revisar','mantener','todos','eliminadas'];
const LS_KEY = 'branch-cleanup-confirmed';

function getConfirmed() {{
  try {{ return JSON.parse(localStorage.getItem(LS_KEY) || '[]'); }}
  catch {{ return []; }}
}}
function setConfirmed(list) {{
  localStorage.setItem(LS_KEY, JSON.stringify(list));
  updateDownloadBtn();
}}
function updateDownloadBtn() {{
  const list = getConfirmed();
  const btn = document.getElementById('btnDownload');
  btn.textContent = `Descargar confirmadas (${{list.length}})`;
  btn.disabled = list.length === 0;
}}

function showTab(name) {{
  TABS.forEach((t, i) => {{
    document.getElementById('panel-'+t).classList.remove('active');
    document.querySelectorAll('.tab')[i].classList.remove('active');
  }});
  document.getElementById('panel-'+name).classList.add('active');
  document.querySelectorAll('.tab')[TABS.indexOf(name)].classList.add('active');
  filterTable();
}}
function activePanel() {{ return TABS.find(t => document.getElementById('panel-'+t).classList.contains('active')); }}

function filterTable() {{
  const q = document.getElementById('search').value.toLowerCase();
  const repo = document.getElementById('repoFilter').value;
  const tb = document.getElementById('tbody-'+activePanel());
  if (!tb) return;
  let shown = 0;
  tb.querySelectorAll('tr').forEach(tr => {{
    const txt = tr.textContent.toLowerCase();
    const trRepo = tr.getAttribute('data-repo') || '';
    const ok = (q === '' || txt.includes(q)) && (repo === '' || trRepo === repo);
    tr.style.display = ok ? '' : 'none';
    if (ok) shown++;
  }});
  document.getElementById('countLabel').textContent = `Mostrando ${{shown}} filas`;
}}

function sortTable(th) {{
  const table = th.closest('table');
  const tbody = table.querySelector('tbody');
  const idx = Array.from(th.parentNode.children).indexOf(th);
  const asc = !th.classList.contains('sorted-asc');
  Array.from(table.querySelectorAll('th')).forEach(h => h.classList.remove('sorted-asc','sorted-desc'));
  th.classList.add(asc ? 'sorted-asc' : 'sorted-desc');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  rows.sort((a, b) => {{
    let A = a.children[idx].textContent.trim();
    let B = b.children[idx].textContent.trim();
    const nA = parseFloat(A), nB = parseFloat(B);
    if (!isNaN(nA) && !isNaN(nB)) return asc ? nA-nB : nB-nA;
    return asc ? A.localeCompare(B) : B.localeCompare(A);
  }});
  rows.forEach(r => tbody.appendChild(r));
}}

function toggleConfirm(btn) {{
  const key = btn.getAttribute('data-key');
  const [repo, branch] = key.split('::');
  let list = getConfirmed();
  const i = list.findIndex(x => x.repo === repo && x.branch === branch);
  const tr = btn.closest('tr');
  if (i >= 0) {{
    list.splice(i, 1);
    btn.classList.remove('confirmed');
    btn.textContent = 'Confirmar';
    tr.classList.remove('confirmed');
  }} else {{
    list.push({{repo, branch, confirmed_at: new Date().toISOString()}});
    btn.classList.add('confirmed');
    btn.textContent = '✓ Confirmada';
    tr.classList.add('confirmed');
  }}
  setConfirmed(list);
}}

function clearConfirmed() {{
  if (!confirm('Borrar todas las marcas de confirmacion?')) return;
  setConfirmed([]);
  document.querySelectorAll('button.btn-confirm.confirmed').forEach(b => {{
    b.classList.remove('confirmed');
    b.textContent = 'Confirmar';
    b.closest('tr').classList.remove('confirmed');
  }});
}}

function downloadConfirmed() {{
  const list = getConfirmed();
  if (!list.length) return;
  const ts = new Date().toISOString().replace(/[:.]/g,'-');
  const data = {{
    generated_at: new Date().toISOString(),
    org: '{ORG}',
    count: list.length,
    branches: list,
  }};
  const blob = new Blob([JSON.stringify(data, null, 2)], {{type: 'application/json'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `confirmed-branches-${{ts}}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}}

// Restore confirmation state on load
document.addEventListener('DOMContentLoaded', () => {{
  const list = getConfirmed();
  list.forEach(({{repo, branch}}) => {{
    const key = `${{repo}}::${{branch}}`;
    const btn = document.querySelector(`button.btn-confirm[data-key="${{key}}"]`);
    if (btn) {{
      btn.classList.add('confirmed');
      btn.textContent = '✓ Confirmada';
      btn.closest('tr').classList.add('confirmed');
    }}
  }});
  updateDownloadBtn();
  filterTable();
}});
</script>
</body>
</html>
'''

def main():
    deleted_history = []
    dhp = 'data/deleted-branches.json'
    if os.path.exists(dhp):
        try: deleted_history = json.load(open(dhp))
        except: deleted_history = []

    repos = list_org_repos()
    print(f'[2/3] Analizando ramas (UMBRAL={UMBRAL_DIAS}d)...', flush=True)
    all_branches = []
    for i, r in enumerate(repos, 1):
        print(f'  ({i}/{len(repos)}) {r["name"]}', flush=True)
        all_branches.extend(analyze_repo(r))

    print(f'[3/3] Generando HTML ({len(all_branches)} ramas)...', flush=True)
    h = build_html(all_branches, deleted_history)
    open('branch-cleanup.html','w').write(h)
    by = Counter(b['accion'] for b in all_branches)
    print(f'  ELIMINAR={by["ELIMINAR"]} REVISAR={by["REVISAR"]} MANTENER={by["MANTENER"]}')
    print('Done: branch-cleanup.html')

if __name__ == '__main__':
    main()
