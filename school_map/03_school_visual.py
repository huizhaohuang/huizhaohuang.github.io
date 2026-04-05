import frykit.shp as shp
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import pandas as pd
import numpy as np
from PIL import Image
import base64
import os

# ====== 配置 ======
CSV_FILE = 'school_age_population.csv'
MAP_DIR = 'maps'
OUTPUT_HTML = 'school_age_map.html'

os.makedirs(MAP_DIR, exist_ok=True)

# ====== 加载地理数据 ======
gdf = shp.get_cn_district_geodataframe()
prov_gdf = shp.get_cn_province_geodataframe()
census = pd.read_csv(CSV_FILE)

# 去除港澳台
hmt = ['香港特别行政区', '澳门特别行政区', '台湾省']
gdf = gdf[~gdf['province_name'].isin(hmt)].copy()
prov_gdf = prov_gdf[~prov_gdf['province_name'].isin(hmt)].copy()

# 合并
merged = gdf.merge(census, left_on='district_name', right_on='地区', how='left')
print(f"Merged: {len(merged)}, matched: {merged['地区'].notna().sum()}")

# ====== 生成24张地图 ======
stages = ['primary', 'middle', 'high']
stage_labels = {
    'primary': 'Primary School (Age 7–12)',
    'middle': 'Middle School (Age 13–15)',
    'high': 'High School (Age 16–18)'
}
years = [2024, 2025, 2026, 2027]

count = 0
for stage in stages:
    for year in years:
        for metric in ['abs', 'chg']:
            col = f'{stage}_{year}' if metric == 'abs' else f'{stage}_chg_{year}'
            data = merged[col].dropna()

            fig, ax = plt.subplots(1, 1, figsize=(14, 11.5))
            fig.patch.set_facecolor('white')

            if metric == 'chg':
                bound = min(max(abs(data.quantile(0.05)), abs(data.quantile(0.95))), 80)
                vmin, vmax = -bound, bound
                colors_list = ['#2166ac','#67a9cf','#d1e5f0','#f7f7f7','#fddbc7','#ef8a62','#b2182b']
                cmap = mcolors.LinearSegmentedColormap.from_list('div', colors_list, N=256)
                clabel = 'Change vs 2020 (%)'
            else:
                vmin, vmax = data.quantile(0.05), data.quantile(0.95)
                colors_list = ['#f7f4ef','#f0e0c8','#e8c496','#d4956a','#c44d2b','#8b1a1a']
                cmap = mcolors.LinearSegmentedColormap.from_list('seq', colors_list, N=256)
                clabel = 'Population'

            merged.plot(column=col, ax=ax, cmap=cmap, vmin=vmin, vmax=vmax,
                       edgecolor='#e0ddd8', linewidth=0.05,
                       missing_kwds={'color':'#f5f4f0','edgecolor':'#e0ddd8','linewidth':0.05})
            prov_gdf.boundary.plot(ax=ax, edgecolor='#1a1a1a', linewidth=0.5, alpha=0.6)

            ax.set_xlim(73, 136)
            ax.set_ylim(15, 55)
            ax.set_aspect(1.18)
            ax.axis('off')

            sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
            sm._A = []
            cbar = fig.colorbar(sm, ax=ax, shrink=0.35, aspect=18, pad=0.01, location='right')
            cbar.ax.tick_params(labelsize=9, colors='#6b6b6b')
            cbar.set_label(clabel, fontsize=10, color='#6b6b6b', labelpad=8)
            cbar.outline.set_edgecolor('#e0ddd8')

            plt.subplots_adjust(left=0.02, right=0.92, top=0.98, bottom=0.02)
            fname = f'{stage}_{metric}_{year}.jpg'
            plt.savefig(os.path.join(MAP_DIR, fname), dpi=130, bbox_inches='tight',
                       facecolor='white', pil_kwargs={'quality': 78, 'optimize': True})
            plt.close()
            count += 1
            print(f"  [{count}/24] {fname}")

