import html
import math

STYLE = """
:root{--bg:#0b1020;--card:#141b34;--line:#26305a;--txt:#e8ecf5;--mut:#8f9bc0;--bad:#f87171;--mid:#fbbf24;--good:#4ade80}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font:15px/1.45 'Segoe UI',Arial,sans-serif;padding:30px 40px}
h1{margin:0 0 4px;font-size:28px}.sub{color:var(--mut);margin-bottom:24px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px 24px;margin-bottom:18px}
.card h2{margin:0 0 12px;font-size:19px;display:flex;justify-content:space-between;align-items:baseline}
.badge{background:#14532d;color:#bbf7d0;border-radius:20px;padding:4px 14px;font-weight:800;font-size:17px}
table{width:100%;border-collapse:collapse}td,th{padding:7px 8px;text-align:left;font-size:14px}th{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:1px}
.bar{height:16px;border-radius:8px;min-width:6px}.num{text-align:right;font-variant-numeric:tabular-nums}.note{color:var(--mut);font-size:12px;margin-top:6px}
"""


def _color(ratio: float) -> str:
    return "var(--bad)" if ratio > 0.66 else "var(--mid)" if ratio > 0.33 else "var(--good)"


def render_report(data: dict) -> str:
    d = data["dataset"]
    cards = ""
    for ep in data["endpoints"]:
        base = ep["stages"][0]["median_ms"]
        best = ep["stages"][-1]["median_ms"]
        speedup = base / best if best else 0
        # шкала логарифмическая: иначе быстрые стадии превращаются в невидимые полоски
        top = math.log10(max(s["median_ms"] for s in ep["stages"]) * 10)
        rows = ""
        for s in ep["stages"]:
            ratio = math.log10(max(s["median_ms"], 0.1) * 10) / top
            sp = base / s["median_ms"] if s["median_ms"] else 0
            rows += (
                f"<tr><td>{html.escape(s['stage'])}</td><td style='width:38%'><div class='bar' style='width:{max(2, ratio * 100):.0f}%;background:{_color(ratio)}'></div></td>"
                f"<td class='num'>{s['median_ms']:.1f} мс</td><td class='num'>{s['p95_ms']:.1f}</td><td class='num'>{s['queries']}</td><td class='num'>{'' if s is ep['stages'][0] else f'×{sp:,.0f}'}</td></tr>"
            )
        cards += (
            f"<div class='card'><h2><span>{html.escape(ep['name'])}</span><span class='badge'>×{speedup:,.0f} быстрее</span></h2>"
            f"<table><tr><th>Стадия</th><th>Время (лог. шкала)</th><th class='num'>Медиана</th><th class='num'>p95, мс</th><th class='num'>SQL-запросов</th><th class='num'>Ускорение</th></tr>{rows}</table></div>"
        )
    return (
        f"<!doctype html><html lang='ru'><head><meta charset='utf-8'><title>Benchmark</title><style>{STYLE}</style></head><body>"
        f"<h1>Оптимизация API: до и после</h1>"
        f"<div class='sub'>{d['customers']:,} клиентов · {d['orders']:,} заказов · {d['order_items']:,} позиций · {data['database']} · медиана из {data['runs']} запусков</div>"
        f"{cards}<div class='note'>Время измерено на HTTP-уровне (TestClient), результаты всех версий сверены на идентичность.</div></body></html>"
    )
