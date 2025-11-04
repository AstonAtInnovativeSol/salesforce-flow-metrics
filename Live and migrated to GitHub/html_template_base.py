#!/usr/bin/env python3
"""
HTML Template Base - Reusable HTML generation using touchpoint7.html style
Used by BocaSalesMotion2.py and pipev3.py for HTML dashboard generation
"""

from datetime import datetime, date, timedelta
from pathlib import Path
import json


def get_touchpoint7_styles():
    """Get CSS styles from touchpoint7.html"""
    return """
  :root{
    --bg:#ffffff;--ink:#101418;--muted:#6b7280;--line:#e5e7eb;--panel:#fafafa;
    --brand:#4b7bec; --brand-2:#6b5af9; --accent:#f8fafc; --border:#e2e8f0;
    --glass: rgba(255,255,255,.65);
  }
  *{box-sizing:border-box}
  html,body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 -apple-system,BlinkMacSystemFont,Inter,Segoe UI,Roboto,Helvetica,Arial,sans-serif}

  .wrap{max-width:1400px;margin:0 auto;padding:24px;width:100%}

  .hdr{
    position:sticky;top:0;z-index:20;backdrop-filter:saturate(180%) blur(8px);
    background:linear-gradient(180deg,rgba(255,255,255,.92),rgba(255,255,255,.86) 60%,rgba(255,255,255,.70));
    border-bottom:1px solid var(--line); padding:12px 24px; margin:0 -24px 12px;
  }
  .hdr-inner{display:flex;gap:18px;align-items:flex-start;justify-content:space-between}
  .kicker{letter-spacing:.22em;text-transform:uppercase;color:var(--muted);font-weight:700;font-size:12px}
  .title{font-size:24px;font-weight:800;line-height:1.1;margin:4px 0 3px}
  .subtitle{color:var(--muted);font-size:13px;max-width:960px;line-height:1.4}

  /* ---------- Data Lineage Capsule ---------- */
  .lineage{
    --g1:#6b5af9; --g2:#4b7bec;
    position:relative; isolation:isolate;
    border-radius:14px; padding:12px 14px;
    background: var(--glass);
    backdrop-filter: blur(10px) saturate(130%);
    box-shadow: 0 8px 20px rgba(16,24,40,.08), inset 0 1px 0 rgba(255,255,255,.4);
  }
  .lineage::before{
    content:""; position:absolute; inset:0; border-radius:14px;
    padding:1px; background:linear-gradient(135deg, var(--g1), var(--g2));
    -webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);
    -webkit-mask-composite:xor; mask-composite: exclude;
    pointer-events:none;
  }
  .lineage-head{
    display:flex; align-items:center; justify-content:space-between; gap:10px;
  }
  .lineage-title{
    font-size:11px; letter-spacing:.14em; text-transform:uppercase;
    color:#7c8aa5; font-weight:800;
  }
  .lineage-cta{
    border:1px solid rgba(98,113,255,.25); background:#fff; color:#334155;
    border-radius:999px; padding:6px 10px; font-size:12px; font-weight:700; cursor:pointer;
    transition:.18s; box-shadow:0 1px 2px rgba(0,0,0,.06);
  }
  .lineage-cta:hover{transform:translateY(-1px); box-shadow:0 3px 8px rgba(0,0,0,.10)}
  .sources{
    display:flex; gap:14px; align-items:center; flex-wrap:wrap; margin-top:8px;
  }
  .source{
    display:flex; align-items:center; gap:8px; padding:8px 10px; border-radius:10px;
    background:#fff; border:1px solid var(--border); box-shadow:0 1px 2px rgba(0,0,0,.04);
    transition:.2s;
  }
  .source:hover{transform:translateY(-1px); box-shadow:0 3px 8px rgba(0,0,0,.10); border-color:#c7cff6}
  .glyph{
    width:18px; height:18px; display:inline-block; opacity:.85;
    transition:opacity .2s, transform .2s, filter .2s;
  }
  .source:hover .glyph{opacity:1; filter:none; transform:scale(1.04)}
  .src-name{font-size:12px; font-weight:700; color:#2b3441; letter-spacing:.01em; white-space:nowrap}
  .sig{font-size:11px; color:#6b7280}

  /* ---------- Common components ---------- */
  .pill{display:inline-flex;align-items:center;gap:8px;font-size:12px;font-weight:700;border:1px solid #e6eaf5;border-radius:999px;padding:6px 10px;background:#f7f9ff}
  .dot{width:8px;height:8px;border-radius:50%;background:linear-gradient(135deg,var(--brand),var(--brand-2))}
  .bar8{height:8px;border-radius:999px;background:linear-gradient(90deg,var(--brand),var(--brand-2))}
  .tools{display:flex;gap:8px;align-items:center;margin-top:8px;flex-wrap:wrap}
  .input,select{appearance:none;border:1px solid var(--border);border-radius:10px;padding:10px 12px;font-size:14px;background:#fff}
  .btn{border:1px solid var(--border);background:#fff;border-radius:10px;padding:10px 12px;font-size:14px;cursor:pointer}
  .panel{background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:18px;box-shadow:0 1px 3px rgba(0,0,0,.05),0 1px 2px rgba(0,0,0,.08)}
  .callout{display:flex;align-items:center;gap:12px;border-left:4px solid var(--brand);background:linear-gradient(135deg,#f6f9ff,#f0f4ff);border-radius:10px;padding:14px 16px;font-size:14px}
  .callout .strong{font-weight:800}
  .table-container{border-radius:12px;border:1px solid var(--border);box-shadow:0 1px 2px rgba(0,0,0,.05);overflow:hidden}
  table{width:100%;border-collapse:separate;border-spacing:0}
  thead th{position:sticky;top:0;background:#fff;border-bottom:1px solid var(--line);color:#334155;padding:10px 10px;vertical-align:bottom}
  .th{display:flex;flex-direction:column;line-height:1.05;gap:2px}
  .th .h{font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.08em}
  .th .s{font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.08em}
  tbody td{border-bottom:1px solid var(--line);padding:12px 10px;font-size:14px;vertical-align:middle}
  tbody tr:hover{background:var(--accent)}
  .rank{width:40px;text-align:right;color:#6b7280;font-weight:700}
  .company{font-weight:700}
  .owner{color:#374151}
  .right{text-align:right}
  .mono{font-variant-numeric:tabular-nums}
  .heat{display:inline-block;height:18px;min-width:34px;padding:0 8px;border-radius:6px;color:#064e3b;font-weight:700;background:linear-gradient(90deg,#ecfdf5,#bbf7d0)}
  .note{color:#6b7280;font-size:12px;margin-top:8px}
  .foot{display:flex;justify-content:space-between;align-items:center;margin-top:14px;color:#6b7280;font-size:12px}
  .brandmark{font-weight:900;letter-spacing:.08em}
  .sort{cursor:pointer;user-select:none}
  .chip{display:inline-flex;align-items:center;gap:6px;font-size:12px;border:1px solid var(--border);border-radius:999px;padding:6px 10px;background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.05)}
  .kpis{display:flex;gap:12px;flex-wrap:wrap;margin-top:6px}
  .kpi{display:flex;gap:8px;align-items:center;font-size:12px}
  .kpi .swatch{width:9px;height:9px;border-radius:50%;background:#d1fae5}
  @media (max-width:1080px){ .wrap{padding:18px} .title{font-size:22px} .lineage{display:none} .hide-sm{display:none} .th .h{font-size:11px} .th .s{font-size:9px} }
"""