# ====== 编码图片为base64 ======
img_data = {}
for s in stages:
    for m in ['abs', 'chg']:
        for y in years:
            fpath = os.path.join(MAP_DIR, f'{s}_{m}_{y}.jpg')
            with open(fpath, 'rb') as f:
                img_data[f'{s}_{m}_{y}'] = base64.b64encode(f.read()).decode()

# ====== 组装HTML ======
img_js_lines = ',\n'.join(f'"{k}":"data:image/jpeg;base64,{v}"' for k, v in img_data.items())

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>China School-Age Population Projections</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
:root {{
  --black: #1a1a1a;
  --gray: #6b6b6b;
  --light: #f5f4f0;
  --accent: #c44d2b;
  --white: #ffffff;
  --border: #e0ddd8;
}}
*, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}
html {{ scroll-behavior: smooth; -webkit-font-smoothing: antialiased; }}
body {{ font-family: 'DM Sans', sans-serif; font-weight: 300; line-height: 1.7; color: var(--black); background: var(--white); }}

.section-label {{
  font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.18em;
  color: var(--accent); font-weight: 500; margin-bottom: 1rem;
}}
.hero {{
  max-width: 1100px; margin: 0 auto; padding: 6rem 2rem 3rem;
}}
.hero h1 {{
  font-family: 'DM Serif Display', serif; font-size: 2.6rem; line-height: 1.2;
  color: var(--black); margin-bottom: 1rem; letter-spacing: -0.01em;
}}
.hero .subtitle {{
  font-size: 1rem; color: var(--gray); max-width: 680px; line-height: 1.7;
}}
.controls-wrap {{
  border-top: 1px solid var(--border); border-bottom: 1px solid var(--border);
  background: var(--white); position: sticky; top: 0; z-index: 100;
}}
.controls {{
  max-width: 1100px; margin: 0 auto; padding: 1rem 2rem;
  display: flex; justify-content: center; gap: 2rem; flex-wrap: wrap;
}}
.cg {{ display: flex; align-items: center; gap: 0.5rem; }}
.cg label {{
  font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.12em;
  color: var(--gray); font-weight: 500;
}}
.bg {{ display: flex; gap: 0; }}
.b {{
  padding: 0.45rem 1rem; border: 1px solid var(--border); background: var(--white);
  color: var(--gray); font-family: 'DM Sans', sans-serif; font-size: 0.82rem;
  font-weight: 400; cursor: pointer; transition: all 0.2s; letter-spacing: 0.02em;
}}
.b:first-child {{ border-radius: 100px 0 0 100px; }}
.b:last-child {{ border-radius: 0 100px 100px 0; }}
.b:not(:first-child) {{ border-left: none; }}
.b.a {{ background: var(--black); color: var(--white); border-color: var(--black); }}
.b:hover:not(.a) {{ border-color: var(--accent); color: var(--accent); }}

.map-section {{ max-width: 1100px; margin: 0 auto; padding: 2rem 2rem 1rem; }}
.map-header {{ margin-bottom: 0.5rem; }}
.map-header h2 {{
  font-family: 'DM Serif Display', serif; font-size: 1.45rem; line-height: 1.35;
  color: var(--black);
}}
.map-header .map-sub {{ font-size: 0.88rem; color: var(--gray); margin-top: 0.25rem; }}
.map-img-wrap {{ background: var(--white); border-radius: 4px; overflow: hidden; }}
.map-img-wrap img {{ width: 100%; height: auto; display: block; }}
.map-note {{ font-size: 0.75rem; color: var(--gray); margin-top: 0.5rem; letter-spacing: 0.02em; }}

