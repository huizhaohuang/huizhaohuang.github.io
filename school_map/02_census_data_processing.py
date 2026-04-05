import pandas as pd
import numpy as np

# ====== 配置 ======
INPUT_FILE = '2020中国人口普查分县资料_原表勿改_.xlsx'
OUTPUT_FILE = 'school_age_population.csv'

# ====== 读取表2（分年龄分性别） ======
df = pd.read_excel(INPUT_FILE, sheet_name='表2', header=0)
regions = df['地区'].tolist()

# ====== Step 1: 识别并去除汇总行 ======
province_suffixes = ['省', '自治区', '特别行政区']
province_names = {'北京市', '天津市', '上海市', '重庆市'}
remove_idx = set()

for i, r in enumerate(regions):
    if r == '合计':
        remove_idx.add(i)
    elif r in province_names or any(r.endswith(s) for s in province_suffixes):
        remove_idx.add(i)
    elif r == '市辖区':
        remove_idx.add(i)
    elif '直辖县级行政区划' in r:
        remove_idx.add(i)
    elif r.endswith('地区') or r.endswith('盟') or r.endswith('自治州'):
        remove_idx.add(i)

# 地级市判断
for i, r in enumerate(regions):
    if i in remove_idx:
        continue
    if r.endswith('市') and r not in province_names:
        if i + 1 < len(regions):
            next_r = regions[i + 1]
            if next_r == '市辖区':
                pop_i = df.iloc[i]['男_0岁']
                pop_next = df.iloc[i + 1]['男_0岁']
                if pd.notna(pop_i) and pd.notna(pop_next) and pop_i == pop_next:
                    pass  # 不设区地级市，保留
                else:
                    remove_idx.add(i)
            elif next_r.endswith('区') and not next_r.endswith('地区'):
                pop_i = df.iloc[i]['男_0岁'] + df.iloc[i]['女_0岁']
                pop_next = df.iloc[i + 1]['男_0岁'] + df.iloc[i + 1]['女_0岁']
                if pd.notna(pop_i) and pd.notna(pop_next) and pop_i > pop_next * 2:
                    remove_idx.add(i)

county = df.drop(index=remove_idx).reset_index(drop=True)
print(f"去除汇总行后: {len(county)} rows")

# ====== Step 2: 合并男女 ======
county['age_0'] = county['男_0岁'] + county['女_0岁']
county['age_1_4'] = county['男_1到4岁'] + county['女_1到4岁']
county['age_5_9'] = county['男_5到9岁'] + county['女_5到9岁']
county['age_10_14'] = county['男_10到14岁'] + county['女_10到14岁']
county['age_15_19'] = county['男_15到19岁'] + county['女_15到19岁']

# ====== Step 3: 等分拆解为逐岁人口 (0-19岁) ======
for age in range(20):
    if age == 0:
        county[f'p{age}'] = county['age_0']
    elif 1 <= age <= 4:
        county[f'p{age}'] = county['age_1_4'] / 4
    elif 5 <= age <= 9:
        county[f'p{age}'] = county['age_5_9'] / 5
    elif 10 <= age <= 14:
        county[f'p{age}'] = county['age_10_14'] / 5
    elif 15 <= age <= 19:
        county[f'p{age}'] = county['age_15_19'] / 5

# ====== Step 4: 推算2024-2027年三个学段人口 ======
results = []
for _, row in county.iterrows():
    rec = {'地区': row['地区']}
    for year in [2020, 2024, 2025, 2026, 2027]:
        offset = year - 2020
        primary = sum(row[f'p{age - offset}'] for age in range(7, 13) if 0 <= age - offset <= 19)
        middle = sum(row[f'p{age - offset}'] for age in range(13, 16) if 0 <= age - offset <= 19)
        high = sum(row[f'p{age - offset}'] for age in range(16, 19) if 0 <= age - offset <= 19)
        rec[f'primary_{year}'] = primary
        rec[f'middle_{year}'] = middle
        rec[f'high_{year}'] = high
    results.append(rec)

result_df = pd.DataFrame(results)

# 计算变化率
for stage in ['primary', 'middle', 'high']:
    for year in [2024, 2025, 2026, 2027]:
        base = result_df[f'{stage}_2020']
        result_df[f'{stage}_chg_{year}'] = np.where(
            base > 0, (result_df[f'{stage}_{year}'] - base) / base * 100, np.nan
        )

result_df = result_df.round(2)
result_df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
print(f"输出 {len(result_df)} 行 → {OUTPUT_FILE}")