def generate_html_header(title, subtitle, kicker="Sales Ops"):
    """Generate HTML header section matching touchpoint7.html style"""
    return f"""
  <div class="hdr">
    <div class="wrap hdr-inner">
      <div style="flex:1 1 auto;min-width:0">
        <div class="kicker">{kicker}</div>
        <div class="title">{title}</div>
        <div class="subtitle">{subtitle}</div>
      </div>
    </div>
  </div>
"""


def generate_html_table(columns, rows_data, table_id="tbl"):
    """Generate HTML table matching touchpoint7.html style"""
    from html import escape
    
    # Build header
    header_html = "<thead><tr>"
    for col in columns:
        sortable = col.get('sortable', False)
        classes = []
        if sortable:
            classes.append("sort")
        if col.get('align'):
            classes.append(col['align'])
        
        class_attr = f' class="{" ".join(classes)}"' if classes else ""
        label = col["label"].replace("<br>", "<br/>")  # Ensure proper HTML
        header_html += f'<th{class_attr} data-key="{col["key"]}"><div class="th"><span class="h">{label}</span></div></th>'
    header_html += "</tr></thead>"
    
    # Build body
    body_html = "<tbody>"
    for row_data in rows_data:
        body_html += "<tr>"
        for col in columns:
            value = row_data.get(col["key"], "—")
            # Escape HTML but allow <br/> tags
            if isinstance(value, str) and "<br" not in value:
                value = escape(value)
            
            align_class = f' class="{col.get("align", "")}"' if col.get("align") else ""
            body_html += f'<td{align_class}>{value}</td>'
        body_html += "</tr>"
    body_html += "</tbody>"
    
    return f"""
    <div class="table-container">
      <table id="{table_id}" aria-label="{table_id}">
        {header_html}
        {body_html}
      </table>
    </div>
"""