.analysis-section {{
  max-width: 760px; margin: 0 auto; padding: 3rem 2rem 5rem;
  line-height: 1.75; font-size: 0.95rem; color: var(--black);
}}
.analysis-section h2 {{
  font-family: 'DM Serif Display', serif; font-size: 1.8rem;
  color: var(--black); margin: 3rem 0 1.2rem; line-height: 1.3;
}}
.analysis-section h2:first-of-type {{ margin-top: 0; }}
.analysis-section h3 {{
  font-family: 'DM Serif Display', serif; font-size: 1.2rem;
  color: var(--black); margin: 2.5rem 0 0.8rem; line-height: 1.35;
}}
.analysis-section p {{ font-size: 0.95rem; color: var(--black); margin: 0 0 1.1rem; line-height: 1.75; }}
.analysis-section .intro-p {{ color: var(--gray); font-style: italic; margin-bottom: 1.5rem; }}
.divider-line {{ border: none; border-top: 1px solid var(--border); margin: 3rem 0; }}
.finding-num {{
  font-family: 'DM Serif Display', serif; color: var(--border);
  font-size: 0.9rem; display: block; margin-bottom: 0.3rem;
}}
.source-link {{
  margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid var(--border);
  font-size: 0.88rem; color: var(--gray);
}}
.source-link a {{
  color: var(--accent); text-decoration: none; border-bottom: 1px solid transparent;
  transition: border-color 0.2s;
}}
.source-link a:hover {{ border-bottom-color: var(--accent); }}

.footer {{
  max-width: 1100px; margin: 0 auto; padding: 3rem 2rem;
  font-size: 0.78rem; color: var(--border);
}}
.fade-in {{ opacity: 0; transform: translateY(24px); transition: opacity 0.7s ease, transform 0.7s ease; }}
.fade-in.visible {{ opacity: 1; transform: translateY(0); }}

@media (max-width: 720px) {{
  .hero {{ padding: 4rem 1.5rem 2rem; }}
  .hero h1 {{ font-size: 1.8rem; }}
  .controls {{ gap: 1rem; padding: 0.8rem 1rem; }}
  .b {{ padding: 0.4rem 0.7rem; font-size: 0.75rem; }}
  .map-section {{ padding: 1.5rem 1rem 1rem; }}
  .analysis-section {{ padding: 2rem 1.5rem 3rem; }}
  .analysis-section h2 {{ font-size: 1.4rem; }}
}}
</style>
</head>
<body>

<div class="hero fade-in">
  <div class="section-label">Selected Work</div>
  <h1>China's School-Age Population:<br>A County-Level Projection</h1>
  <p class="subtitle">County-level estimates derived from the 2020 National Population Census, mapping the shifting landscape of primary, middle, and high school-age populations across 2,900+ counties from 2024 to 2027.</p>
</div>

<div class="controls-wrap">
<div class="controls">
  <div class="cg"><label>Stage</label><div class="bg" id="sg">
    <button class="b a" data-v="primary">Primary (7–12)</button>
    <button class="b" data-v="middle">Middle (13–15)</button>
    <button class="b" data-v="high">High (16–18)</button>
  </div></div>
  <div class="cg"><label>Year</label><div class="bg" id="yg">
    <button class="b a" data-v="2024">2024</button>
    <button class="b" data-v="2025">2025</button>
    <button class="b" data-v="2026">2026</button>
    <button class="b" data-v="2027">2027</button>
  </div></div>
  <div class="cg"><label>Metric</label><div class="bg" id="mg">
    <button class="b a" data-v="chg">Change (%)</button>
    <button class="b" data-v="abs">Population</button>
  </div></div>
</div>
</div>

<div class="map-section">
  <div class="map-header">
    <h2 id="mt">Primary School (Age 7–12) — 2024</h2>
    <p class="map-sub" id="ms">Percentage change relative to 2020 census baseline</p>
  </div>
  <div class="map-img-wrap">
    <img id="mi" src="" alt="Map visualization">
  </div>
  <p class="map-note">This map displays data for China's 31 mainland provinces only.</p>
</div>

<div class="analysis-section">

<div class="section-label">Analysis</div>
<h2>Introduction</h2>
<p>The turning point for China's school-age population has arrived — swiftly and forcefully. In 2023, many cities were still grappling with the peak enrollment pressure from the two-child policy boom: enrollment warnings, oversized classes, and redistricting were common nationwide. Yet from 2024 onward, more than half of China's counties are projected to see their compulsory education-age populations begin to decline. Following the wave of kindergarten closures, the impact of declining birth rates is now rippling into primary and middle schools.</p>
<p>Drawing on academic research and fieldwork across provinces including Henan and Guangdong, I set out to assemble a more granular picture of China's shifting educational demographics. Three core findings emerged:</p>

<h3><span class="finding-num">01</span>The "Central China Collapse" Demands Attention</h3>
<p>Regional divergence in school-age population trends is stark, and the central provinces — home to the country's largest population base — are precisely where student numbers are shrinking fastest. Previously, western China was seen as the most educationally underserved region, receiving the lion's share of targeted funding. Today, central China's compounding population and fiscal crisis warrants equal urgency.</p>

<h3><span class="finding-num">02</span>Migration Reshapes the Education Map More Profoundly Than Fertility</h3>
<p>Thanks to large inflows of children who migrate with their parents across provincial lines, parts of the Beijing Capital Region, the Yangtze River Delta, and the Pearl River Delta can still post enrollment growth despite low birth rates. However, as more people opt for intra-provincial rather than inter-provincial migration, these traditional destination regions are losing their pull, and their school-age population structures face a medium- to long-term shift.</p>

<h3><span class="finding-num">03</span>From "Investing in Rural Areas" to "Consolidating in Towns"</h3>
<p>The backbone of county-level education is shifting from scattered village schools to boarding schools and urban campuses that pursue economies of scale. Rural families' desire to send children to town schools, village teachers' aspirations to transfer to urban posts, and county governments' impulse to develop "education-driven real estate" have together hit the accelerator on educational urbanization. In some central and western provinces, the educational urbanization rate at the compulsory education stage could exceed 90% — well above the rate of residential urbanization.</p>

<hr class="divider-line">

<h2>Data and Stories: A Panorama of the Student Shortage</h2>
<p class="intro-p">The sections below trace how four macro-regions — the Northeast, Central China, the West, and the East — each face distinct challenges.</p>

<h3>Northeast China</h3>
<p>Low population base, low birth rates, high out-migration — the Northeast presents China's most advanced case of educational depopulation. Over the decade from 2013 to 2022, Heilongjiang lost nearly 60% of its primary schools, Jilin over 50%, and Liaoning close to half. While most provinces are only now approaching their enrollment peaks, Heilongjiang and Jilin passed theirs years ago and have been declining since.</p>
<p>Looking ahead, primary school enrollment in Heilongjiang and Jilin is projected to fall a further 18–20%, and Liaoning by about 11%. Chronic student decline carries a hidden consequence: an aging and increasingly closed-off teaching workforce. Research by Northeast Normal University found that some counties in the region have gone over a decade without hiring a single new teacher. As early as 2010, more than half of Heilongjiang's primary school teachers were over 40 — while in Shenzhen in 2019, 70% of K–12 teachers were under 40.</p>

<h3>Central China: A Collapse at Scale</h3>
<p>If the Northeast is the pioneer of educational depopulation, central China's six provinces are about to face a qualitatively different challenge: collapse at massive scale.</p>
<p>Between 2023 and 2027, primary school enrollment across the six central provinces is projected to fall by over 15% — a rate comparable to the Northeast. But the same percentage translates to vastly different magnitudes: in the Northeast, it means losing roughly half a million students; in central China, it means a reduction on the order of four million — equivalent to emptying over 5,000 eighteen-classroom primary schools.</p>
<p>Henan stands at the epicenter. Over 2023–2027, the province's primary school-age population is projected to drop by more than two million, a contraction exceeding 20%. More than half of Henan's counties are expected to see primary enrollment fall by over 20%. Neighboring Hebei's Zhangjiakou prefecture also shows acute signs of collapse, with counties like Chicheng, Shangyi, and Kangbao seeing middle school-age populations shrinking even faster than primary — a clear signal of student outflow.</p>
<p>Yet central China's inflection point arrived later than the Northeast's. Over the next three years, roughly half of central China's counties will still see middle school enrollment grow; the "student shortage" has not yet swept into secondary education at scale.</p>
<p>Can the resources freed by shrinking enrollments naturally remedy the "education collapse"? Fieldwork suggests otherwise. In 2023, Fugou County in Henan consolidated over a hundred teaching sites with fewer than 50 students, recouping roughly 5.8 million yuan in education funds. That same year, to accommodate students moving into urban areas following school redistricting, the county government invested over 600 million yuan to build four new compulsory education schools — and has budgeted another 680 million yuan for four more. What was saved by closing schools falls far short of what must be spent to build new ones.</p>