def generate_html_document(title, subtitle, table_html, additional_scripts="", kicker="Sales Ops"):
    """Generate complete HTML document matching touchpoint7.html structure"""
    styles = get_touchpoint7_styles()
    header = generate_html_header(title, subtitle, kicker)
    
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{title}</title>
<style>
{styles}
</style>
</head>
<body>
{header}
<div class="wrap">
  <div class="panel">
    {table_html}
    <div class="foot">
      <div class="note">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
      <div class="brandmark">INNOVATIVE • SALES OPS</div>
    </div>
  </div>
</div>
{additional_scripts}
</body>
</html>
"""


def get_week_key(period_start_date):
    """
    Get a unique week key from a period start date.
    Uses the last_full_week logic: week starts Sunday, ends Saturday.
    Returns YYYY-WW format (e.g., "2025-44" for week 44 of 2025).
    
    Args:
        period_start_date: datetime.date or ISO string (e.g., "2025-11-03")
    
    Returns:
        str: Week key in format "YYYY-WW"
    """
    if isinstance(period_start_date, str):
        period_start_date = date.fromisoformat(period_start_date)
    
    # Find the Sunday of the week containing this date
    # If date is Sunday (weekday=6), use it; otherwise go back to previous Sunday
    days_since_sunday = period_start_date.weekday() + 1  # Monday=0, Sunday=6
    if days_since_sunday == 7:  # It's Sunday
        week_start = period_start_date
    else:
        week_start = period_start_date - timedelta(days=days_since_sunday)
    
    # Get ISO week number
    year, week, _ = week_start.isocalendar()
    return f"{year}-{week:02d}"


def load_json_history(file_path, max_entries=12):
    """Load JSON history file, keeping only last max_entries (one per week)"""
    if not Path(file_path).exists():
        return []
    
    with open(file_path, 'r') as f:
        history = json.load(f)
    
    if not isinstance(history, list):
        return []
    
    # Sort by generated_at (most recent first)
    history.sort(key=lambda x: x.get("generated_at", ""), reverse=True)
    
    # Keep only last max_entries
    return history[:max_entries]


def save_json_history(file_path, data, period_start_date, max_entries=12):
    """
    Save data to JSON history file, week-specific (one entry per week).
    If multiple runs in the same week, keeps only the latest.
    
    Args:
        file_path: Path to JSON file
        data: Data dictionary to save
        period_start_date: datetime.date or ISO string - the start date of the data period
        max_entries: Maximum number of weeks to keep (default 12)
    
    Returns:
        list: Updated history list
    """
    history = load_json_history(file_path, max_entries + 1)
    
    # Get week key for this data period
    week_key = get_week_key(period_start_date)
    
    # Create new entry
    new_entry = {
        "week_key": week_key,
        "period_start": str(period_start_date) if isinstance(period_start_date, date) else period_start_date,
        "generated_at": datetime.now().isoformat(),
        "data": data
    }
    
    # Remove any existing entry for this week
    history = [h for h in history if h.get("week_key") != week_key]
    
    # Add new entry
    history.append(new_entry)
    
    # Sort by week_key (most recent first)
    history.sort(key=lambda x: x.get("week_key", ""), reverse=True)
    
    # Keep only last max_entries weeks
    history = history[:max_entries]
    
    # Save
    with open(file_path, 'w') as f:
        json.dump(history, f, indent=2)
    
    return history