<h3>Western China: Another Crossroads</h3>
<p>Most western provinces face a smaller enrollment decline than central China or the Northeast, with primary school losses generally under 10%. But the challenge in the West lies not in the numbers themselves — it lies in the difficulty and cost of redistribution. Mountain terrain accounts for over 86% of the land area across the West's twelve provinces, and more than 60% of its nearly 800 counties are classified as mountainous, severely constraining how education resources can be reorganized.</p>

<h3>Eastern China: Short-Term Pressure, Long-Term Uncertainty</h3>
<p>In contrast to the contracting center and west, eastern China's major destination cities — Beijing, Shanghai, Guangzhou, Shenzhen — still face enrollment expansion pressure over the next three years. But this pressure is unevenly distributed.</p>
<p>A striking pattern: it is the inner suburbs, not the city centers, that bear the greatest strain. As young families migrate to suburbs with lower living costs, core urban districts are slowly aging while suburban education demand surges. In Beijing's Dongcheng and Xicheng, and Shanghai's Jing'an and Huangpu, primary enrollment may fall by more than one-sixth. Meanwhile, suburban districts like Beijing's Changping and Daxing, or Shanghai's Qingpu and Jiading, are projected to see middle school enrollment surge by 40–60%.</p>
<p>Guangzhou and Shenzhen in the Pearl River Delta present a distinctive pattern shaped by both high birth rates and high in-migration. Though Guangzhou covers less than half of Beijing's area and Shenzhen less than one-eighth, both cities have compulsory education-age populations comparable to Beijing's. Over 2023–2027, Guangzhou's primary and middle school enrollments are each projected to grow by roughly 120,000 students, while Shenzhen's middle school enrollment is expected to rise by about 110,000 — an increase of nearly 30%.</p>

<div class="source-link">
  <p>This page is based on my original reporting for <em>Caixin Weekly</em>. The full article (in Chinese) is available <a href="https://weekly.caixin.com/2024-06-28/102210715.html" target="_blank" rel="noopener">here</a>.</p>
</div>

</div>

<div class="footer">
  Data source: 2020 China Population Census (County-level). Projections assume static cohort aging with no migration or mortality.
</div>

<script>
const I={{
{img_js_lines}
}};
const L={{primary:"Primary School (Age 7\\u201312)",middle:"Middle School (Age 13\\u201315)",high:"High School (Age 16\\u201318)"}};
let S="primary",Y="2024",M="chg";
function U(){{
document.getElementById("mi").src=I[S+"_"+M+"_"+Y];
document.getElementById("mt").textContent=L[S]+" \\u2014 "+Y;
document.getElementById("ms").textContent=M==="chg"?"Percentage change relative to 2020 census baseline":"Estimated school-age population count";
}}
function B(g,fn){{
document.querySelectorAll("#"+g+" .b").forEach(b=>{{
b.addEventListener("click",()=>{{
document.querySelectorAll("#"+g+" .b").forEach(x=>x.classList.remove("a"));
b.classList.add("a");fn(b.dataset.v);U();
}});
}});
}}
B("sg",v=>S=v);B("yg",v=>Y=v);B("mg",v=>M=v);
U();
const obs=new IntersectionObserver((entries)=>{{
entries.forEach(e=>{{if(e.isIntersecting){{e.target.classList.add("visible");obs.unobserve(e.target);}}}});
}},{{threshold:0.1}});
document.querySelectorAll(".fade-in").forEach(el=>obs.observe(el));
</script>
</body>
</html>'''

with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Output: {OUTPUT_HTML} ({os.path.getsize(OUTPUT_HTML)/1024/1024:.1f} MB)")
